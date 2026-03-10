import PyPDF2
import re
import os

def check_uploads():
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        print("Uploads directory missing")
        return
    
    files = ["CAP.pdf", "JEE.pdf"]
    for filename in files:
        path = os.path.join(upload_dir, filename)
        if not os.path.exists(path):
            print(f"File missing: {path}")
            continue
            
        print(f"Checking {path} ({os.path.getsize(path)} bytes)")
        try:
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = reader.pages[0].extract_text()
                ids = re.findall(r'EN\s?\d{8}', text, re.I)
                print(f"  First page text length: {len(text) if text else '0'}")
                print(f"  First page IDs: {ids[:5]}")
        except Exception as e:
            print(f"  Error reading {path}: {e}")

if __name__ == "__main__":
    check_uploads()
