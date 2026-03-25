import string
import frappe
from rapidfuzz import process, fuzz

def get_all_customers():
    """Fetch all customers with their villages/custom fields for matching."""
    # Assuming 'local_address' exists. Adjust if standard territory is used.
    # We will fetch mobile number as well.
    customers = frappe.get_all(
        "Customer",
        fields=["name", "customer_name", "local_address", "mobile_no"],
        filters={"disabled": 0}
    )
    return customers

def clean_for_match(text):
    if not text:
        return ""
    text = str(text).lower()
    # Strip basic punctuation to help fuzzy match
    for p in string.punctuation:
        text = text.replace(p, " ")
    return " ".join(text.split())

def match_customer(customer_name, village, existing_customers):
    """
    Find best customer match using rapidfuzz token_sort_ratio.
    Formula: 0.7 * name_score + 0.3 * village_score
    """
    if not customer_name:
        return None, 0
        
    c_name_search = clean_for_match(customer_name)
    c_vil_search = clean_for_match(village)

    best_score = 0
    best_match_id = None
    
    for c in existing_customers:
        c_name = c.get("customer_name") or c.get("name")
        c_vil = c.get("local_address") or ""
        
        target_name = clean_for_match(c_name)
        target_vil = clean_for_match(c_vil)
        
        name_score = fuzz.token_sort_ratio(c_name_search, target_name)
        
        # If village strings are empty, do we penalize? No, we just use name match entirely or count village as 100 if both empty?
        # Actually doing standard match:
        vil_score = fuzz.token_sort_ratio(c_vil_search, target_vil) if (c_vil_search or target_vil) else 100
        
        candidate_score = (0.7 * name_score) + (0.3 * vil_score)
        
        if candidate_score > best_score:
            best_score = candidate_score
            best_match_id = c.get("name")
            
    if best_score >= 70:
        return best_match_id, best_score
        
    return None, best_score

def resolve_customer(record, existing_customers):
    """
    Given an excel record dictionary, finds or creates the customer.
    """
    raw_name = record.get("name_clean", "")
    village = record.get("village", "")
    phone = str(record.get("phone", "")).strip()
    
    # Strip everything except digits and plus for phone validation
    clean_phone = "".join([c for c in phone if c.isdigit() or c == "+"])
    if len(clean_phone) < 6:
        clean_phone = "" # Not a real phone
    
    # 1. Fuzzy match
    matched_id, score = match_customer(raw_name, village, existing_customers)
    phone_updated = False
    
    if matched_id:
        doc = frappe.get_doc("Customer", matched_id)
        changed = False
        
        from nakoda_automation.ledger_sync.excel_parser import DEBUG_EXCEL_IMPORT
        if DEBUG_EXCEL_IMPORT:
            print({
                "raw_name": record.get("raw_name"),
                "name_clean": raw_name,
                "matched_customer": doc.customer_name,
                "match_score": score
            })
            
        # 3.2 Phone Handling Rule: append if different
        if clean_phone:
            existing_phone = doc.get("mobile_no") or ""
            if not existing_phone:
                doc.mobile_no = clean_phone
                changed = True
                phone_updated = True
            elif clean_phone not in existing_phone:
                if len(existing_phone) > 20: 
                    pass # Don't exceed field limit 
                else:
                    doc.mobile_no = existing_phone + ", " + clean_phone
                    changed = True
                    phone_updated = True
                    
        if village and not doc.local_address:
            vname = str(village).strip()
            if not frappe.db.exists("Village", vname):
                try:
                    vdoc = frappe.new_doc("Village")
                    vdoc.village_name = vname
                    vdoc.insert(ignore_permissions=True)
                except: pass
            doc.local_address = vname
            changed = True
                    
        if changed:
            doc.flags.ignore_permissions = True
            doc.save()
            
        return matched_id, False, phone_updated
        
    if record.get("type", "") == "Jama":
        from nakoda_automation.ledger_sync.excel_parser import DEBUG_EXCEL_IMPORT
        if DEBUG_EXCEL_IMPORT:
            print({
                "raw_name": record.get("raw_name"),
                "village": village,
                "error": "Customer not found"
            })
        return None, False, False
        
    # Create new customer
    if not raw_name:
        raw_name = f"Unknown - {village}" if village else "Unknown Customer"
        
    doc = frappe.new_doc("Customer")
    doc.customer_name = raw_name
    doc.customer_type = "Individual"
    # doc.customer_group = "Commercial" # default
    # doc.territory = "All Territories" # default
    if clean_phone:
        doc.mobile_no = clean_phone
        phone_updated = True
        
    if village:
        # Link logic: Ensure village exists, then set link
        vname = str(village).strip()
        if not frappe.db.exists("Village", vname):
            try:
                vdoc = frappe.new_doc("Village")
                vdoc.village_name = vname
                vdoc.insert(ignore_permissions=True)
            except:
                pass
        doc.local_address = vname 
        
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    
    from nakoda_automation.ledger_sync.excel_parser import DEBUG_EXCEL_IMPORT
    if DEBUG_EXCEL_IMPORT:
        print({
            "raw_name": record.get("raw_name"),
            "name_clean": raw_name,
            "matched_customer": doc.customer_name,
            "match_score": "NEW (Score: {:.2f})".format(score)
        })
    
    # Reload existing dictionary list so new customer is fuzzy matched next time in the loop
    existing_customers.append({
        "name": doc.name,
        "customer_name": doc.customer_name,
        "local_address": doc.get("local_address"),
        "mobile_no": doc.get("mobile_no")
    })
    
    return doc.name, True, phone_updated
