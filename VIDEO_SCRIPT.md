# Findable: Hackathon Video Script & Shot List

> **Target Duration:** 2 minutes 45 seconds (Hard stop: 3:00)  
> **Resolution:** 1080p, 60fps  
> **Audio:** Clear voiceover with burned-in subtitles  
> **Pitch Tagline:** *"Toffee isn't a colour. ΔE 1.8 is."*

---

## Shot List & Script Breakdown

| Timestamp | Visual / Screen Recording | Voiceover Script | Production Notes |
|---|---|---|---|
| **0:00 – 0:15** | Close-up shot of Priya's 12 foundation jars on a wooden kitchen table. Cut to an AI shopping agent chat recommending a large conglomerate brand instead. | *"Priya makes clean foundations in 12 shades. But to an AI shopping agent, they're just subjective names—Toffee, Honey, Caramel. An agent can't match a name to a customer's complexion, so it sends buyers to conglomerate brands with proprietary shade finders."* | Zoom in on jar handwritten labels vs generic LLM chat output. |
| **0:15 – 0:30** | Title cards with statistics: Foundation returns ~23%, mostly shade mismatch (*NRF / retail benchmarks*). Cut to PayPal quote: *"AI agents surface products based on fit, not ad budget."* | *"Shade mismatch is why foundation returns are triple other categories. PayPal says AI agents should buy on fit, not ad spend. But fit requires objective, structured data."* | Bold, clean typography on dark background with lime accents. |
| **0:30 – 1:10** | **Seller Studio**: Priya uploads a phone photo on white printer paper taken under warm lighting. Drags paper box + swatch boxes &rarr; clicks **Measure** &rarr; raw vs calibrated chips appear side by side &rarr; AG Grid table populates &rarr; clicks **Publish Passports**. | *"One phone photo on plain white paper. Findable uses the paper as a neutral diffuser to cancel ambient lighting, extracting physical CIELAB coordinates. It signs a tamper-evident Shade Passport for every shade with HMAC-SHA256. Same swatch under warm lighting: lighting bias is eliminated in linear RGB."* | Highlight the real-time split chip view and AG Grid Community table. |
| **1:10 – 1:55** | **AI Agent / Claude Desktop via MCP**: Shopper uploads face photo &rarr; samples cheek shade &rarr; system returns top-5 matches with honest CIEDE2000 ΔE optical distances &rarr; agent prepares order with server-authoritative pricing &rarr; opens PayPal Sandbox checkout. | *"Any shopping agent can discover Priya. Claude or our web agent calls Findable over MCP, finds Honey 04 at ΔE 1.2—virtually imperceptible to the human eye—and prepares a verified PayPal checkout. The shopper approves in PayPal; the agent never touches funds."* | Emphasize server-side authoritative pricing, ΔE ranking, and PayPal approve screen. |
| **1:55 – 2:25** | **PayPal Sandbox Approval & Return**: Shopper logs into PayPal Sandbox, clicks Pay Now &rarr; redirects to verified return view with Order ID and capture details. | *"The shopper approves the transaction in PayPal Sandbox. Findable captures the order, binds the passport bundle hash into custom_id, and permanently links the payment to the exact optical measurement shown to the agent."* | Show PayPal Sandbox login, approval, and verified confirmation page. |
| **2:25 – 2:45** | **Seller Dashboard & Audit Trail**: Real-time order row in AG Grid, showing capture ID and passport bundle hash. Scroll to live PayPal REST telemetry log. | *"Priya sees the sale immediately on her dashboard via a cryptographically verified webhook. In the persistent PayPalLog audit trail, every Orders v2 call, capture, and webhook signature verification is logged."* | Show AG Grid order row and PayPal REST telemetry log. |
| **2:45 – 2:55** | Findable Logo & PayPal Hackathon lockup banner. | *"Findable. Toffee isn't a colour. ΔE 1.8 is."* | Fade to black. |

---

## Recording Checklist
- [ ] No background music unless royalty-free with license.
- [ ] No third-party trademarks, logos, or copyrighted assets shown.
- [ ] Screen captures zoomed to 125% for high readability on mobile devices.
- [ ] Subtitles embedded and synchronized with voiceover.
- [ ] Keep final export under 3 minutes (2:45 recommended).
