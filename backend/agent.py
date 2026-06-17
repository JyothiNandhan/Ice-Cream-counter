import json
import time
import random
import logging
from openai import OpenAI
from typing import Dict, Any, List, Optional

from config import NVIDIA_TEXT_API_KEY, NVIDIA_BASE_URL
from models import ReportItem

logger = logging.getLogger(__name__)

text_client = OpenAI(
    api_key=NVIDIA_TEXT_API_KEY,
    base_url=NVIDIA_BASE_URL,
)

AGENT_SYSTEM_PROMPT = """You are a precise inventory management agent for a retail ice cream operation.
You produce clean, accurate reports for managers. You never fabricate or change numbers.
You always return valid raw JSON only — no markdown, no backticks, no explanation."""

AGENT_USER_PROMPT = """You have two inventory scans to compare:

CURRENT SCAN (taken at {current_datetime}):
{current_scan_json}

PREVIOUS SCAN (taken at {previous_scan_timestamp}):
{previous_scan_json}

Your tasks:

1. For each product in the current scan calculate:
   units_sold = previous_units_currently_visible - current_units_currently_visible
   - If result is negative: restocking occurred, set units_sold = 0
   - If brand not in previous scan: set units_sold = null
   - If no previous scan exists: set all units_sold = null

2. Assign restock_urgency based on fill_level (fill_level is the reliable metric — unit counts are estimates):
   "CRITICAL" if fill_level is "EMPTY" or "LOW"
   "MEDIUM"   if fill_level is "MEDIUM"
   "LOW"      if fill_level is "FULL"

3. Compose a WhatsApp message in this format:

*Freezer Inventory Report*
Date: {current_datetime}
──────────────────────────

*HAAGEN-DAZS*
🔴 Chocolate — EMPTY (~1 unit) ← CRITICAL
🟢 Vanilla — FULL (~8 units)

*NESTLE*
🔴 Drumstick Vanilla — LOW (~4 units) ← CRITICAL
🟢 Toll House Cookie Dough — FULL (~6 units)
🟡 Oreo Mint — MEDIUM (~3 units)

──────────────────────────
*Scan #{scan_id}*
──────────────────────────
⚠️ Unit counts are estimates (photo-based). Fill level is reliable.
🔴 CRITICAL = restock immediately (EMPTY or LOW)
🟡 MEDIUM = restock soon
🟢 LOW = stocked well (FULL)

Rules for the message:
- Show fill_level (FULL/MEDIUM/LOW/EMPTY) as the primary status for each product.
- Show unit count in parentheses preceded by ~ to signal it is an estimate.
- Group products under their brand header.
- Use 🔴 for CRITICAL, 🟡 for MEDIUM, 🟢 for LOW.
- Keep it under 300 words.

Return ONLY this raw JSON object:
{{
  "structured_report": [
    {{
      "brand": "string",
      "product_name": "string",
      "sku_identifier": null,
      "fill_level": "FULL",
      "units_currently_visible": 0,
      "shelf_capacity_estimate": 0,
      "confidence": "high",
      "units_sold": 0,
      "restock_urgency": "CRITICAL"
    }}
  ],
  "whatsapp_message": "full formatted message string here"
}}"""


def extract_json(text: str) -> str:
    """Strip markdown fences and any prose before the opening brace."""
    text = text.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            break
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    brace = text.find("{")
    if brace > 0:
        text = text[brace:]
    return text


def compute_fill_level(units: int, capacity: int) -> str:
    capacity = capacity or 1
    ratio = units / capacity
    if ratio >= 0.75:
        return "FULL"
    elif ratio >= 0.40:
        return "MEDIUM"
    elif ratio >= 0.10:
        return "LOW"
    return "EMPTY"


def urgency_from_fill(fill_level: str) -> str:
    return "LOW" if fill_level == "FULL" else ("MEDIUM" if fill_level == "MEDIUM" else "CRITICAL")


def fallback_urgency(report: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fill in fill_level and restock_urgency for any item the model left blank."""
    for item in report:
        if not item.get("fill_level"):
            item["fill_level"] = compute_fill_level(
                item.get("units_currently_visible", 0),
                item.get("shelf_capacity_estimate", 1),
            )
        if not item.get("restock_urgency"):
            item["restock_urgency"] = urgency_from_fill(item["fill_level"])
    return report


def build_fallback_report(
    current_items: List[Dict[str, Any]],
    scan_id: int,
    timestamp: str,
) -> Dict[str, Any]:
    """Build a minimal report purely from vision data when the LLM is unavailable."""
    report = []
    for item in current_items:
        fill = item.get("fill_level") or compute_fill_level(
            item.get("units_currently_visible", 0),
            item.get("shelf_capacity_estimate", 1),
        )
        urgency = urgency_from_fill(fill)
        report.append({**item, "fill_level": fill, "units_sold": None, "restock_urgency": urgency})

    brands: Dict[str, list] = {}
    for item in report:
        brands.setdefault(item["brand"], []).append(item)

    lines = [
        "*Freezer Inventory Report*",
        f"Date: {timestamp}",
        "──────────────────────────",
    ]
    for brand, items in brands.items():
        lines.append(f"\n*{brand.upper()}*")
        for i in items:
            icon = {"CRITICAL": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(i["restock_urgency"], "🟢")
            fill = i.get("fill_level", "")
            count = i["units_currently_visible"]
            suffix = " ← CRITICAL" if i["restock_urgency"] == "CRITICAL" else ""
            lines.append(f"{icon} {i['product_name']} — {fill} (~{count} units){suffix}")

    lines += [
        "\n──────────────────────────",
        f"*Scan #{scan_id}*",
        "──────────────────────────",
        "⚠️ Unit counts are estimates (photo-based). Fill level is reliable.",
        "🔴 CRITICAL = restock immediately (EMPTY or LOW)",
        "🟡 MEDIUM = restock soon",
        "🟢 LOW = stocked well (FULL)",
    ]

    return {"structured_report": report, "whatsapp_message": "\n".join(lines)}


def generate_report(
    current_scan: Dict[str, Any],
    previous_scan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current_datetime = current_scan.get("timestamp", "")
    current_items = current_scan.get("items", [])
    scan_id = current_scan.get("id", 1)
    total_tubs = sum(item.get("units_currently_visible", 0) for item in current_items)

    previous_scan_timestamp = (
        previous_scan.get("timestamp", "None") if previous_scan else "None (first scan)"
    )
    previous_scan_json = (
        json.dumps(previous_scan.get("raw_json", []), indent=2) if previous_scan else "[]"
    )

    prompt = (
        AGENT_USER_PROMPT
        .replace("{current_datetime}", current_datetime)
        .replace("{current_scan_json}", json.dumps(current_items, indent=2))
        .replace("{previous_scan_timestamp}", previous_scan_timestamp)
        .replace("{previous_scan_json}", previous_scan_json)
        .replace("{total}", str(total_tubs))
        .replace("{scan_id}", str(scan_id))
    )

    max_retries = 3
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        if attempt > 0:
            delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.info(f"[Agent] Retry {attempt}/{max_retries - 1} in {delay:.1f}s")
            time.sleep(delay)

        try:
            logger.info(f"[Agent] Calling Qwen3.5-397B (attempt {attempt + 1}). Total tubs: {total_tubs}")

            response = text_client.chat.completions.create(
                model="qwen/qwen3.5-397b-a17b",
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=4096,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )

            raw_content = response.choices[0].message.content
            logger.info(f"[Agent] Raw response snippet: {raw_content[:200]}")

            result = json.loads(extract_json(raw_content))
            result["structured_report"] = fallback_urgency(result.get("structured_report", []))
            logger.info(f"[Agent] Report generated successfully on attempt {attempt + 1}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"[Agent] JSON parse error on attempt {attempt + 1}: {e}")
            last_error = e
        except Exception as e:
            logger.error(f"[Agent] API error on attempt {attempt + 1}: {e}")
            last_error = e

    logger.warning(f"[Agent] All {max_retries} retries exhausted (last: {last_error}). Using fallback report.")
    return build_fallback_report(current_items, scan_id, current_datetime)
