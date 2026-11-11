# How to Run Findable on Windows

> **"Toffee isn't a colour. ΔE 1.8 is."**  
> Complete step-by-step instructions to set up, configure, and run Findable locally on Windows.

---

## Prerequisites
- **Python 3.11+** installed (verify with `python --version`)
- **Git** (optional, for version control)
- **PowerShell** or **Command Prompt**

---

## Option A: One-Click Launch (Recommended)
You can launch Findable with a single command or by double-clicking:

### In Command Prompt / PowerShell:
```bat
run_findable.bat
```
*(This script automatically checks for Python, creates a virtual environment `.venv`, installs requirements, and launches the FastAPI server at `http://localhost:8000`).*

---

## Option B: Manual Step-by-Step Setup

### Step 1: Open Terminal in Project Directory
Navigate to your project root folder:
```powershell
cd "c:\Users\HP\Desktop\ml comp"
```

---

### Step 2: Create and Activate a Python Virtual Environment
```powershell
# 1. Create a virtual environment named .venv
python -m venv .venv

# 2. Activate the virtual environment
# In PowerShell:
.venv\Scripts\Activate.ps1

# (Or in Command Prompt:)
# .venv\Scripts\activate.bat
```

> **Note for PowerShell execution policy:** If PowerShell blocks script activation, run:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

---

### Step 3: Install Required Packages
Install all framework, computer vision, database, and payment libraries:
```powershell
pip install -r requirements.txt
```

---

### Step 4: Environment Configuration (`.env`)
The project comes with a pre-configured `.env` file designed for **100% offline, zero-quota-drain** execution:
- `MOCK_PAYPAL=1`: Simulates orders, captures, and refunds instantly without needing active PayPal credentials or consuming API quota.
- `LLM_API_KEY`: Kept blank by default to automatically activate the offline deterministic fallback, preserving external AI tokens.

#### To connect to real PayPal Sandbox (Optional):
Edit `.env` and set:
```env
PAYPAL_CLIENT_ID=your_sandbox_client_id_here
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret_here
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
MOCK_PAYPAL=0
```

---

### Step 5: Start the Findable Server
Run the FastAPI web application using Uvicorn:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running, open your web browser to:

| View | Browser URL | What to Do |
|---|---|---|
| 🏁 **Judges Walkthrough** | [http://localhost:8000/judges](http://localhost:8000/judges) | 3-minute guided evaluation flow with a one-click "Reset Demo" button |
| 📸 **Seller Studio** | [http://localhost:8000/studio](http://localhost:8000/studio) | Load Priya's photo, draw white-balance and swatch boxes, see raw vs calibrated chips |
| 🤖 **AI Shopping Agent** | [http://localhost:8000/agent](http://localhost:8000/agent) | Chat with the agent, test `REF-7K2Q`, view match cards with $\Delta E$ badges and PayPal checkout |
| 📊 **Seller Dashboard** | [http://localhost:8000/dashboard](http://localhost:8000/dashboard) | View incoming agent orders in AG Grid Community and live PayPal API call logs |
| 🔬 **Measure Current Shade** | [http://localhost:8000/measure](http://localhost:8000/measure) | Generate a new `REF-` code from an existing foundation swatch |
| 📜 **Passport Inspector** | [http://localhost:8000/passport/shd_honey04](http://localhost:8000/passport/shd_honey04) | Inspect canonical JSON, SHA-256 hash, and HMAC-SHA256 signature |
| 🛡️ **Shade Promise Dispute** | [http://localhost:8000/promise/ord_7a9f2b1c](http://localhost:8000/promise/ord_7a9f2b1c) | Test zero-friction optical mismatch evaluation and instant refund |
| 🔌 **MCP Endpoint** | [http://localhost:8000/mcp](http://localhost:8000/mcp) | Streamable HTTP endpoint for external agents & Claude Desktop |

---

### Step 6: Run the Tri-Condition Benchmark (Optional)
To test accuracy across all 3 conditions:
- **Condition A**: Today's LLM heuristic on shade names & raw photos
- **Condition B**: Raw color without lighting correction
- **Condition C**: Findable calibrated CIELAB & CIEDE2000 ($\Delta E$)

```powershell
python bench/run.py
```
This script evaluates 20 reference queries in `bench/queries.json` and updates `bench/results.csv`.

---

### Step 7: Run the Test Suite (Optional)
To verify color science math, cryptographic HMAC signing, and PayPal client mock execution:
```powershell
pytest tests/ -v
```

---

### Step 8: Connecting Claude Desktop via MCP (Optional)
To connect Claude Desktop to your local Findable server, add the following to your configuration file:

- **Path**: `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart Claude Desktop, and you can prompt:
> *"My current foundation is REF-7K2Q. Find me a match in Priya's catalog under $30 with a ΔE under 2.0, explain the match, and give me a checkout link."*

---

## Troubleshooting & FAQ

1. **Port 8000 already in use?**
   Run on a different port:
   ```powershell
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
   ```

2. **How to reset the demo data?**
   Click the **"Reset Demo Data"** button at [http://localhost:8000/judges](http://localhost:8000/judges), or send a POST request:
   ```powershell
   curl -X POST http://localhost:8000/api/demo/reset
   ```

3. **Does running this consume API credits or tokens?**
   No. With `MOCK_PAYPAL=1` and blank `LLM_API_KEY`, Findable operates 100% locally with zero external network or quota consumption.

