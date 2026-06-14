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
        raw_json TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER REFERENCES scans(id),
        brand TEXT,
        product_name TEXT,
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
    
    raw_json = json.dumps(items)
    
    cursor.execute(
        "INSERT INTO scans (timestamp, raw_json) VALUES (?, ?)",
        (timestamp, raw_json)
    )
    scan_id = cursor.lastrowid
    
    for item in items:
        cursor.execute("""
            INSERT INTO inventory_items 
            (scan_id, brand, product_name, units_current, shelf_capacity, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            item.get("brand"),
            item.get("product_name"),
            item.get("units_currently_visible"),
            item.get("shelf_capacity_estimate"),
            item.get("confidence")
        ))
        
    conn.commit()
    conn.close()
    
    return scan_id

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
            "raw_json": json.loads(row[2])
        }
    return None

def get_scan_history(limit: int = 10) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, timestamp, raw_json FROM scans ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "timestamp": row[1],
            "raw_json": json.loads(row[2])
        })
        
    return history
