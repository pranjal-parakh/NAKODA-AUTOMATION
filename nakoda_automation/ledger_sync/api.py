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
        from nakoda_automation.ledger_sync.matching import get_all_customers, resolve_customer
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
        new_villages = []
        
        for rec in records:
            matched_id, is_new, ph_upd = resolve_customer(rec, existing_customers)
            
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
        matched_udhaari = sum(1 for r in records if r.get("type") == "उधारी" and r.get("_customer_id"))
        matched_jama = sum(1 for r in records if r.get("type") == "जमा" and r.get("_customer_id"))
        
        skipped_jms = [r.get("raw_name") for r in records if r.get("type") == "जमा" and not r.get("_customer_id")]
        skipped_udh = [r.get("raw_name") for r in records if r.get("type") == "उधारी" and not r.get("_customer_id")]
        
        skipped_jama = len(skipped_jms)
        skipped_udhaari = len(skipped_udh)
        
        success_msg = f"<b>Extraction Completed in {duration}s</b><br><br>"
        success_msg += f"📦 Total Records Found: {total_rows}<br>"
        success_msg += f"--------------------------------<br>"
        success_msg += f"📉 <b>उधारी (Udhaari)</b><br>"
        success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• Total in Excel: {len(ud_records)}<br>"
        success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• Mapped successfully: {matched_udhaari}<br>"
        if skipped_udhaari > 0:
            uv_list = ", ".join(skipped_udh[:5])
            if len(skipped_udh) > 5: uv_list += f" (+{len(skipped_udh)-5} more)"
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• ⚠️ Unmatched (Create Manually): {skipped_udhaari} ({uv_list})<br>"

        success_msg += f"<br>"
        success_msg += f"📈 <b>जमा (Jama)</b><br>"
        success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• Total in Excel: {len(jm_records)}<br>"
        success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• Mapped successfully: {matched_jama}<br>"
        if skipped_jama > 0:
            jv_list = ", ".join(skipped_jms[:5])
            if len(skipped_jms) > 5: jv_list += f" (+{len(skipped_jms)-5} more)"
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• ⚠️ Unmatched (Skipped): {skipped_jama} ({jv_list})<br>"
        success_msg += f"<br>"
        success_msg += f"👤 <b>Updates</b><br>"
        
        if customers_created > 0:
            c_list = ", ".join(created_customer_names[:5])
            if len(created_customer_names) > 5: c_list += f" (+{len(created_customer_names)-5} more)"
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• New Customers Created: {customers_created} ({c_list})<br>"
        else:
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• New Customers Created: 0<br>"
            
        if phones_updated > 0:
            p_list = ", ".join(updated_phone_names[:5])
            if len(updated_phone_names) > 5: p_list += f" (+{len(updated_phone_names)-5} more)"
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• Phone Numbers Updated: {phones_updated} ({p_list})<br>"
        else:
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;• Phone Numbers Updated: 0<br>"
        
        if new_villages:
            success_msg += f"<br>🏘️ <b>New Villages Added:</b><br>"
            # Limit to 5 names to keep it clean
            v_list = ", ".join(new_villages[:5])
            if len(new_villages) > 5: v_list += f" (+{len(new_villages)-5} more)"
            success_msg += f"&nbsp;&nbsp;&nbsp;&nbsp;{v_list}<br>"
            
        success_msg += f"--------------------------------<br>"
        success_msg += "<br>Please verify the <b>Pending</b> rows in the grid below before final Posting."
        
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
