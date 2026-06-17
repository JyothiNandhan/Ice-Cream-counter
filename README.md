# Ice Cream Freezer Inventory Management System

A local-first, mobile-friendly full-stack web application for ice cream freezer inventory management. Staff photograph the freezer from their phone, the system uses AI vision to count every product on every shelf, compares with the previous scan to calculate units sold and restock urgency, and dispatches a formatted WhatsApp report to managers — all in one tap.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLite |
| Vision AI | NVIDIA NIM — `nvidia/nemotron-nano-12b-v2-vl` |
| Report AI | NVIDIA NIM — `qwen/qwen3.5-397b-a17b` |
| WhatsApp | CallMeBot free API |
| Frontend | React 18 · Vite 5 (mobile-first, served on LAN) |

## Prerequisites

- Python 3.10+
- Node.js 18+
- NVIDIA NIM API keys (vision + text) — [platform.nvidia.com](https://platform.nvidia.com)
- CallMeBot activated on each recipient number (see below)

## CallMeBot Activation

Every recipient must activate CallMeBot once before they can receive reports:

1. Save `+34 644 60 49 79` as a contact on WhatsApp.
2. Send `I allow callmebot to send me messages` to that contact on WhatsApp.
3. You will receive a personal API key via WhatsApp within seconds.
4. Add the phone number and API key to `.env`.

## Environment Variables

Copy `.env` into `backend/` and fill in all values:

```
NVIDIA_VISION_API_KEY=nvapi-...
NVIDIA_TEXT_API_KEY=nvapi-...
CALLMEBOT_NUMBERS=+1234567890,+0987654321
CALLMEBOT_API_KEYS=abc123,xyz789
```

`CALLMEBOT_NUMBERS` and `CALLMEBOT_API_KEYS` are comma-separated lists of equal length.

## Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env .env
python main.py                  # starts on http://0.0.0.0:8000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev                     # starts on http://0.0.0.0:5173
```

## Accessing on a Phone

1. Find your laptop's local IP:
   - Mac/Linux: `ifconfig | grep "inet "`
   - Windows: `ipconfig`
2. Make sure phone and laptop are on the **same WiFi network**.
3. Open `http://YOUR_LAPTOP_IP:5173` on the phone browser.

## How to Use

1. Tap **📷 Take Photo** to capture the freezer (or **🖼️ Gallery** to pick existing photos).
2. Add photos from multiple angles — the system deduplicates overlapping views automatically.
3. Tap **Analyze Freezer 🔍** and wait ~10–20 seconds.
4. Review the report: each product shows current units, capacity, units sold since last scan, and a restock urgency badge (🔴 CRITICAL / 🟡 MEDIUM / 🟢 LOW).
5. The WhatsApp report is sent automatically to all configured numbers.
6. Tap **📋 View Scan History** to browse past scans and track trends.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/analyze` | Upload images, run full pipeline, return report |
| `GET` | `/history?limit=20` | List past scans with summary stats |
| `GET` | `/scan/{id}` | Full detail for a specific scan |
| `GET` | `/health` | Liveness check |

## How the Pipeline Works

```
Photos → Vision model (parallel per image)
       → Merge results (MAX count per product across angles)
       → Save raw scan to SQLite
       → Compare with previous scan
       → LLM agent: compute units_sold, urgency, WhatsApp message
       → Save enriched report back to SQLite
       → Send WhatsApp to all configured numbers
       → Return AnalyzeResponse to frontend
```

**Deduplication:** When the same product appears in multiple photos (different angles of the same shelf), the system takes the maximum unit count rather than summing — preventing double-counting.

**Agent resilience:** The LLM call retries up to 3 times with exponential backoff. If all retries fail, a local fallback computes urgency from the vision data so the app always returns a usable result.

## Troubleshooting

- **Camera not opening on phone:** Mobile browsers restrict camera access to HTTPS or `localhost`. On a LAN IP over plain HTTP, use Safari (iOS) or try enabling the Chrome flag `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
- **WhatsApp not sending:** Confirm the CallMeBot API key matches the exact phone number in `.env`, and that the recipient completed the activation step.
- **NVIDIA API errors:** Check that both `NVIDIA_VISION_API_KEY` and `NVIDIA_TEXT_API_KEY` are set and have sufficient credits.
- **Can't reach server from phone:** Verify both devices are on the same WiFi, and check your laptop firewall allows inbound traffic on ports `5173` and `8000`.
