# Here is the complete step-by-step guide to run Findable on your Windows machine:

### Step 1: Open Terminal in the Project Directory
Ensure you are in `c:\Users\HP\Desktop\ml comp` in PowerShell or Command Prompt.

---

### Step 2: Create & Activate a Virtual Environment
```powershell
# Create a virtual environment named .venv
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate
```

---

### Step 3: Install Dependencies
Install all required packages from `requirements.txt`:
```powershell
pip install -r requirements.txt
```

---

### Step 4: Verify the Configuration (`.env`)
By default, `.env` is pre-configured with:
- `MOCK_PAYPAL=1` (allows 100% offline checkout, approval, and capture simulation without real PayPal credentials or spending API quota).
- Offline AI fallback (lets you chat and match shades without external API tokens).

> If you want to use real **PayPal Sandbox** credentials later, simply update `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` in `.env` and set `MOCK_PAYPAL=0`.

---

### Step 5: Start the Web Application
Run the FastAPI application with Uvicorn:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running, open your web browser to any of these URLs:
| Page | URL | Description |
|---|---|---|
| **Judges Guide** | http://localhost:8000/judges | 3-minute guided evaluation flow with demo reset |
| **Seller Studio** | http://localhost:8000/studio | Upload swatch photo, draw canvas boxes, calibrate lighting |
| **AI Shopping Agent** | http://localhost:8000/agent | Chat with agent, match skin tones, initiate PayPal checkout |
| **Seller Dashboard** | http://localhost:8000/dashboard | AG Grid orders table and live PayPal API call telemetry |
| **Measure Shade** | http://localhost:8000/measure | Generate a `REF-` code from an existing foundation swatch |
| **MCP Stream Endpoint** | http://localhost:8000/mcp | Streamable HTTP endpoint for Claude Desktop |

---

### Step 6: Run the Benchmark Script (Optional)
To test accuracy across all 3 conditions (Heuristic, Raw Color, and Findable CIELAB ΔE):
```powershell
python bench/run.py
```
This evaluates all 20 reference queries in `bench/queries.json` and outputs results to `bench/results.csv`.

---

### Step 7: Run Unit Tests (Optional)
To verify color science maths, cryptographic Shade Passport HMAC signing, and PayPal client logic:
```powershell
pytest tests/ -v
```

---

### Step 8: Connecting Claude Desktop to Findable MCP (Optional)
Add this to your Claude Desktop config file (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "findable": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```
Restart Claude Desktop and ask:
> *"My current foundation is REF-7K2Q. Find me a match in Priya's catalog under $30 with a ΔE under 2.0."*

