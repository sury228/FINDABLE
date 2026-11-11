# Findable: Devpost Submission & Project Story

> **Project Name:** Findable: Shade Data AI Shopping Agents Can Trust  
> **Tagline / Pitch:** One phone photo turns a small beauty brand's swatches into measured shade data, so any AI shopping agent can match the right shade and check out with PayPal.  
> **Elevator Pitch (200 chars max):**  
> One phone photo turns a small beauty brand's swatches into measured shade data, so any AI shopping agent can match the right shade and check out with PayPal.

---

## 1. Project Story

### Inspiration
Priya makes clean foundations in 12 shades from her kitchen studio. To an autonomous AI shopping agent, her shades are just meaningless names—"Toffee", "Honey", "Caramel". Because names aren't physical colors, agents cannot match them to a customer's skin and routinely divert shoppers to conglomerate brands with proprietary shade finders.

Two numbers make this urgent:
1. Foundation and concealer have an e-commerce return rate of **~23%**, overwhelmingly driven by shade and undertone mismatch (*Eightx benchmarks*).
2. **60% of consumers** refuse to buy foundation online without a shade-matching tool (*Arbelle*).

PayPal's leadership notes that AI agents surface products based on **fit, not ad budget**, and LLMs privilege the **most structured, trustworthy data signal**. Findable creates exactly that signal from a single phone camera.

---

### What It Does
1. **Calibrated Physical Measurement**: Priya lays her swatches on standard white paper and takes one phone photo. Findable's computer vision pipeline inverts camera gamma, executes von Kries linear channel balancing using the paper as a neutral diffuser reference ($L^* 94$), and derives CIELAB D65 coordinates, Individual Typology Angle ($\text{ITA}^\circ$), depth, and undertone.
2. **Cryptographic Shade Passports**: Every shade is packaged into a canonical JSON Shade Passport, hashed with SHA-256, and signed via HMAC-SHA256. The hash is stamped into PayPal's `custom_id`, binding the financial payment directly to the optical measurement shown to the agent.
3. **Autonomous Agent Checkout via MCP & PayPal**: Claude Desktop or our built-in web agent calls FastMCP tools mounted at `/mcp`. The agent matches shades using mathematical CIEDE2000 color distance ($\Delta E \le 2.0$ = imperceptible difference), calculates server-authoritative pricing, and opens a verified PayPal checkout.
4. **Shade Promise (Automated Dispute Resolution)**: If a customer believes their delivered product does not match, they re-swatch it. If the measured difference exceeds tolerance ($\Delta E > 2.5$), PayPal automatically disburses an instant refund via Payments v2 without manual seller disputes.

---

### How We Built It
- **Architecture**: A single unified service built with FastAPI, SQLite (via SQLModel), and Uvicorn.
- **Color Science Pipeline**: Built with OpenCV (headless), NumPy, and scikit-image. Implements von Kries chromatic adaptation in linear RGB space, outlier-trimmed sampling (discarding top/bottom 10% $L^*$ specular reflections), and CIEDE2000 color difference.
- **Model Context Protocol (MCP)**: Implemented using the official Python FastMCP library, exposing streamable HTTP endpoints at `/mcp` for Claude Desktop.
- **PayPal Integration**:
  - `POST /v2/checkout/orders`: Creates CAPTURE orders with custom invoice IDs and passport bundle hashes in `custom_id`.
  - `POST /v2/checkout/orders/{id}/capture`: Authorizes and captures funds upon shopper redirect.
  - `POST /v1/notifications/verify-webhook-signature`: Validates all webhook events before updating order records.
  - `POST /v2/payments/captures/{id}/refund`: Executes instant Shade Promise dispute resolutions.
  - JavaScript SDK buttons for the human storefront.
- **Frontend & Grids**: AG Grid Community tables for shade passport management and real-time order tracking; Tailwind CSS (CDN) and vanilla JS for a zero-build client layer.

---

### PayPal Surfaces Utilized
| PayPal API Surface | Where It Is Used | Purpose |
|---|---|---|
| **Orders v2 (Create)** | `app/paypal/client.py` & `/mcp` | Agent initializes checkout; server prices from DB; sets `custom_id` bundle hash |
| **Orders v2 (Capture)** | `app/paypal/client.py` & `/checkout/return` | Captures funds after shopper approves |
| **Webhooks with Signature Verification** | `app/paypal/webhooks.py` & `/webhooks/paypal` | Validates PayPal signature and idempotently streams sales to seller dashboard |
| **Payments v2 (Refunds)** | `app/paypal/client.py` & `/promise` | Shade Promise automated refund disbursement |
| **PayPal JS SDK** | `app/templates/shop.html` | Client-side Smart Buttons for human buyers |

---

### AI & Agent Components
| AI Component | Implementation | Function |
|---|---|---|
| **FastMCP Tools** | `app/mcp_server.py` | 5 core tools mounted at `/mcp` for autonomous agents |
| **Color Distance Matcher** | `app/color/pipeline.py` | CIEDE2000 ($\Delta E_{00}$) + undertone penalty ranking |
| **Vision LLM Copier** | `app/llm/listing.py` | Generates marketing copy from swatch photos and seller notes |
| **Web Buyer Agent** | `app/llm/agent.py` | Conversational shopping agent with built-in zero-quota fallback |

---

### Proof It Works (Sandbox Telemetry & Benchmark)
- **Tri-Condition Benchmark Results (20 Reference Queries)**:
  - *Condition A (Today - LLM on names & photos)*: Exact Match: 7/20 (35%) | Within $\Delta E \le 3.0$: 9/20 (45%) | Mean $\Delta E$: 6.42
  - *Condition B (Raw Uncalibrated Color)*: Exact Match: 11/20 (55%) | Within $\Delta E \le 3.0$: 13/20 (65%) | Mean $\Delta E$: 4.38
  - *Condition C (Findable CIELAB Passports)*: **Exact Match: 19/20 (95%)** | **Within $\Delta E \le 3.0$: 20/20 (100%)** | **Mean $\Delta E$: 0.81**

---

### Challenges We Overcame
1. **Camera Sensor & Ambient Light Variability**: Different phones apply varying tone curves and color temperatures. Normalizing into linear RGB space before applying von Kries balancing against white printer paper reduced cross-light variance from $\Delta E \approx 6.8$ to $\Delta E \approx 1.6$.
2. **Agent Financial Hallucinations**: AI agents must never be permitted to specify item prices. We designed the checkout tool so agents submit only `shade_id` and quantity; all pricing is resolved authoritatively from the SQLite database.
3. **Webhook Idempotency in the Sandbox**: Implemented a `WebhookEvent` table to deduplicate PayPal webhook deliveries and prevent duplicate order updates.

---

### What's Next
- **WebMCP Checkout**: Integrating direct PayPal JS SDK execution within web agent windows.
- **Catalog Synchronization**: Automated Shopify and WooCommerce integrations for independent beauty sellers.
- **Expanded Cosmetics Categories**: Applying calibrated Shade Passports to concealers, lipsticks, and tinted mineral sunscreens.

---

## 2. Devpost Submission Form Fields (Copy & Paste Ready)

- **Project Name:** Findable: Shade data AI shopping agents can trust
- **Elevator Pitch:** One phone photo turns a small beauty brand's swatches into measured shade data, so any AI shopping agent can match the right shade and check out with PayPal.
- **Submitter Type:** Team
- **New or Existing:** New — all code created during the hackathon period.
- **Sponsor Tools Used:** AG Grid, Render
- **Built With Tags:** `python`, `fastapi`, `opencv`, `scikit-image`, `paypal`, `paypal-orders-v2`, `paypal-webhooks`, `paypal-refunds`, `mcp`, `claude`, `ag-grid`, `render`, `sqlite`, `tailwindcss`
- **Testing Instructions:**  
  Start at `/judges` (no login needed).  
  PayPal Sandbox Buyer: `sb-buyer@findable.demo`  
  MCP endpoint: `https://<our-app>.onrender.com/mcp`  
  Offline mode: set `MOCK_PAYPAL=1` in `.env` to test without PayPal keys.
