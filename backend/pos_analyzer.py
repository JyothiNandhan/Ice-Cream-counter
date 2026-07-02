import json
import base64
import io
import logging
from typing import List, Dict, Any

from PIL import Image
from openai import OpenAI

from config import NVIDIA_VISION_API_KEY, NVIDIA_BASE_URL
from database import upsert_product_stock, update_current_stock_after_sales

logger = logging.getLogger(__name__)

vision_client = OpenAI(
    api_key=NVIDIA_VISION_API_KEY,
    base_url=NVIDIA_BASE_URL,
)

POS_VISION_PROMPT = """You are an OCR agent reading a Point of Sale (POS) daily sales report screenshot.

Extract every ice cream product row from the table. Products are grouped under brand/supplier headers.

For each PRODUCT row (skip subtotal and total rows), return:
- "brand": the brand/group header above this product (e.g. "Nestle", "Haagen-Dazs")
- "product_name": product name exactly as printed
- "units_sold": the value in the "Sold" column as an integer (e.g. 1.0 → 1, 3.0 → 3)

Return ONLY a raw JSON array. No markdown. No explanation.

[
  {"brand": "Nestle", "product_name": "Drumstick 14oz", "units_sold": 1},
  {"brand": "Nestle", "product_name": "Kit Kat 14oz", "units_sold": 3}
]"""


def _compress_image(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.width > 1024:
        ratio = 1024 / img.width
        img = img.resize((1024, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def extract_pos_sales(image_bytes: bytes) -> List[Dict[str, Any]]:
    """OCR the POS screenshot → list of {brand, product_name, units_sold}."""
    b64 = _compress_image(image_bytes)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": POS_VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]
    }]

    raw = ""
    for attempt in range(2):
        try:
            response = vision_client.chat.completions.create(
                model="meta/llama-3.2-90b-vision-instruct",
                messages=messages,
                temperature=0.0,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content.strip()

            for fence in ("```json", "```"):
                if raw.startswith(fence):
                    raw = raw[len(fence):]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

            parsed = json.loads(raw)
            for item in parsed:
                item["units_sold"] = int(float(item.get("units_sold", 0)))
            logger.info(f"[POS] Extracted {len(parsed)} products from POS image")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"[POS] JSON parse error attempt {attempt + 1}: {e}")
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": "Return ONLY the raw JSON array. No markdown."})
        except Exception as e:
            logger.error(f"[POS] API error attempt {attempt + 1}: {e}")

    raise Exception("Failed to extract sales data from POS image after 2 attempts")


def calculate_inventory(sales_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Looks up live current_stock from DB for each product.
    remaining = current_stock - units_sold
    Updates DB with the new remaining stock after sales.
    """
    result = []
    for item in sales_data:
        brand = item["brand"]
        product_name = item["product_name"]
        units_sold = item["units_sold"]

        # Get or create product in DB
        product = upsert_product_stock(brand, product_name)
        current_stock = product["current_stock"]
        full_stock = product["full_stock"]
        reorder_threshold = product["reorder_threshold"]

        remaining = max(0, current_stock - units_sold)

        # Persist updated stock back to DB
        update_current_stock_after_sales(product["id"], remaining)

        result.append({
            "brand": brand,
            "product_name": product_name,
            "units_sold": units_sold,
            "remaining": remaining,
            "full_stock": full_stock,
            "needs_reorder": remaining <= reorder_threshold,
        })
    return result


def build_pos_whatsapp_message(inventory: List[Dict[str, Any]], date: str) -> str:
    items_to_reorder = [i for i in inventory if i["needs_reorder"]]
    is_urgent = len(items_to_reorder) > 1

    brands: Dict[str, list] = {}
    for item in inventory:
        brands.setdefault(item["brand"], []).append(item)

    lines = [
        "*🍦 Daily Sales Report*",
        f"Date: {date}",
        "──────────────────────────",
    ]

    for brand, items in brands.items():
        lines.append(f"\n*{brand.upper()}*")
        for item in items:
            icon = "🔴" if item["needs_reorder"] else "🟢"
            suffix = " ← REORDER" if item["needs_reorder"] else ""
            lines.append(
                f"{icon} {item['product_name']} — Sold: {item['units_sold']} | Left: {item['remaining']}/{item['full_stock']}{suffix}"
            )

    lines.append("\n──────────────────────────")

    if is_urgent:
        reorder_names = ", ".join(i["product_name"] for i in items_to_reorder)
        lines.append(f"🚨 *CRITICAL — {len(items_to_reorder)} items need restocking!*")
        lines.append(f"Reorder: {reorder_names}")
    elif items_to_reorder:
        lines.append(f"⚠️ *Reorder: {items_to_reorder[0]['product_name']}*")
    else:
        lines.append("✅ *All items well stocked*")

    total_sold = sum(i["units_sold"] for i in inventory)
    lines.append(f"\nTotal sold today: {total_sold} units")
    lines.append("──────────────────────────")

    return "\n".join(lines)
