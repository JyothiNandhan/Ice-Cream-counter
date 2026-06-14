import base64
import asyncio
import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import logging

from database import init_db, save_scan, get_previous_scan
from vision import extract_inventory
from agent import generate_report
from whatsapp import send_to_all
from models import AnalyzeResponse

# Ensure config validation runs
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ice Cream Inventory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    init_db()

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred on the server.", "error": str(exc)},
    )

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_freezer(images: List[UploadFile] = File(...)):
    if not images or len(images) == 0:
        raise HTTPException(status_code=400, detail="No images provided")
        
    logger.info(f"Received {len(images)} images for analysis")
    
    # 1. Read images as bytes and base64
    images_bytes = []
    images_base64 = []
    for img in images:
        content = await img.read()
        images_bytes.append(content)
        images_base64.append(base64.b64encode(content).decode("utf-8"))
        
    # 2. Vision Pipeline: Extract inventory
    try:
        inventory_items_models = await asyncio.to_thread(extract_inventory, images_bytes, images_base64)
        inventory_items_dicts = [item.model_dump() for item in inventory_items_models]
    except Exception as e:
        logger.error(f"Vision extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze photos: {str(e)}")
        
    # 3. Database: Save scan and get previous
    timestamp = datetime.datetime.now().isoformat()
    scan_id = save_scan(inventory_items_dicts, timestamp)
    
    current_scan = {
        "id": scan_id,
        "timestamp": timestamp,
        "items": inventory_items_dicts
    }
    
    previous_scan = get_previous_scan()
    
    # 4. Agent Pipeline: Generate structured report and WhatsApp message
    try:
        report_data = await asyncio.to_thread(generate_report, current_scan, previous_scan)
        structured_report = report_data.get("structured_report", [])
        whatsapp_message = report_data.get("whatsapp_message", "")
    except Exception as e:
        logger.error(f"Agent report generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
        
    # 5. WhatsApp Pipeline: Send messages
    whatsapp_statuses = await send_to_all(whatsapp_message)
    
    return AnalyzeResponse(
        scan_id=scan_id,
        timestamp=timestamp,
        report=structured_report,
        whatsapp_statuses=whatsapp_statuses,
        whatsapp_message=whatsapp_message
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
