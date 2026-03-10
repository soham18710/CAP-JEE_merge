import os
import shutil
import asyncio
import json
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
# Handle imports for both local and Vercel
try:
    from cap_and_jee import merge_pdfs
except ImportError:
    from api.cap_and_jee import merge_pdfs

from vercel_blob import put
import sys

# Ensure api directory is in path for relative imports
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.append(api_dir)

from fastapi.staticfiles import StaticFiles

# Global progress state
progress_state = {
    "stage": "Idle", 
    "percent": 0, 
    "message": "Ready",
    "current": 0,
    "total": 0,
    "start_time": 0
}

app = FastAPI(title="CAP-JEE Merit Merger")
# Vercel entry point
print("--- Server Starting: Version 2.0 (Enhanced Progress & Robust PDF) ---")

# Enable CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (Optional on Vercel as it serves them directly)
# app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Use /tmp for serverless environments (Vercel)
UPLOAD_DIR = "/tmp/uploads" if os.environ.get("VERCEL") else "uploads"
RESULTS_FILE = os.path.join("/tmp" if os.environ.get("VERCEL") else ".", "ALL_CAP_JEE_Merged.csv")

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/progress")
async def get_progress(request: Request):
    async def event_generator():
        while True:
            # Check if client closed connection
            if await request.is_disconnected():
                break
            
            yield f"data: {json.dumps(progress_state)}\n\n"
            await asyncio.sleep(0.5) # Update every 500ms
            
            if progress_state["percent"] == 100 and progress_state["stage"] == "Completed":
                # Final message before closing
                yield f"data: {json.dumps(progress_state)}\n\n"
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/upload")
async def upload_files(cap_pdf: UploadFile = File(...), jee_pdf: UploadFile = File(...)):
    cap_path = os.path.join(UPLOAD_DIR, "CAP.pdf")
    jee_path = os.path.join(UPLOAD_DIR, "JEE.pdf")

    try:
        # Use async read to get the full file content reliably
        cap_content = await cap_pdf.read()
        jee_content = await jee_pdf.read()
        
        with open(cap_path, "wb") as buffer:
            buffer.write(cap_content)
        with open(jee_path, "wb") as buffer:
            buffer.write(jee_content)
        
        # Process the PDFs with progress tracking
        import time
        stage_start_time = time.time()
        
        def on_progress(stage, percent, message, current=0, total=0):
            nonlocal stage_start_time
            if progress_state["stage"] != stage:
                stage_start_time = time.time()
                
            progress_state["stage"] = stage
            progress_state["percent"] = percent
            progress_state["message"] = message
            progress_state["current"] = current
            progress_state["total"] = total
            progress_state["start_time"] = stage_start_time

        progress_state["stage"] = "Initialising"
        progress_state["percent"] = 0
        progress_state["message"] = "Starting PDF processing..."
        progress_state["current"] = 0
        progress_state["total"] = 0
        progress_state["start_time"] = time.time()

        # Run synchronous merge in a threadpool
        try:
            from fastapi.concurrency import run_in_threadpool
            df = await run_in_threadpool(merge_pdfs, cap_path, jee_path, on_progress)
        except ValueError as ve:
            progress_state["stage"] = "Error"
            progress_state["message"] = str(ve)
            raise HTTPException(status_code=400, detail=str(ve))
        
        if df is None or df.empty:
            progress_state["stage"] = "Error"
            progress_state["message"] = "No records found after merging."
            raise HTTPException(status_code=400, detail="Merging failed: No records were found after matching CAP and JEE data.")
        
        progress_state["stage"] = "Saving"
        progress_state["message"] = "Saving results..."
        df.to_csv(RESULTS_FILE, index=False)
        
        # Upload to Vercel Blob if token is present
        blob_url = None
        if os.environ.get("BLOB_READ_WRITE_TOKEN"):
            try:
                with open(RESULTS_FILE, "rb") as f:
                    resp = put("CAP_JEE_Merged_Results.csv", f.read(), {"access": "public"})
                    blob_url = resp.get("url")
                    # Store URL in environment or a simple local cache (limited effectiveness in serverless)
                    os.environ["VERCEL_BLOB_URL"] = blob_url
            except Exception as e:
                print(f"Blob upload failed: {e}")

        progress_state["stage"] = "Completed"
        progress_state["percent"] = 100
        progress_state["message"] = "Process successfully finished."
        
        # Prepare a preview
        preview = df.head(50).fillna("").to_dict(orient="records")
        summary = {
            "total_students": len(df),
            "matched_students": int(df['JEE_Main_Percentile'].notna().sum()),
            "download_url": blob_url or "/download"
        }
        
        return JSONResponse(content={
            "message": "Files processed successfully",
            "summary": summary,
            "preview": preview
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download")
async def download_results():
    if os.environ.get("VERCEL_BLOB_URL"):
        # If we have a stored blob URL, redirect to it
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=os.environ.get("VERCEL_BLOB_URL"))
    
    if not os.path.exists(RESULTS_FILE):
        raise HTTPException(status_code=404, detail="Results file not found. Please upload files first.")
    return FileResponse(path=RESULTS_FILE, filename="CAP_JEE_Merged_Results.csv", media_type='text/csv')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
