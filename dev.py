import os
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add the root directory to sys.path so we can import from 'api'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the app from our api/index.py
from api.index import app

# Keep the original routes from api/index.py and just add static serving for local dev
app.mount("/", StaticFiles(directory="public", html=True), name="static")

@app.get("/")
async def read_index():
    return FileResponse('index.html')

if __name__ == "__main__":
    import uvicorn
    print("Starting Local Development Server...")
    print("Serving static files from root directory")
    print("API routes active (/upload, /progress, /download)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
