from pydantic import BaseModel
from typing import List, Optional

class InventoryItem(BaseModel):
    brand: str
    product_name: str
    sku_identifier: Optional[str] = None
    fill_level: Optional[str] = None   # FULL / MEDIUM / LOW / EMPTY (primary metric)
    units_currently_visible: int
    shelf_capacity_estimate: int
    confidence: str

class ScanResult(BaseModel):
    items: List[InventoryItem]

class ReportItem(InventoryItem):
    units_sold: Optional[int] = None
    restock_urgency: str

class WhatsAppStatus(BaseModel):
    number: str
    success: bool
    error_message: Optional[str] = None

class AnalyzeResponse(BaseModel):
    scan_id: int
    timestamp: str
    report: List[ReportItem]
    whatsapp_statuses: List[WhatsAppStatus]
    whatsapp_message: str

class POSSaleItem(BaseModel):
    brand: str
    product_name: str
    units_sold: int
    remaining: int
    full_stock: int
    needs_reorder: bool

class POSAnalyzeResponse(BaseModel):
    date: str
    items: List[POSSaleItem]
    whatsapp_statuses: List[WhatsAppStatus]
    whatsapp_message: str
    critical: bool
    items_to_reorder: List[str]

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
