import PyPDF2
import re
import pandas as pd
from tqdm import tqdm
import requests
import io
import os

def load_pdf(path):
    """Opens a PDF from a URL or local path and returns a file-like object."""
    if path.startswith(('http://', 'https://')):
        print(f"[FETCH] Fetching from URL: {path}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(path, headers=headers, timeout=30)
        response.raise_for_status() # Raises error if download fails
        print("[SUCCESS] Download complete.")
        return io.BytesIO(response.content)
    else:
        print(f"[FILE] Opening local file: {os.path.abspath(path)}...")
        if not os.path.exists(path):
             raise FileNotFoundError(f"Could not find local file: {path}")
        return open(path, 'rb')

def merge_pdfs(cap_pdf_path, jee_pdf_path, progress_callback=None):
    """Merges CAP and JEE PDF data and returns a DataFrame.
    
    Args:
        cap_pdf_path: Path to CAP PDF
        jee_pdf_path: Path to JEE PDF
        progress_callback: Optional function(stage, percent, message) to report progress
    """
    def update_progress(stage, percent, message, current=0, total=0):
        if progress_callback:
            progress_callback(stage, percent, message, current, total)

    all_cap_ids = []
    update_progress("Step 1/2", 0, "Initializing CAP extraction...")
    print("\n=========================================")
    print("---- Step 1: Extract from CAP PDF ----")
    print("=========================================")
    try:
        with load_pdf(cap_pdf_path) as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            for i, page in enumerate(tqdm(reader.pages, desc="Processing CAP PDF")):
                # Report CAP progress (capped at 50% for step 1)
                update_progress("Step 1/2", int((i / total_pages) * 50), f"Extracting IDs: Page {i+1}/{total_pages}", i+1, total_pages)
                text = page.extract_text()
                if not text:
                    print(f"[DEBUG] Page {i+1}: No text extracted.")
                    continue
                print(f"[DEBUG] Page {i+1}: Extracted {len(text)} characters.")
                # More robust extraction: find all IDs in the page text
                # Supporting both EN25... and EN 25...
                ids = re.findall(r'EN\s?\d{8}', text, re.IGNORECASE)
                # Normalize IDs to ENXXXXXXXX format
                normalized_ids = [re.sub(r'\s+', '', i).upper() for i in ids]
                all_cap_ids.extend(normalized_ids)
        
        print(f"[INFO] Found {len(all_cap_ids)} students in CAP PDF")
    except Exception as e:
        print(f"[ERROR] Error processing CAP PDF: {e}")
        raise ValueError(f"Failed to process CAP PDF: {str(e)}")

    jee_records = []
    all_id_set = set(all_cap_ids)
    if not all_id_set:
        print("[WARN] No students found in CAP PDF.")
        raise ValueError("No student IDs (format EN25XXXXXX) were found in the CAP PDF. Please ensure this is the correct document.")

    print("\n=========================================")
    print("---- Step 2: Extract from JEE PDF ----")
    print("=========================================")
    try:
        with load_pdf(jee_pdf_path) as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            for i, page in enumerate(tqdm(reader.pages, desc="Processing JEE PDF")):
                # Report JEE progress (starts at 50%, ends at 100%)
                update_progress("Step 2/2", 50 + int((i / total_pages) * 50), f"Matching JEE data: Page {i+1}/{total_pages}", i+1, total_pages)
                text = page.extract_text()
                if not text: continue
                for line in text.split("\n"):
                    # Clean up the line and parts
                    parts = line.split()
                    if not parts: continue
                    
                    # Search for Application ID in the first few parts
                    app_id = None
                    for part in parts[:3]: # Usually ID is in first 3 parts
                        if re.match(r"EN\d{8}", part):
                            app_id = part
                            break
                    
                    if app_id and app_id in all_id_set:
                        merit_no = parts[0]
                        try:
                            # Use "JEE" as a marker to find where values start
                            if "JEE" in parts:
                                jee_pos = parts.index("JEE")
                                name = " ".join(parts[parts.index(app_id)+1:jee_pos])
                                start_idx = jee_pos + 1
                                values = [parts[i] if i < len(parts) else '' for i in range(start_idx, start_idx + 16)]
                                record = [merit_no, app_id, name] + values
                                jee_records.append(record)
                        except (ValueError, IndexError):
                            continue
    except Exception as e:
         print(f"\n[WARN] Warning: Could not process JEE PDF ({e}). Continuing with just CAP data...")

    print("\n=========================================")
    print("---- Step 3 & 4: Merge and Save ----")
    print("=========================================")
    print("\n[MERGING] Merging data...")

    jee_columns = [
        "Merit_No", "Application_ID", "JEE_Name",
        "JEE_Main_Percentile", "JEE_Math_Percentile", "JEE_Physics_Percentile", "JEE_Chemistry_Percentile",
        "MHT_CET_PCM_Total", "MHT_CET_Math", "MHT_CET_Physics", "MHT_CET_Chemistry",
        "HSC_PCM_Percent", "HSC_Math_Percent", "HSC_Physics_Percent", "HSC_Total_Percent",
        "SSC_Total_Percent", "SSC_Math_Percent", "SSC_Science_Percent", "SSC_English_Percent"
    ]

    cap_df = pd.DataFrame(all_cap_ids, columns=['Application_ID'])
    cap_df['Application_ID'] = cap_df['Application_ID'].str.strip().str.upper()
    cap_df = cap_df.drop_duplicates(subset=['Application_ID'])
    
    if jee_records:
        jee_df = pd.DataFrame(jee_records, columns=jee_columns)
        jee_df['Application_ID'] = jee_df['Application_ID'].str.strip()
        merged = pd.merge(cap_df, jee_df, on="Application_ID", how="left")
    else:
        print("[WARN] No JEE records found. Creating empty JEE columns.")
        for col in jee_columns:
            if col != 'Application_ID':
                cap_df[col] = pd.NA
        merged = cap_df
    
    if not merged.empty and 'JEE_Main_Percentile' in merged.columns:
        merged['JEE_Main_Percentile'] = pd.to_numeric(merged['JEE_Main_Percentile'], errors='coerce')
        merged = merged.sort_values('JEE_Main_Percentile', ascending=False)
    
    return merged

if __name__ == "__main__":
    # For local execution
    cap_path = 'CAP.pdf'
    jee_path = 'JEE.pdf'
    df = merge_pdfs(cap_path, jee_path)
    if df is not None:
        output_filename = 'ALL_CAP_JEE_Merged.csv'
        df.to_csv(output_filename, index=False)
        print(f"\n[SUCCESS] Merged data saved to: {output_filename}")
        print(f"Total Students: {len(df)}")
        print(f"Students with JEE Data Matched: {df['JEE_Main_Percentile'].notna().sum()}")
        print("\nTop 5 Students by JEE Score (using JEE_Name):")
        print(df[['Application_ID', 'JEE_Name', 'JEE_Main_Percentile']].head())
