# Ice Cream Freezer Inventory Management System

A local-first, mobile-friendly full-stack web application designed for ice cream inventory management. Users can take multiple photos of a freezer, which are analyzed using advanced multimodal vision models (mistral-small-3.1). The system automatically tracks stock, calculates restock urgency (using llama-3.3-70b-instruct), and dispatches structured inventory reports directly to stakeholders via WhatsApp.

## Prerequisites

- Python 3.10+
- Node.js 18+
- UF GatorLink account with Navigator Toolkit access
- CallMeBot activated on each recipient number

## CallMeBot Activation Steps
For every recipient who should receive inventory reports, they must activate CallMeBot:
1. Save `+34 644 60 49 79` as a contact on their phone.
2. Send the message "I allow callmebot to send me messages" on WhatsApp to that contact.
3. They will receive a personal API key instantly via WhatsApp.
4. Add their phone number and API key to the `.env` file in the corresponding lists.

## Step-by-Step Backend Setup

1. Open your terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Mac/Linux: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. YOLOv11l Setup (automatic):
   - No setup needed
   - On first run yolo11l.pt downloads automatically (~49MB)
   - Requires internet connection on first run only
   - After first run works completely offline
   - Model cached at: ultralytics/assets/yolo11l.pt
6. Configure environment variables:
   ```bash
   cp ../.env .env
   ```
   *(Ensure to fill in your real `UF_API_KEY`, and CallMeBot numbers/keys in the `.env` file.)*
7. Start the backend server:
   ```bash
   python main.py
   ```

## Step-by-Step Frontend Setup

1. Open a new terminal tab and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the necessary packages:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```

## Accessing on Phone Browser

1. Find your laptop's local IP address:
   - Mac/Linux: Run `ifconfig | grep "inet "`
   - Windows: Run `ipconfig`
2. Ensure your phone and laptop are connected to the **same WiFi network**.
3. Open a browser on your phone and go to: `http://YOUR_LAPTOP_IP:5173`

## How to Use the App

1. Open the app on your mobile device as directed above.
2. Tap **"📷 Take Photo"** to capture live photos of the freezer from multiple angles (or use **"🖼️ Gallery"** to select existing photos).
3. Review the thumbnails in the preview grid (you can tap ✕ to remove any bad shots).
4. Tap **"Analyze Freezer 🔍"**.
5. Wait for the analysis to complete. The app will show a breakdown of each identified brand, current units, restocked/sold amounts, and a restock urgency badge.
6. The app will display a confirmation that the WhatsApp inventory report was successfully delivered to the configured numbers.
7. Tap **"Scan Again"** to start a new scan.

## Troubleshooting

- **CORS errors:** Ensure your FastAPI application CORS settings (`main.py`) allow all origins or specifically your laptop IP.
- **Camera not opening:** Mobile browsers restrict camera access to HTTPS or `localhost` / `127.0.0.1`. If accessing via a local IP (`192.168.x.x`), you must use HTTP unless you set up SSL certs. Some browsers may block camera access over plain HTTP on LAN. Use Safari/Chrome setting exceptions or test using ngrok.
- **WhatsApp not sending:** Verify that the CallMeBot API key is perfectly matched to the recipient's phone number in `.env` and that they followed the activation steps.
- **Vision model errors:** Ensure your `UF_API_KEY` is correct in `.env`.
- **Can't reach server on phone:** Verify your laptop and phone are on the exact same WiFi. Check your laptop's firewall to ensure it allows traffic on ports 5173 and 8000. Ensure you're using the correct IP address.
