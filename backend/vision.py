import io
import json
import time
import logging
import base64
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

from openai import OpenAI
from models import InventoryItem
from config import NVIDIA_VISION_API_KEY, NVIDIA_BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NVIDIA NIM client — nemotron-nano-12b-v2-vl for vision
vision_client = OpenAI(
    api_key=NVIDIA_VISION_API_KEY,
    base_url=NVIDIA_BASE_URL,
)

VISION_PROMPT = """You are an expert retail inventory analyst inspecting a freezer shelf photo.

Look at every shelf in this photo very carefully.

For EACH distinct ice cream product you can see, assess its stock level and identify the brand and flavor.

Return a JSON array where each element has:
- "brand": exact brand name on the label (e.g. "Nestle", "Haagen-Dazs", "Oreo", "Drumstick", "Toll House", "KitKat")
- "product_name": specific flavor or variant (e.g. "Vanilla", "Oreo Mint", "Cookie Dough")
- "sku_identifier": barcode or SKU if visible, otherwise null
- "fill_level": how full this product's shelf space looks — MUST be exactly one of: "FULL", "MEDIUM", "LOW", "EMPTY"
  - FULL: shelf slot looks ≥75% stocked (well-stocked, minimal gaps)
  - MEDIUM: shelf slot is roughly 40–74% stocked (noticeable gaps but not sparse)
  - LOW: shelf slot is roughly 10–39% stocked (very few items, mostly empty)
  - EMPTY: shelf slot is <10% stocked or completely bare
- "units_currently_visible": rough visual estimate of how many tubs/packages you see (this is approximate, not a precise count)
- "shelf_capacity_estimate": rough estimate of how many units fill this slot when completely full
- "confidence": "high" if label clearly readable, "medium" if partially visible, "low" if guessed

Rules:
- fill_level is the PRIMARY and most important field. Judge honestly how full each shelf looks.
- units_currently_visible is a rough estimate only — exact counts from photos are unreliable.
- Group same products together.
- If a label is unreadable, use "Unknown Brand" and describe packaging color.
- Return ONLY raw JSON array. No markdown fences. No explanation.

[
  {{
    "brand": "Nestle",
    "product_name": "Drumstick Vanilla",
    "sku_identifier": null,
    "fill_level": "LOW",
    "units_currently_visible": 4,
    "shelf_capacity_estimate": 8,
    "confidence": "high"
  }}
]"""


def compress_image(image_bytes: bytes, max_width: int = 1024, quality: int = 85) -> str:
    """Resize and compress image to reduce API payload size."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    compressed_bytes = buf.getvalue()
    original_kb = len(image_bytes) / 1024
    compressed_kb = len(compressed_bytes) / 1024
    logger.info(f"[Vision] Compressed: {original_kb:.0f}KB → {compressed_kb:.0f}KB")
    return base64.b64encode(compressed_bytes).decode()


def analyze_single_image(image_bytes: bytes, image_index: int) -> list[dict]:
    """Send one image to the vision model and return parsed results."""
    compressed_b64 = compress_image(image_bytes)

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{compressed_b64}"}}
        ]
    }]

    max_retries = 2
    raw_content = ""

    for attempt in range(max_retries):
        try:
            logger.info(f"[Vision] Image {image_index + 1}: attempt {attempt + 1}/{max_retries}")
            response = vision_client.chat.completions.create(
                model="nvidia/nemotron-nano-12b-v2-vl",
                messages=messages,
                temperature=0.0,
                max_tokens=2048,
            )
            raw_content = response.choices[0].message.content.strip()

            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()

            parsed = json.loads(raw_content)
            # Compute fill_level from ratio as fallback if model omitted it
            for p in parsed:
                if not p.get("fill_level"):
                    units = p.get("units_currently_visible", 0)
                    cap = p.get("shelf_capacity_estimate", 1) or 1
                    ratio = units / cap
                    p["fill_level"] = "FULL" if ratio >= 0.75 else ("MEDIUM" if ratio >= 0.40 else ("LOW" if ratio >= 0.10 else "EMPTY"))
            logger.info(f"[Vision] Image {image_index + 1}: found {len(parsed)} products")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"[Vision] Image {image_index + 1}: JSON parse error: {e}")
            if attempt < max_retries - 1:
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({
                    "role": "user",
                    "content": "Return ONLY the raw JSON array. No markdown fences. No explanation."
                })
                time.sleep(1)
            else:
                logger.warning(f"[Vision] Image {image_index + 1}: returning empty result after parse failure")
                return []

        except Exception as e:
            logger.error(f"[Vision] Image {image_index + 1}: API error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                logger.warning(f"[Vision] Image {image_index + 1}: skipping after API failure")
                return []


def merge_results(all_results: list[list[dict]]) -> list[dict]:
    """
    Merge results from multiple parallel image analyses.
    Groups by (brand, product_name) and takes the MAX unit count
    (same product seen from two angles → take the larger count, not the sum).
    """
    merged: dict[tuple, dict] = {}

    for image_results in all_results:
        for item in image_results:
            key = (
                item.get("brand", "Unknown").strip().lower(),
                item.get("product_name", "").strip().lower()
            )
            if key not in merged:
                merged[key] = item.copy()
            else:
                existing = merged[key]
                # Take the MAX count (avoids double-counting same shelf from two angles)
                existing["units_currently_visible"] = max(
                    existing.get("units_currently_visible", 0),
                    item.get("units_currently_visible", 0)
                )
                # Take the larger shelf capacity estimate
                existing["shelf_capacity_estimate"] = max(
                    existing.get("shelf_capacity_estimate", 0),
                    item.get("shelf_capacity_estimate", 0)
                )
                # Take the higher confidence
                conf_rank = {"high": 2, "medium": 1, "low": 0}
                if conf_rank.get(item.get("confidence", "low"), 0) > conf_rank.get(existing.get("confidence", "low"), 0):
                    existing["confidence"] = item["confidence"]
                # Take the most optimistic fill_level (best-angle view wins)
                fill_rank = {"EMPTY": 0, "LOW": 1, "MEDIUM": 2, "FULL": 3}
                if fill_rank.get(item.get("fill_level", "LOW"), 1) > fill_rank.get(existing.get("fill_level", "LOW"), 1):
                    existing["fill_level"] = item["fill_level"]

    result = list(merged.values())
    logger.info(f"[Vision] Merged {sum(len(r) for r in all_results)} detections → {len(result)} unique products")
    return result


def extract_inventory(images_bytes: list[bytes]) -> List[InventoryItem]:
    n = len(images_bytes)
    logger.info(f"[Vision] Parallel analyzing {n} image(s) with nvidia/nemotron-nano-12b-v2-vl...")

    # Fire all image API calls in parallel using a thread pool
    all_results: list[list[dict]] = [None] * n
    with ThreadPoolExecutor(max_workers=n) as executor:
        future_to_idx = {
            executor.submit(analyze_single_image, img_bytes, idx): idx
            for idx, img_bytes in enumerate(images_bytes)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                all_results[idx] = future.result()
            except Exception as e:
                logger.error(f"[Vision] Image {idx + 1} future error: {e}")
                all_results[idx] = []

    # Merge all parallel results, deduplicating by brand+product
    merged = merge_results(all_results)

    if not merged:
        raise Exception("Vision model could not identify any products from the provided images.")

    items = [InventoryItem(**item) for item in merged]
    logger.info(f"[DONE] Inventory extraction complete — {len(items)} products")
    return items
