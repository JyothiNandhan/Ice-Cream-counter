import sqlite3
import json
from typing import List, Dict, Any, Optional
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "inventory.db")


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        freezer_id TEXT DEFAULT 'default',
        raw_json TEXT NOT NULL,
        report_json TEXT
    )
    """)

    # Migrate existing databases that lack the report_json column
    try:
        cursor.execute("ALTER TABLE scans ADD COLUMN report_json TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER REFERENCES scans(id),
        brand TEXT,
        product_name TEXT,
        sku_identifier TEXT,
        units_current INTEGER,
        units_sold INTEGER,
        shelf_capacity INTEGER,
        confidence TEXT,
        restock_urgency TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_scan(items: List[Dict[str, Any]], timestamp: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO scans (timestamp, raw_json) VALUES (?, ?)",
        (timestamp, json.dumps(items))
    )
    scan_id = cursor.lastrowid

    for item in items:
        cursor.execute("""
            INSERT INTO inventory_items
            (scan_id, brand, product_name, sku_identifier, units_current, shelf_capacity, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            item.get("brand"),
            item.get("product_name"),
            item.get("sku_identifier"),
            item.get("units_currently_visible"),
            item.get("shelf_capacity_estimate"),
            item.get("confidence"),
        ))

    conn.commit()
    conn.close()
    return scan_id


def update_scan_report(scan_id: int, report_items: List[Dict[str, Any]]) -> None:
    """Persist the agent-enriched report (urgency + units_sold) back into the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE scans SET report_json = ? WHERE id = ?",
        (json.dumps(report_items), scan_id)
    )

    for item in report_items:
        cursor.execute("""
            UPDATE inventory_items
            SET units_sold = ?, restock_urgency = ?
            WHERE scan_id = ? AND brand = ? AND product_name = ?
        """, (
            item.get("units_sold"),
            item.get("restock_urgency"),
            scan_id,
            item.get("brand"),
            item.get("product_name"),
        ))

    conn.commit()
    conn.close()


def get_previous_scan() -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, timestamp, raw_json FROM scans ORDER BY id DESC LIMIT 1 OFFSET 1"
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "timestamp": row[1],
            "raw_json": json.loads(row[2]),
        }
    return None


def get_scan_history(limit: int = 20) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, timestamp, raw_json, report_json FROM scans ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        raw_items = json.loads(row[2])
        report_items = json.loads(row[3]) if row[3] else []
        history.append({
            "id": row[0],
            "timestamp": row[1],
            "item_count": len(raw_items),
            "total_units": sum(i.get("units_currently_visible", 0) for i in raw_items),
            "critical_count": sum(1 for i in report_items if i.get("restock_urgency") == "CRITICAL"),
            "report": report_items,
        })
    return history


def get_scan_by_id(scan_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, timestamp, raw_json, report_json FROM scans WHERE id = ?",
        (scan_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "timestamp": row[1],
        "items": json.loads(row[2]),
        "report": json.loads(row[3]) if row[3] else [],
    }
