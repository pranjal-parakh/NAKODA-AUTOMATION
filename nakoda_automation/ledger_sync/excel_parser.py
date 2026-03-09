import pandas as pd
import unicodedata
import time
import re
DEBUG_EXCEL_IMPORT = True

def normalize_text(x):
    if pd.isna(x):
        return x
    return unicodedata.normalize("NFC", str(x)).strip()

def extract_metadata(raw_name):
    # Default values
    tenure_months = 0
    internal_ref_code = ""
    name_clean = raw_name

    if not isinstance(raw_name, str) or not raw_name:
        return name_clean, tenure_months, internal_ref_code

    # 1. Extract Tenure (e.g. "1 माह", "2 माह")
    tenure_match = re.search(r'\((\d+)\s*माह\)', raw_name)
    if tenure_match:
        tenure_months = int(tenure_match.group(1))
        # Remove from name
        name_clean = re.sub(r'\(\d+\s*माह\)', '', name_clean)

    # 2. Extract Internal Code (e.g. "(93)", "(60)")
    # This regex looks for digits inside parentheses that are not right before "माह"
    code_matches = re.findall(r'\((\d+)\)', name_clean)
    if code_matches:
        internal_ref_code = code_matches[-1]
        
        # Remove ALL numeric codes
        name_clean = re.sub(r'\(\d+\)', '', name_clean)

    # Clean up any leftover double spaces or trailing/leading spaces
    name_clean = re.sub(r'\s+', ' ', name_clean).strip()
    return name_clean, tenure_months, internal_ref_code


def process_excel(file_path):
    start = time.perf_counter()
    
    # 1.1 Sheet Detection
    xls = pd.ExcelFile(file_path, engine="openpyxl")
    
    jaavak_sheet = [s for s in xls.sheet_names if "जावक" in s]
    aavak_sheet = [s for s in xls.sheet_names if "आवक" in s]
    
    if not jaavak_sheet:
        return [], None
    jaavak_sheet_name = jaavak_sheet[0]

    if not aavak_sheet:
        aavak_sheet_name = None
    else:
        aavak_sheet_name = aavak_sheet[0]

    records = []

    # Let's extract posting date from sheet name or A1 if possible
    # We will just parse the sheet name string "18-02-2026 मंगलवार"
    # User's python env will capture today if it fails
    # Quick date extractor
    date_match = re.search(r'(\d{2}-\d{2}-\d{4})', jaavak_sheet_name)
    excel_date = date_match.group(1) if date_match else None

    # --- PROCESS UDHAARI ---
    df_j = pd.read_excel(xls, sheet_name=jaavak_sheet_name, header=None)
    df_j = df_j.map(normalize_text)

    # Find boundaries
    u_mask = df_j.apply(lambda row: row.astype(str).str.contains("उधारी", na=False).any(), axis=1)
    if u_mask.any():
        y_start_u = df_j[u_mask].index[0]
        
        stop_mask = df_j.apply(lambda row: row.astype(str).str.contains("TOTAL|UPI|जमा", na=False).any(), axis=1)
        valid_stops = df_j[stop_mask].index
        next_stops = [idx for idx in valid_stops if idx > y_start_u]
        y_end_u = next_stops[0] if next_stops else len(df_j)

        udhaari_df = df_j.iloc[y_start_u+1:y_end_u].copy()
        
        for _, row in udhaari_df.iterrows():
            vals = list(row.values)
            if len(vals) < 7: continue # Too empty, skip
            
            bill_no = str(vals[2]).strip() if pd.notna(vals[2]) else ""
            raw_name = str(vals[4]).strip() if pd.notna(vals[4]) else ""
            village = str(vals[5]).strip() if pd.notna(vals[5]) else ""
            amt_raw = str(vals[6]).replace(",", "").strip() if len(vals) > 6 and pd.notna(vals[6]) else ""
            phone = str(vals[7]).split('.')[0].strip() if len(vals) > 7 and pd.notna(vals[7]) else ""
            if phone in ("nan", "None"): phone = ""
            
            if not raw_name or not amt_raw:
                continue

            try:
                amount = float(amt_raw)
            except ValueError:
                amount = 0.0
                
            if amount == 0.0:
                continue

            name_clean, tenure_months, internal_ref_code = extract_metadata(raw_name)

            if DEBUG_EXCEL_IMPORT:
                print(f"Parsed Udhaari -> bill_no: {bill_no}, raw_name: {raw_name}, village: {village}, amount: {amount}, phone: {phone}")

            records.append({
                "type": "Udhaari",
                "row_no": bill_no,
                "raw_name": raw_name,
                "name_clean": name_clean,
                "village": village,
                "amount": amount,
                "phone": phone,
                "tenure_months": tenure_months,
                "internal_ref_code": internal_ref_code
            })

    return records, excel_date
