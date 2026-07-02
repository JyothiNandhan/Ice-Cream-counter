import sqlite3
import json
from typing import List, Dict, Any, Optional
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "inventory.db")


DEFAULT_PRODUCTS = [
    ("Nestle", "Drumstick 14oz"),
    ("Nestle", "Kit Kat 14oz"),
    ("Nestle", "MINT Oreo"),
    ("Nestle", "Snickers"),
]
DEFAULT_FULL_STOCK = 50
DEFAULT_REORDER_THRESHOLD = 25


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

    try:
        cursor.execute("ALTER TABLE scans ADD COLUMN report_json TEXT")
    except sqlite3.OperationalError:
        pass

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

    try:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN sku_identifier TEXT")
    except sqlite3.OperationalError:
        pass

    # Supervisor auth table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS supervisors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
    """)

    # Live stock levels per product
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        product_name TEXT NOT NULL,
        full_stock INTEGER NOT NULL DEFAULT 50,
        current_stock INTEGER NOT NULL DEFAULT 50,
        reorder_threshold INTEGER NOT NULL DEFAULT 25,
        last_updated TEXT,
        UNIQUE(brand, product_name)
    )
    """)

    # Audit log of all restock actions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restock_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        brand TEXT,
        product_name TEXT,
        units_added INTEGER,
        action TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # Seed default products if table is empty
    cursor.execute("SELECT COUNT(*) FROM product_stock")
    if cursor.fetchone()[0] == 0:
        now = _now()
        for brand, name in DEFAULT_PRODUCTS:
            cursor.execute("""
                INSERT OR IGNORE INTO product_stock
                (brand, product_name, full_stock, current_stock, reorder_threshold, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (brand, name, DEFAULT_FULL_STOCK, DEFAULT_FULL_STOCK, DEFAULT_REORDER_THRESHOLD, now))

    conn.commit()
    conn.close()


def _now() -> str:
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


# ── Supervisor auth ──────────────────────────────────────────────────────────

def get_supervisor(username: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash FROM supervisors WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return {"username": row[0], "password_hash": row[1]} if row else None


def create_supervisor(username: str, password_hash: str) -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO supervisors (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    conn.commit()
    conn.close()


# ── Product stock ────────────────────────────────────────────────────────────

def get_all_stock() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, brand, product_name, full_stock, current_stock, reorder_threshold, last_updated
        FROM product_stock ORDER BY brand, product_name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "brand": r[1], "product_name": r[2],
            "full_stock": r[3], "current_stock": r[4],
            "reorder_threshold": r[5], "last_updated": r[6],
            "needs_reorder": r[4] <= r[5],
        }
        for r in rows
    ]


def get_stock_by_product(brand: str, product_name: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, brand, product_name, full_stock, current_stock, reorder_threshold
        FROM product_stock WHERE brand = ? AND product_name = ?
    """, (brand, product_name))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "brand": row[1], "product_name": row[2],
                "full_stock": row[3], "current_stock": row[4], "reorder_threshold": row[5]}
    return None


def upsert_product_stock(brand: str, product_name: str) -> Dict[str, Any]:
    """Get existing product or create with defaults."""
    existing = get_stock_by_product(brand, product_name)
    if existing:
        return existing
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO product_stock
        (brand, product_name, full_stock, current_stock, reorder_threshold, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (brand, product_name, DEFAULT_FULL_STOCK, DEFAULT_FULL_STOCK, DEFAULT_REORDER_THRESHOLD, _now()))
    conn.commit()
    conn.close()
    return get_stock_by_product(brand, product_name)


def update_current_stock_after_sales(product_id: int, new_stock: int) -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE product_stock SET current_stock = ?, last_updated = ? WHERE id = ?",
        (max(0, new_stock), _now(), product_id),
    )
    conn.commit()
    conn.close()


def restock_product(product_id: int, units_to_add: int) -> Dict[str, Any]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE product_stock
        SET current_stock = MIN(full_stock, current_stock + ?), last_updated = ?
        WHERE id = ?
    """, (units_to_add, _now(), product_id))
    cursor.execute(
        "SELECT id, brand, product_name, full_stock, current_stock, reorder_threshold, last_updated FROM product_stock WHERE id = ?",
        (product_id,)
    )
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return {
        "id": row[0], "brand": row[1], "product_name": row[2],
        "full_stock": row[3], "current_stock": row[4],
        "reorder_threshold": row[5], "last_updated": row[6],
        "needs_reorder": row[4] <= row[5],
    }


def full_restock_all() -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE product_stock SET current_stock = full_stock, last_updated = ?", (_now(),)
    )
    conn.commit()
    conn.close()


# ── Restock log ──────────────────────────────────────────────────────────────

def add_restock_log(
    performed_by: str,
    action: str,
    product_id: Optional[int] = None,
    brand: Optional[str] = None,
    product_name: Optional[str] = None,
    units_added: Optional[int] = None,
) -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO restock_log (product_id, brand, product_name, units_added, action, performed_by, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (product_id, brand, product_name, units_added, action, performed_by, _now()))
    conn.commit()
    conn.close()


def get_restock_log(limit: int = 50) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, brand, product_name, units_added, action, performed_by, timestamp
        FROM restock_log ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "brand": r[1], "product_name": r[2], "units_added": r[3],
         "action": r[4], "performed_by": r[5], "timestamp": r[6]}
        for r in rows
    ]


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
