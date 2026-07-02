import asyncio
import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import logging

from database import (
    init_db, save_scan, get_previous_scan, update_scan_report,
    get_scan_history, get_scan_by_id, get_supervisor, create_supervisor,
)
from vision import extract_inventory
from agent import generate_report
from whatsapp import send_to_all
from pos_analyzer import extract_pos_sales, calculate_inventory, build_pos_whatsapp_message
from auth import verify_password, hash_password, create_access_token
from stock_routes import router as stock_router
from models import AnalyzeResponse, POSAnalyzeResponse, POSSaleItem, LoginRequest, TokenResponse
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ice Cream Inventory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stock_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    init_db()
    # Seed default supervisor if none exists
    if not get_supervisor("supervisor"):
        create_supervisor("supervisor", hash_password("admin123"))
        logger.info("Default supervisor created: supervisor / admin123")


@app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    supervisor = get_supervisor(body.username)
    if not supervisor or not verify_password(body.password, supervisor["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(body.username)
    return TokenResponse(access_token=token, username=body.username)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred on the server.", "error": str(exc)},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}


@app.get("/history")
async def get_history(limit: int = 20):
    try:
        scans = get_scan_history(limit=min(limit, 100))
        return {"scans": scans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/{scan_id}")
async def get_scan(scan_id: int):
    scan = get_scan_by_id(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return scan


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_freezer(images: List[UploadFile] = File(...)):
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")

    logger.info(f"Received {len(images)} image(s) for analysis")

    # 1. Read images as bytes
    images_bytes = []
    for img in images:
        images_bytes.append(await img.read())

    # 2. Vision Pipeline: identify and count products
    try:
        inventory_items_models = await asyncio.to_thread(extract_inventory, images_bytes)
        inventory_items_dicts = [item.model_dump() for item in inventory_items_models]
    except Exception as e:
        logger.error(f"Vision extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze photos: {str(e)}")

    # 3. Persist the raw vision scan
    timestamp = datetime.datetime.now().isoformat()
    scan_id = save_scan(inventory_items_dicts, timestamp)

    current_scan = {"id": scan_id, "timestamp": timestamp, "items": inventory_items_dicts}
    previous_scan = get_previous_scan()

    # 4. Agent Pipeline: compare scans, compute urgency, compose WhatsApp message
    try:
        report_data = await asyncio.to_thread(generate_report, current_scan, previous_scan)
    except Exception as e:
        logger.error(f"Agent report generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

    structured_report = report_data.get("structured_report", [])
    whatsapp_message = report_data.get("whatsapp_message", "")

    # 5. Persist the enriched report (urgency + units_sold) back to the database
    update_scan_report(scan_id, structured_report)

    # 6. WhatsApp: send to all configured numbers
    whatsapp_statuses = await send_to_all(whatsapp_message)

    return AnalyzeResponse(
        scan_id=scan_id,
        timestamp=timestamp,
        report=structured_report,
        whatsapp_statuses=whatsapp_statuses,
        whatsapp_message=whatsapp_message,
    )


@app.post("/analyze-pos", response_model=POSAnalyzeResponse)
async def analyze_pos(image: UploadFile = File(...)):
    """Mode 2: Upload a POS sales report screenshot → math-based inventory → WhatsApp alert."""
    if not image:
        raise HTTPException(status_code=400, detail="No image provided")

    image_bytes = await image.read()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1. OCR the POS image to get units sold per product
    try:
        sales_data = await asyncio.to_thread(extract_pos_sales, image_bytes)
    except Exception as e:
        logger.error(f"POS extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read POS image: {str(e)}")

    # 2. Pure math — no AI needed here
    inventory = calculate_inventory(sales_data)

    # 3. Build WhatsApp message
    message = build_pos_whatsapp_message(inventory, date_str)

    # 4. Send WhatsApp
    whatsapp_statuses = await send_to_all(message)

    items_to_reorder = [i["product_name"] for i in inventory if i["needs_reorder"]]

    return POSAnalyzeResponse(
        date=date_str,
        items=[POSSaleItem(**i) for i in inventory],
        whatsapp_statuses=whatsapp_statuses,
        whatsapp_message=message,
        critical=len(items_to_reorder) > 1,
        items_to_reorder=items_to_reorder,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
