# Findable: Devpost Submission & Project Story

> **Project Name:** Findable: Shade Data AI Shopping Agents Can Trust  
> **Tagline / Pitch:** One phone photo turns a small beauty brand's swatches into measured shade data, so any AI shopping agent can match the right shade and check out with PayPal.  
> **Elevator Pitch (200 chars max):**  
> One phone photo turns a small beauty brand's swatches into measured shade data, so any AI shopping agent can match the right shade and check out with PayPal.

---

## 1. Project Story

### Inspiration
Priya makes clean foundations in 12 shades from her studio. To an AI shopping agent, her shades are just meaningless names—"Toffee", "Honey", "Caramel". Because names aren't physical colors, agents cannot match them to a customer's skin and routinely divert shoppers to conglomerate brands with proprietary shade finders.

Two numbers make this urgent:
1. Retail industry benchmarks show apparel and beauty return rates hover around 20–30%, with e-commerce averages at ~24.4% per National Retail Federation 2023 reports, overwhelmingly driven by shade and undertone mismatch.
2. **60% of consumers** hesitate to buy foundation online without an objective shade validation tool (*Arbelle*).

PayPal's leadership notes that AI agents surface products based on **fit, not ad budget**, and LLMs privilege the **most structured, trustworthy data signal**. Findable creates exactly that signal from a single phone camera.

---

### What It Does
1. **Calibrated Physical Measurement**: Priya lays her swatches on standard white paper and takes one phone photo. Findable's color science pipeline inverts camera gamma, executes von Kries linear channel balancing using the paper as a neutral diffuser reference ($L^* 94$), and derives CIELAB D65 coordinates, Individual Typology Angle ($\text{ITA}^\circ$), depth, and undertone using NumPy, Pillow, and scikit-image.
2. **Cryptographic Shade Passports**: Every shade is packaged into a canonical JSON Shade Passport, hashed with SHA-256, and signed via HMAC-SHA256 (tamper-evident, signed by Findable). The hash is stamped into PayPal's `custom_id`, binding the financial payment directly to the optical measurement shown to the agent.
3. **Agent Matching & PayPal Checkout**: Claude Desktop (via MCP streamable HTTP at `/mcp`) or our built-in web agent matches shades using mathematical CIEDE2000 color distance ($\Delta E$). The agent prepares the order with server-authoritative pricing; the shopper approves in PayPal Sandbox.

---

### How We Built It
- **Architecture**: A single unified service built with FastAPI, SQLite (via SQLModel), and Uvicorn.
- **Color Science Pipeline**: Built with NumPy, Pillow, and scikit-image. Implements von Kries chromatic adaptation in linear RGB space, outlier-trimmed sampling (discarding top/bottom 10% $L^*$ specular reflections), and CIEDE2000 color difference.
- **Model Context Protocol (MCP)**: Implemented using the Python MCP server library, exposing streamable HTTP endpoints at `/mcp` and stdio transport for Claude Desktop.
- **AI Agent with Tool Calling**: Built on Groq `llama-3.3-70b-versatile` with tool calling via the OpenAI-compatible API (`app/llm/agent.py`), backed by deterministic offline fallback to preserve quota during testing.
- **PayPal Integration**:
  - `POST /v1/oauth2/token`: Acquires access token with in-memory caching (`app/paypal/client.py`).
  - `POST /v2/checkout/orders`: Creates CAPTURE orders with custom invoice IDs and passport bundle hashes in `custom_id` (`app/paypal/client.py`).
  - `POST /v2/checkout/orders/{id}/capture`: Authorizes and captures funds upon shopper redirect (`app/paypal/client.py`).
  - `POST /v2/payments/captures/{id}/refund`: Disburses verified refunds against captured orders (`app/paypal/client.py`).
  - `POST /v1/notifications/verify-webhook-signature`: Validates all webhook events before updating order records (`app/paypal/webhooks.py`).
- **Frontend & Grids**: AG Grid Community tables for shade catalog management and real-time order tracking; Tailwind CSS (CDN) and vanilla JS for a zero-build client layer.

---

### PayPal Surfaces Utilized
| PayPal API Surface | Where It Is Used | Purpose |
|---|---|---|
| **Auth** | `app/paypal/client.py` | `POST /v1/oauth2/token` for OAuth2 authentication |
| **Orders v2 (Create)** | `app/paypal/client.py` & `/mcp` | `POST /v2/checkout/orders`: Server prices from DB; sets `custom_id` bundle hash |
| **Orders v2 (Capture)** | `app/paypal/client.py` & `/checkout/return` | `POST /v2/checkout/orders/{id}/capture`: Captures funds after shopper approves |
| **Payments v2 (Refunds)** | `app/paypal/client.py` | `POST /v2/payments/captures/{id}/refund`: Disburses verified refunds against capture IDs |
| **Webhooks with Signature Verification** | `app/paypal/webhooks.py` & `/webhooks/paypal` | `POST /v1/notifications/verify-webhook-signature`: Validates PayPal signature and idempotently streams sales to seller dashboard |
| **PayPal JS SDK** | `app/templates/shop.html` | Client-side Smart Buttons for human buyers |

---

### AI & Agent Components
| AI Component | Implementation | Function |
|---|---|---|
| **MCP Server Tools** | `app/mcp_server.py` | 5 tools mounted at `/mcp` for shopping agents |
| **Color Distance Matcher** | `app/color/pipeline.py` | CIEDE2000 ($\Delta E_{00}$) mathematical distance ranking |
| **Web Buyer Agent** | `app/llm/agent.py` | Groq `llama-3.3-70b-versatile` with tool calling and deterministic offline fallback |

---

### Challenges We Overcame
1. **Camera Sensor & Ambient Light Variability**: Different phones apply varying tone curves and color temperatures. Normalizing into linear RGB space before applying von Kries balancing against white printer paper cancels illumination bias.
2. **Agent Financial Hallucinations**: AI agents must never be permitted to specify item prices. We designed the checkout tool so agents submit only `shade_id` and quantity; all pricing is resolved authoritatively from the SQLite database.
3. **Webhook Idempotency in the Sandbox**: Implemented a `WebhookEvent` table to deduplicate PayPal webhook deliveries and prevent duplicate order updates.
4. **PayPal Audit Trail**: Built persistent `PayPalLog` storage to track every API interaction with HTTP status codes and `paypal-debug-id` telemetry.

---

### What's Next
- **Physical Swatch Library**: Controlled D65 lightbox photography of 50+ cosmetic swatches to publish real scientific accuracy benchmarks.
- **Catalog Synchronization**: Automated Shopify and WooCommerce integrations for independent beauty sellers.
- **Expanded Cosmetics Categories**: Applying calibrated Shade Passports to concealers, lipsticks, and tinted mineral sunscreens.

---

## 2. Devpost Submission Form Fields (Copy & Paste Ready)

- **Project Name:** Findable: Shade data AI shopping agents can trust
- **Elevator Pitch:** One phone photo turns a small beauty brand's swatches into measured shade data, so any AI shopping agent can match the right shade and check out with PayPal.
- **Submitter Type:** Team
- **New or Existing:** New — all code created during the hackathon period.
- **Sponsor Tools Used:** AG Grid, Render
- **Built With Tags:** `python`, `fastapi`, `pillow`, `scikit-image`, `numpy`, `paypal`, `paypal-orders-v2`, `paypal-webhooks`, `paypal-refunds`, `mcp`, `groq`, `ag-grid`, `render`, `sqlite`, `tailwindcss`
- **Testing Instructions:**  
  Start at `/judges` (no login needed).  
  PayPal Sandbox Buyer: `sb-buyer@findable.demo`  
  MCP endpoint: `/mcp`  
  Offline mode: set `MOCK_PAYPAL=1` in `.env` to test without PayPal keys.
