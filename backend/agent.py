import json
import logging
from openai import OpenAI
from typing import Dict, Any, List

from config import NVIDIA_TEXT_API_KEY, NVIDIA_BASE_URL
from models import ReportItem

logger = logging.getLogger(__name__)

# NVIDIA NIM client — Qwen3.5-397B for report writing
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

2. Assign restock_urgency:
   "CRITICAL" if units_currently_visible < 20% of shelf_capacity_estimate
   "MEDIUM"   if units_currently_visible is 20%–60% of shelf_capacity_estimate
   "LOW"      if units_currently_visible > 60% of shelf_capacity_estimate

3. Compose a WhatsApp message in this format:

*Freezer Inventory Report*
Date: {current_datetime}
──────────────────────────

*HAAGEN-DAZS*
🔴 Chocolate — 1 tub (sold: 3) ← CRITICAL
🟢 Vanilla — 8 tubs (sold: 0)

*NESTLE*
🔴 Drumstick Vanilla — 4 tubs (sold: 2) ← CRITICAL
🟢 Toll House Cookie Dough — 6 tubs (sold: 0)
🟡 Oreo Mint — 3 tubs (sold: 2)

──────────────────────────
*Total tubs in freezer: {total}*
*Scan #{scan_id}*
──────────────────────────
🔴 CRITICAL = restock immediately (< 20% full)
🟡 MEDIUM = restock soon (20–60% full)
🟢 LOW = stocked well (> 60% full)

Rules for the message:
- Use exact counts from the current scan — never round or estimate.
- Group products under their brand header.
- Use 🔴 for CRITICAL, 🟡 for MEDIUM, 🟢 for LOW.
- Say "tub" for 1, "tubs" for plural.
- Keep it under 300 words.

Return ONLY this raw JSON object:
{{
  "structured_report": [
    {{
      "brand": "string",
      "product_name": "string",
      "sku_identifier": null,
      "units_currently_visible": 0,
      "shelf_capacity_estimate": 0,
      "confidence": "high",
      "units_sold": 0,
      "restock_urgency": "CRITICAL"
    }}
  ],
  "whatsapp_message": "full formatted message string here"
}}"""


def fallback_urgency(report: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for item in report:
        if not item.get("restock_urgency"):
            current = item.get("units_currently_visible", 0)
            capacity = item.get("shelf_capacity_estimate", 1) or 1
            ratio = current / capacity
            if ratio < 0.2:
                item["restock_urgency"] = "CRITICAL"
            elif ratio <= 0.6:
                item["restock_urgency"] = "MEDIUM"
            else:
                item["restock_urgency"] = "LOW"
    return report


def generate_report(current_scan: Dict[str, Any], previous_scan: Dict[str, Any] = None) -> Dict[str, Any]:
    current_datetime = current_scan.get("timestamp", "")
    current_items = current_scan.get("items", [])
    total_tubs = sum(item.get("units_currently_visible", 0) for item in current_items)

    current_scan_json = json.dumps(current_items, indent=2)

    if previous_scan:
        previous_scan_timestamp = previous_scan.get("timestamp", "None")
        previous_scan_json = json.dumps(previous_scan.get("raw_json", []), indent=2)
    else:
        previous_scan_timestamp = "None (first scan)"
        previous_scan_json = "[]"

    prompt = AGENT_USER_PROMPT \
        .replace("{current_datetime}", current_datetime) \
        .replace("{current_scan_json}", current_scan_json) \
        .replace("{previous_scan_timestamp}", previous_scan_timestamp) \
        .replace("{previous_scan_json}", previous_scan_json) \
        .replace("{total}", str(total_tubs)) \
        .replace("{scan_id}", str(current_scan.get("id", "1")))

    logger.info(f"[Agent] Calling Qwen3.5-397B for report. Total tubs: {total_tubs}")

    try:
        response = text_client.chat.completions.create(
            model="qwen/qwen3.5-397b-a17b",
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=4096,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        raw_content = response.choices[0].message.content.strip()
        logger.info(f"[Agent] Raw response snippet: {raw_content[:200]}")

        # Strip markdown fences
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        raw_content = raw_content.strip()

        result = json.loads(raw_content)
        result["structured_report"] = fallback_urgency(result.get("structured_report", []))
        logger.info(f"[Agent] Report generated successfully")
        return result

    except Exception as e:
        logger.error(f"[Agent] Failed to generate report: {e}")
        raise Exception(f"Agent report generation failed: {str(e)}")
