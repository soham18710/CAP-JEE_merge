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
        print(f"🌐 Fetching from URL: {path}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(path, headers=headers, timeout=30)
        response.raise_for_status() # Raises error if download fails
        print("✅ Download complete.")
        return io.BytesIO(response.content)
    else:
        print(f"📁 Opening local file: {path}...")
        if not os.path.exists(path):
             raise FileNotFoundError(f"❌ Could not find local file: {path}")
        return open(path, 'rb')

# =========================================
# ---- Step 1: Extract from CAP PDF ----
# =========================================

cap_pdf_path = 'CAP.pdf' 
all_cap_ids = [] 
try:
    with load_pdf(cap_pdf_path) as f:
        reader = PyPDF2.PdfReader(f)
        for page in tqdm(reader.pages, desc="Processing CAP PDF"):
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                match = re.search(r'\bEN\d{8}\b', line)
                if match:
                    app_id = match.group()
                    all_cap_ids.append(app_id) 

    print(f"✅ Found {len(all_cap_ids)} students in CAP PDF") 

except Exception as e:
    print(f"❌ Error processing CAP PDF: {e}")
    exit()

# =========================================
# ---- Step 2: Extract from JEE PDF ----
# =========================================

jee_pdf_path = 'JEE.pdf'  # Ensure this file is in your folder
jee_records = []
all_id_set = set(all_cap_ids) 

if not all_id_set:
    print("⚠️ No students found in CAP PDF. Skipping JEE extraction.")
else:
    try:
        with load_pdf(jee_pdf_path) as f:
            reader = PyPDF2.PdfReader(f)
            for page in tqdm(reader.pages, desc="Processing JEE PDF"):
                text = page.extract_text()
                if not text: continue
                for line in text.split("\n"):
                    parts = line.split()
                    if len(parts) > 4 and re.match(r"EN\d{8}", parts[1]):
                        app_id = parts[1]
                        if app_id in all_id_set:
                            merit_no = parts[0]
                            try:
                                jee_pos = parts.index("JEE")
                                name = " ".join(parts[2:jee_pos])
                                start_idx = jee_pos + 1
                                values = [parts[i] if i < len(parts) else '' for i in range(start_idx, start_idx + 16)]
                                record = [merit_no, app_id, name] + values
                                jee_records.append(record)
                            except ValueError:
                                continue 
    except Exception as e:
         print(f"\n⚠️ Warning: Could not process JEE PDF ({e}). Continuing with just CAP data...")

# =========================================
# ---- Step 3 & 4: Merge and Save ----
# =========================================

print("\n🔄 Merging data...")

jee_columns = [
    "Merit_No", "Application_ID", "JEE_Name",
    "JEE_Main_Percentile", "JEE_Math_Percentile", "JEE_Physics_Percentile", "JEE_Chemistry_Percentile",
    "MHT_CET_PCM_Total", "MHT_CET_Math", "MHT_CET_Physics", "MHT_CET_Chemistry",
    "HSC_PCM_Percent", "HSC_Math_Percent", "HSC_Physics_Percent", "HSC_Total_Percent",
    "SSC_Total_Percent", "SSC_Math_Percent", "SSC_Science_Percent", "SSC_English_Percent"
]

cap_df = pd.DataFrame(all_cap_ids, columns=['Application_ID']) 
jee_df = pd.DataFrame(jee_records, columns=jee_columns)

merged = pd.merge(cap_df, jee_df, on="Application_ID", how="left")

merged['JEE_Main_Percentile'] = pd.to_numeric(merged['JEE_Main_Percentile'], errors='coerce')
merged = merged.sort_values('JEE_Main_Percentile', ascending=False)

output_filename = 'ALL_CAP_JEE_Merged.csv'
merged.to_csv(output_filename, index=False)

print(f"\n🎉 SUCCESS! Merged data saved to: {output_filename}")
print(f"Total Students: {len(merged)}")
print(f"Students with JEE Data Matched: {merged['JEE_Main_Percentile'].notna().sum()}")
print("\nTop 5 Students by JEE Score (using JEE_Name):")
print(merged[['Application_ID', 'JEE_Name', 'JEE_Main_Percentile']].head()) 
