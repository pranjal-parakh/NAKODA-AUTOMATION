import pandas as pd
import unicodedata
import re
from nakoda_automation.ledger_sync.excel_parser import extract_metadata, normalize_text

DEBUG_JAMA_IMPORT = True

def parse_jama(file_path):
    xls = pd.ExcelFile(file_path, engine="openpyxl")
    aavak_sheet = [s for s in xls.sheet_names if "आवक" in s]
    
    if not aavak_sheet:
        return []
        
    aavak_sheet_name = aavak_sheet[0]
    df_a = pd.read_excel(xls, sheet_name=aavak_sheet_name, header=None)
    df_a = df_a.map(normalize_text)

    records = []
    
    # 1. Locate exact "जमा" to find starting boundary
    j_mask = df_a.apply(lambda row: row.astype(str).str.strip().eq("जमा").any(), axis=1)
    if not j_mask.any():
        return records
        
    y_start_j = df_a[j_mask].index[0]
    
    # 2. Scope boundary till TOTAL
    t_mask = df_a.apply(lambda row: row.astype(str).str.contains("TOTAL|Total|total", na=False).any(), axis=1)
    valid_t = df_a[t_mask].index
    next_t = [idx for idx in valid_t if idx > y_start_j]
    y_end_j = next_t[0] if next_t else len(df_a)

    # 3. Extract the scoped DataFrame. 
    # INCLUDE y_start_j since the same row contains "जमा " *and* the very first record
    jama_df = df_a.iloc[y_start_j:y_end_j].copy()
    
    # User's mapped strict columns logic 
    for _, row in jama_df.iterrows():
        vals = list(row.values)
        
        # Pandas naturally extracts them shifted due to column merging
        while len(vals) <= 10:
            vals.append("")
            
        raw_name = str(vals[6]).strip() if pd.notna(vals[6]) else ""
        village = str(vals[9]).strip() if pd.notna(vals[9]) else ""
        amt_raw = str(vals[10]).replace(",", "").strip() if pd.notna(vals[10]) else ""
        
        # Fallback to user specified exactly (4, 5, 6) just in case the file actually strips merge headers
        if not raw_name and not amt_raw and len(vals) > 6:
            raw_name_fb = str(vals[4]).strip() if pd.notna(vals[4]) else ""
            amt_raw_fb = str(vals[6]).replace(",", "").strip() if pd.notna(vals[6]) else ""
            if raw_name_fb and amt_raw_fb and raw_name_fb != "nan":
                raw_name = raw_name_fb
                village = str(vals[5]).strip() if pd.notna(vals[5]) else ""
                amt_raw = amt_raw_fb
            
        if not raw_name or not amt_raw or raw_name == "nan" or amt_raw == "nan":
            continue
            
        # Ignore filter conditions explicitly
        row_str_search = raw_name + " " + " ".join(str(v) for v in vals)
        if any(kw in row_str_search for kw in ["गिरवी", "AD का जमा", "नगदी", "स्कीम", "अन्य", "ब्याज"]):
            continue
            
        try:
            amount = float(amt_raw)
        except ValueError:
            amount = 0.0
            
        if amount <= 0:
            continue

        name_clean, tenure_months, internal_ref_code = extract_metadata(raw_name)

        if DEBUG_JAMA_IMPORT:
            print(f"Parsed Jama -> raw_name: {raw_name}, village: {village}, amount: {amount}")

        records.append({
            "type": "जमा",
            "row_no": "N/A",
            "raw_name": raw_name,
            "name_clean": name_clean,
            "village": village,
            "amount": amount,
            "phone": "",
            "tenure_months": "",
            "internal_ref_code": ""
        })
        
    return records
