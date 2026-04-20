import string
import frappe
from rapidfuzz import process, fuzz
from nakoda_automation.ledger_sync.excel_parser import DEBUG_EXCEL_IMPORT

def get_all_customers():
    """Fetch all customers with their villages/custom fields for matching."""
    # Assuming 'custom_village' exists. Adjust if standard territory is used.
    # We will fetch mobile number as well.
    customers = frappe.get_all(
        "Customer",
        fields=["name", "customer_name", "custom_village", "mobile_no"],
        filters={"disabled": 0}
    )
    return customers

def clean_for_match(text):
    if not text:
        return ""
    text = str(text).lower()
    # Strip basic punctuation to help fuzzy match, including '/'
    for p in string.punctuation.replace("(", "").replace(")", "") + "/":
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
        c_name = c.get("customer_name")
        c_vil = c.get("custom_village") or ""
        
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
            
    if best_score >= 30:
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
        
        if DEBUG_EXCEL_IMPORT:
            print({
                "raw_name": record.get("raw_name"),
                "name_clean": raw_name,
                "matched_customer": doc.customer_name,
                "match_score": score
            })
            
        # 3.2 Phone Handling Rule: append if different
        if clean_phone:
            existing_phone = str(doc.get("mobile_no") or "").strip()
            # If empty, just set it
            if not existing_phone:
                # doc.mobile_no = clean_phone
                changed = True
                # phone_updated = True
            else:
                # Check if this exact number is already in the string (comma/space separated)
                parts = [p.strip() for p in existing_phone.replace(",", " ").split() if p.strip()]
                if clean_phone not in parts:
                    # Append it
                    # Ensure we don't exceed field limit (usually 140 or 255 depending on system, but Customer mobile_no is usually small)
                    # new_val = existing_phone + ", " + clean_phone
                    # if len(new_val) < 130: # Safe margin for standard mobile_no fields
                        # doc.mobile_no = new_val
                        changed = True
                        # phone_updated = True
                    
        if village and not doc.custom_village:
            vname = str(village).strip()
            # Use db_set to update the field directly in the DB, bypassing
            # ERPNext's validate() pipeline (which enforces customer_group rules
            # and can fail on existing data with Group-type customer groups).
            doc.db_set("custom_village", vname, update_modified=False)
            changed = False  # Already saved via db_set, no need to call doc.save()

        if changed:
            try:
                doc.flags.ignore_permissions = True
                doc.flags.ignore_validate = True
                doc.save()
            except Exception as e:
                frappe.log_error(f"Customer update skipped for {doc.name}: {e}", "Matching Warning")
            
        return matched_id, False, phone_updated, {"matched_via": "V1 Fuzzy", "score": score}
        
    # NEW CUSTOMER CREATION DISABLED AS PER REQUEST (For both Udhaari and Jama)
    # The return values will indicate No Match, allowing the user to create them manually.
    if DEBUG_EXCEL_IMPORT:
        print(f"No match for customer: {raw_name} ({village}). Creation disabled.")
        
    return None, False, False, {"reason": "No fuzzy match found (Score < 30)"}

def resolve_customer_v2(record, existing_customers):
    """
    Deterministic hierarchical matching pipeline (V2).
    """
    raw_name_input = record.get("raw_name", "")
    name_clean = record.get("name_clean", "")
    village_input = record.get("village", "") or ""
    
    clean_name_search = clean_for_match(name_clean)
    clean_vil_search = clean_for_match(village_input)
    
    match_details = {
        "v2_active": True,
        "village_candidates": 0,
        "prefix_candidates": 0,
        "best_score": 0,
        "reason": "",
        "matched_village": ""
    }
    
    # STEP 1: VILLAGE FILTER (STRICT)
    village_candidates = []
    for c in existing_customers:
        c_vil = c.get("custom_village") or ""
        target_vil = clean_for_match(c_vil)
        
        if not clean_vil_search and not target_vil:
            vil_score = 100
        else:
            vil_score = fuzz.token_sort_ratio(clean_vil_search, target_vil)
            
        if vil_score >= 90:
            village_candidates.append(c)
            
    match_details["village_candidates"] = len(village_candidates)
            
    if not village_candidates:
        match_details["reason"] = f"No village candidates found (Strict Match score < 90/100 for '{village_input}')"
        cid, is_new, ph_upd, legacy_details = resolve_customer(record, existing_customers)
        match_details.update(legacy_details)
        match_details["v2_active"] = False
        return cid, is_new, ph_upd, match_details
        
    # STEP 2: PREFIX FILTER (LOCALIZED)
    prefix_candidates = []
    words = [w.strip() for w in name_clean.split() if w.strip()]
    if words:
        prefix = words[0][:3].lower()
        for i, c in enumerate(village_candidates):
            c_name_clean = clean_for_match(c.get("customer_name") or "")
            c_words = [w.strip() for w in c_name_clean.split() if w.strip()]
            if c_words and c_words[0].lower().startswith(prefix):
                prefix_candidates.append(c)
                
    match_details["prefix_candidates"] = len(prefix_candidates)
    
    final_candidates = prefix_candidates if prefix_candidates else village_candidates
    if not prefix_candidates:
        match_details["info"] = "No prefix matches found; using all village candidates."
    
    # STEP 3: FINAL RESOLUTION
    matched_customer = None
    best_score = 0
    
    for c in final_candidates:
        c_name_clean = clean_for_match(c.get("customer_name") or "")
        score = fuzz.token_sort_ratio(clean_name_search, c_name_clean)
        if score > best_score:
            best_score = score
            matched_customer = c
                
    match_details["best_score"] = best_score
    if matched_customer:
        match_details["matched_village"] = matched_customer.get("custom_village")
        
    if not matched_customer or best_score < 30:
        match_details["reason"] = f"Fuzzy score {best_score} < 30 threshold"
        cid, is_new, ph_upd, legacy_details = resolve_customer(record, existing_customers)
        # Preserve V2 metrics but use V1 reason if V1 found it
        match_details["legacy_match"] = legacy_details
        return cid, is_new, ph_upd, match_details
        
    # STEP 4: RESOLVE & UPDATE
    match_details["matched_via"] = "V2 Prefix/Village" if prefix_candidates else "V2 Village Fuzzy"
    cid, is_new, ph_upd, _ = resolve_customer(record, [matched_customer])
    return cid, is_new, ph_upd, match_details
