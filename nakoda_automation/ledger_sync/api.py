import frappe
from frappe import _
from datetime import datetime
from frappe.utils import add_months, getdate
import json
import hashlib

import time

@frappe.whitelist()
def parse_excel_ledger():
    start_time = time.perf_counter()
    try:
        if "file_url" not in frappe.form_dict or "dashboard_id" not in frappe.form_dict:
            frappe.throw(_("Please provide file_url and dashboard_id"))
            
        file_url = frappe.form_dict.get("file_url")
        dashboard_id = frappe.form_dict.get("dashboard_id")
        
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()
        
        if not file_path.endswith(".xlsx"):
            frappe.throw(_("Invalid file type. Please upload an Excel (.xlsx) file."))

        from nakoda_automation.ledger_sync.excel_parser import process_excel
        from nakoda_automation.ledger_sync.jama_parser import parse_jama
        
        ud_records, excel_date = process_excel(file_path)
        jm_records = parse_jama(file_path)
        
        records = ud_records + jm_records
        
        ledger_day = frappe.get_doc("Nakoda Ledger Day", dashboard_id)
        
        if not records:
            return {"status": "success", "message": "No structured rows found."}

        posting_date = excel_date or getdate()
        from nakoda_automation.ledger_sync.matching import get_all_customers, resolve_customer, resolve_customer_v2
        existing_customers = get_all_customers()

        # Update Ledger Day main fields only if not set
        if not ledger_day.ledger_date:
            ledger_day.ledger_date = posting_date
        
        proc_log = []
        proc_log.append({"step": "Parsed Excel", "total_records": len(records)})
        
        # Phase 1: Pre-resolve Customers to ensure Link Database validity
        frappe.db.begin()
        customers_created = 0
        created_customer_names = []
        phones_updated = 0
        updated_phone_names = []
        
        # Read checkbox state from the doctype (defaults to True if field missing)
        USE_V2 = bool(ledger_day.get("use_v2_matching", 1))
        
        for rec in records:
            if USE_V2:
                matched_id, is_new, ph_upd, m_details = resolve_customer_v2(rec, existing_customers)
            else:
                matched_id, is_new, ph_upd, m_details = resolve_customer(rec, existing_customers)
            
            rec["_match_details"] = m_details
            
            # Fetch the actual customer_name for display/storage as requested
            customer_display_name = None
            if matched_id:
                customer_display_name = frappe.db.get_value("Customer", matched_id, "customer_name")
            
            rec["_customer_id"] = matched_id
            rec["_customer_name"] = customer_display_name
            
            if is_new:
                customers_created += 1
                created_customer_names.append(rec.get("raw_name") or f"Unknown - {rec.get('village', 'No Village')}")
            if ph_upd:
                phones_updated += 1
                if customer_display_name not in updated_phone_names:
                    updated_phone_names.append(customer_display_name or matched_id)
                
            if matched_id:
                proc_log.append({
                    "step": "Customer Resolved", 
                    "raw_name": rec.get("raw_name"), 
                    "matched_id": customer_display_name or matched_id,
                    "is_new": is_new,
                    "phone_updated": ph_upd
                })
            elif rec.get("type") == "जमा":
                proc_log.append({
                    "step": "Customer Not Found", 
                    "raw_name": rec.get("raw_name"), 
                    "error": "Customer not found"
                })
        frappe.db.commit()
        
        # Clear existing rows to prevent duplication if parsing twice
        ledger_day.set("ledger_rows", [])
        
        # Populate mapped Data mapped in Pending State
        total_udhaari = 0
        total_jama = 0
        for rec in records:
            txn_type = rec.get("type", "")
            amt = rec.get("amount", 0)
            status = "Pending"
            msg = ""
            if not rec.get("_customer_id"):
                status = "Skipped"
                msg = f"Customer '{rec.get('raw_name')}' not found. Skipped Posting."
            
            display_type = "जमा" if txn_type == "जमा" else "उधारी"
                
            if status == "Pending":
                if txn_type == "उधारी":
                    total_udhaari += amt
                elif txn_type == "जमा":
                    total_jama += amt
                
            # Ensure village exists in our new Village DocType before appending to grid
            vname = str(rec.get("village", "")).strip()
            if vname and vname not in ("None", "nan"):
                if not frappe.db.exists("Village", vname):
                    try:
                        # vdoc = frappe.new_doc("Village")
                        # vdoc.village_name = vname
                        # vdoc.insert(ignore_permissions=True)
                        new_villages.append(vname)
                    except:
                        pass
            else:
                vname = None

            ledger_day.append("ledger_rows", {
                "transaction_type": display_type,
                "row_reference": rec.get("row_no", ""),
                "customer": rec.get("_customer_name") or rec.get("_customer_id"),
                "customer_name_raw": rec.get("raw_name"),
                "village": vname,
                "amount": amt,
                "status": status,
                "message": msg,
                "matched_village": rec.get("_match_details", {}).get("matched_village"),
                "match_info": json.dumps(rec.get("_match_details", {}), indent=2, ensure_ascii=False),
                "tenure_months": rec.get("tenure_months", 0)
            })
            
        # As we lost `tenure_months` from the row dictionary, let's just save it to string or message for now
        # Actually better to save all records json into processing log and we can retrieve it during posting.
        ledger_day.processing_log = json.dumps({"records": records, "log": "Parsed perfectly."}, indent=4, ensure_ascii=False)
        ledger_day.total_udhaari = total_udhaari
        ledger_day.total_jama = total_jama
        
        # Bypass link validation to allow friendly names in the customer columns as requested
        ledger_day.flags.ignore_links = True
        ledger_day.flags.ignore_permissions = True
        
        ledger_day.save()
        frappe.db.commit()
        
        duration = round(time.perf_counter() - start_time, 2)
        total_rows = len(records)
        matched_udhaari = sum(1 for r in records if r.get("type") == "\u0909\u0927\u093e\u0930\u0940" and r.get("_customer_id"))
        matched_jama = sum(1 for r in records if r.get("type") == "\u091c\u092e\u093e" and r.get("_customer_id"))
        skipped_jama = sum(1 for r in records if r.get("type") == "\u091c\u092e\u093e" and not r.get("_customer_id"))
        skipped_udhaari = sum(1 for r in records if r.get("type") == "\u0909\u0927\u093e\u0930\u0940" and not r.get("_customer_id"))
        
        # ── Summary header ───────────────────────────────────────────────────
        success_msg  = f"<b>Extraction Completed in {duration}s</b><br>"
        success_msg += f"<span style='font-size:0.85rem;color:#888;'>Total: {total_rows} records &nbsp;|&nbsp; "
        success_msg += f"\u091c\u092e\u093e: {len(jm_records)} ({matched_jama} mapped, {skipped_jama} unmatched) &nbsp;|&nbsp; "
        success_msg += f"\u0909\u0927\u093e\u0930\u0940: {len(ud_records)} ({matched_udhaari} mapped, {skipped_udhaari} unmatched)"
        if customers_created > 0:
            success_msg += f" &nbsp;|&nbsp; \U0001f464 New: {customers_created}"
        if phones_updated > 0:
            success_msg += f" &nbsp;|&nbsp; \U0001f4de Updated: {phones_updated}"
        success_msg += "</span>"
        
        # ── Per-transaction detail table ─────────────────────────────────────
        def build_txn_table(recs, title, emoji):
            if not recs:
                return ""
            tbl  = f"<br><br><b>{emoji} {title}</b>"
            tbl += "<div style='overflow-x:auto;width:100%;'>"
            tbl += (
                "<table style='width:100%;border-collapse:collapse;font-size:0.72rem;margin-top:6px;white-space:nowrap;'>"
                "<thead><tr>"
                "<th style='padding:4px 6px;text-align:left;border:1px solid #ccc;'>#</th>"
                "<th style='padding:4px 6px;text-align:left;border:1px solid #ccc;'>Raw Name</th>"
                "<th style='padding:4px 6px;text-align:left;border:1px solid #ccc;'>Raw Village</th>"
                "<th style='padding:4px 6px;text-align:left;border:1px solid #ccc;'>Village</th>"
                "<th style='padding:4px 6px;text-align:left;border:1px solid #ccc;'>Matched Customer</th>"
                "<th style='padding:4px 6px;text-align:left;border:1px solid #ccc;'>Via</th>"
                "<th style='padding:4px 6px;text-align:center;border:1px solid #ccc;'>Score</th>"
                "<th style='padding:4px 6px;text-align:right;border:1px solid #ccc;'>Amount</th>"
                "</tr></thead><tbody>"
            )
            total_amt = 0
            for idx, r in enumerate(recs, 1):
                md      = r.get("_match_details") or {}
                matched = bool(r.get("_customer_id"))
                cname   = r.get("_customer_name") or r.get("_customer_id") or "\u2014"
                
                raw_village = r.get("village") or "\u2014"
                
                m_village = md.get("matched_village") or ""
                r_village = r.get("village") or ""
                if matched and m_village:
                    vil_cell = f"<span style='color:green;'>\u2714 {m_village}</span>"
                elif r_village:
                    vil_cell = f"<span style='color:red;'>\u2718 {r_village}</span>"
                else:
                    vil_cell = "\u2014"
                
                raw_score = float(md.get("best_score") or md.get("score") or 0)
                score_disp = f"{round(raw_score, 1)}%" if raw_score else "\u2014"
                score_color = "green" if raw_score >= 70 else ("orange" if raw_score >= 30 else "red")
                
                via = md.get("matched_via") or ("V1 Fuzzy" if md.get("score") else ("\u2014" if matched else "No Match"))
                
                cname_disp = (
                    f"<b style='color:{score_color};'>{cname}</b>" if matched
                    else f"<span style='color:red;'>\u2718 Not Matched</span>"
                )
                amt_val = r.get('amount', 0)
                total_amt += amt_val
                amt = f"\u20b9{amt_val:,.0f}"
                
                tbl += (
                    f"<tr>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;'>{idx}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;'>{r.get('raw_name','')}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;'>{raw_village}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;'>{vil_cell}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;'>{cname_disp}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;'>{via}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;text-align:center;"
                    f"color:{score_color};font-weight:700;'>{score_disp}</td>"
                    f"<td style='padding:3px 5px;border:1px solid #ccc;text-align:right;"
                    f"font-weight:600;'>{amt}</td>"
                    f"</tr>"
                )
            # Total footer row
            tbl += (
                f"<tr>"
                f"<td colspan='7' style='padding:6px 10px;border:1px solid #ccc;"
                f"text-align:right;font-weight:700;'>Total</td>"
                f"<td style='padding:6px 10px;border:1px solid #ccc;text-align:right;"
                f"font-weight:700;'>\u20b9{total_amt:,.0f}</td>"
                f"</tr>"
            )
            tbl += "</tbody></table></div>"
            return tbl
        
        jama_recs    = [r for r in records if r.get("type") == "\u091c\u092e\u093e"]
        udhaari_recs = [r for r in records if r.get("type") == "\u0909\u0927\u093e\u0930\u0940"]
        
        success_msg += build_txn_table(jama_recs,    "\u091c\u092e\u093e (Jama) Transactions",    "\U0001f4c8")
        success_msg += build_txn_table(udhaari_recs, "\u0909\u0927\u093e\u0930\u0940 (Udhaari) Transactions", "\U0001f4c9")

        
        return {"status": "success", "message": success_msg}
        
    except Exception as e:
        frappe.log_error(title="Parse Excel Error", message=frappe.get_traceback())
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def post_ledger_entries():
    try:
        if "dashboard_id" not in frappe.form_dict:
            frappe.throw(_("Please provide dashboard_id"))
            
        dashboard_id = frappe.form_dict.get("dashboard_id")
        ledger_day = frappe.get_doc("Nakoda Ledger Day", dashboard_id)
        
        if ledger_day.rows_processed > 0 or ledger_day.rows_failed > 0:
            return {"status": "error", "message": "Already processed. Cannot post again."}
            
        posting_date = ledger_day.ledger_date
        total_udhaari = 0
        total_jama = 0
        processed = 0
        failed = 0
        skipped = 0
        
        proc_log = []
        has_error = False
        error_msg = ""
        
        # Extract original records from processing log
        raw_cache = {}
        try:
            log_data = json.loads(ledger_day.processing_log)
            for r in log_data.get("records", []):
                # match by row_no + raw_name + type
                key = f"{r.get('type')}_{r.get('row_no')}_{r.get('raw_name')}"
                raw_cache[key] = r
        except:
            pass
            
        frappe.db.begin()
        
        for row in ledger_day.ledger_rows:
            if row.status != "Pending":
                continue
                
            status = "Pending"
            msg = ""
            row_ref = row.row_reference
            amt = row.amount
            display_type = row.transaction_type
            txn_type = "Jama" if display_type == "जमा" else "Udhaari"
            
            row_key = f"{txn_type}_{row_ref}_{row.customer_name_raw}"
            raw_rec = list(filter(lambda r: r.get("type") == txn_type and str(r.get("row_no")) == str(row_ref), log_data.get("records", [])))
            original_rec = raw_rec[0] if raw_rec else {}
            
            # Prefer original internal ID, fall back to row column
            customer_id = original_rec.get("_customer_id") or row.customer
            
            # Strictly honor the owner's selected date on the Ledger Day record
            posting_date = ledger_day.ledger_date
            
            try:
                row_string = f"{customer_id}|{posting_date}|{amt}|{txn_type}"
                row_hash = hashlib.sha256(row_string.encode('utf-8')).hexdigest()
                
                if records_exists(row_hash):
                    status = "Duplicate"
                    msg = "Hash already exists"
                    skipped += 1
                else:
                    if txn_type == "Udhaari":
                        invoice = frappe.new_doc("Sales Invoice")
                        invoice.customer = customer_id
                        invoice.set_posting_time = 1
                        invoice.posting_date = posting_date
                        
                        tenure = row.tenure_months or 0
                        if tenure == 0:
                            tenure = 2
                        invoice.due_date = add_months(posting_date, tenure)
                            
                        if not frappe.db.exists("Item", "Udhaari Entry"):
                            item = frappe.new_doc("Item")
                            item.item_code = "Udhaari Entry"
                            item.item_name = "Udhaari Entry"
                            item.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
                            item.is_stock_item = 0
                            item.insert(ignore_permissions=True)
                            
                        invoice.append("items", {
                            "item_code": "Udhaari Entry", 
                            "qty": 1,
                            "rate": amt,
                            "amount": amt
                        })
                        invoice.flags.ignore_permissions = True
                        invoice.insert()
                        invoice.submit()
                        
                        record_hash(row_hash, "Sales Invoice", invoice.name)
                        status = "Posted"
                        total_udhaari += amt
                        proc_log.append({"step": "Posted Invoice", "customer": customer_id, "invoice_id": invoice.name, "amount": amt})
                        
                    elif txn_type == "Jama":
                        pe = frappe.new_doc("Payment Entry")
                        pe.payment_type = "Receive"
                        pe.party_type = "Customer"
                        pe.party = customer_id
                        
                        pe.posting_date = posting_date
                        pe.paid_amount = amt
                        pe.received_amount = amt
                        
                        company = frappe.defaults.get_user_default("company") or frappe.get_all("Company")[0].name
                        pe.mode_of_payment = pe.mode_of_payment or "Cash"
                        
                        cash_acc = frappe.db.get_value("Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name")
                        if not cash_acc:
                            cash_acc = frappe.db.get_value("Account", {"company": company, "account_type": "Bank", "is_group": 0}, "name")
                            
                        if not cash_acc:
                            frappe.throw(f"No valid Cash or Bank account found for company {company}")
                            
                        pe.paid_to = cash_acc
                        pe.company = company
                        
                        # Auto allocate loosely
                        # Fetch outstanding invoices using standard method
                        outstanding = frappe.get_all("Sales Invoice", filters={"customer": customer_id, "docstatus": 1, "outstanding_amount": [">", 0]}, fields=["name", "outstanding_amount"], order_by="posting_date asc")
                        
                        alloc_left = amt
                        for inv in outstanding:
                            if alloc_left <= 0: break
                            alloc_amt = min(inv.outstanding_amount, alloc_left)
                            pe.append("references", {
                                "reference_doctype": "Sales Invoice",
                                "reference_name": inv.name,
                                "allocated_amount": alloc_amt
                            })
                            alloc_left -= alloc_amt

                        pe.flags.ignore_permissions = True
                        pe.insert()
                        pe.submit()
                        
                        record_hash(row_hash, "Payment Entry", pe.name)
                        status = "Posted"
                        total_jama += amt
                        proc_log.append({"step": "Posted Payment", "customer": customer_id, "payment_id": pe.name, "amount": amt})
                        
                    processed += 1
                    
            except Exception as e:
                frappe.log_error(title="Row Process Failed", message=frappe.get_traceback())
                status = "Failed"
                msg = str(e)[:140]
                failed += 1
                has_error = True
                error_msg = msg
                proc_log.append({"step": "Error", "customer": customer_id, "error": msg})

            row.status = status
            row.message = msg
            
        if has_error:
            frappe.db.rollback()
            frappe.db.begin()
            ledger_day.rows_processed = processed
            ledger_day.rows_failed = failed
            proc_log.append({"step": "Transaction Aborted", "reason": f"Atomic transaction aborted due to row error: {error_msg}"})
            ledger_day.processing_log = json.dumps(proc_log, indent=4, ensure_ascii=False)
            # Revert rows to pending, except the ones we failed on? No, just save. Actually rolling back the DB rolls back row child writes too.
            ledger_day.flags.ignore_links = True
            ledger_day.flags.ignore_permissions = True
            ledger_day.save()
            frappe.db.commit()
            return {"status": "error", "message": f"Atomic transaction aborted due to row error: {error_msg}"}
            
        else:
            ledger_day.rows_processed = processed
            ledger_day.rows_failed = failed
            ledger_day.processing_log = json.dumps(proc_log, indent=4, ensure_ascii=False)
            ledger_day.flags.ignore_links = True
            ledger_day.flags.ignore_permissions = True
            ledger_day.save()
            frappe.db.commit()
            return {"status": "success", "message": "ERP Ledger Postings successful!"}
            
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="Ledger Posting Failed", message=frappe.get_traceback())
        return {"status": "error", "message": str(e)}

def records_exists(row_hash):
    check1 = frappe.db.exists("Sales Invoice", {"remarks": f"Hash:{row_hash}"})
    check2 = frappe.db.exists("Payment Entry", {"remarks": f"Hash:{row_hash}"})
    return bool(check1 or check2)

def record_hash(row_hash, doctype, docname):
    frappe.db.set_value(doctype, docname, "remarks", f"Hash:{row_hash}")
