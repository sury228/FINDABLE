// Findable AI Shopping Agent: Conversational loop, match cards & box-draw swatch upload

let agentBoxDraw = null;
let agentCurrentRef = null;

// ─── Measure Drawer ───────────────────────────────────────────────────────────

function openMeasureDrawer() {
    document.getElementById('measureDrawer').classList.remove('hidden');
}

function closeMeasureDrawer() {
    document.getElementById('measureDrawer').classList.add('hidden');
}

function sendRefToChat() {
    if (!agentCurrentRef) return;
    const userInput = document.getElementById('userInput');
    const chatForm = document.getElementById('chatForm');
    userInput.value = `My shade is ${agentCurrentRef}, find me a match`;
    closeMeasureDrawer();
    chatForm.dispatchEvent(new Event('submit'));
}

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatContainer = document.getElementById('chatContainer');
    const agentFileInput = document.getElementById('agentFileInput');
    const agentCanvasWrap = document.getElementById('agentCanvasWrap');
    const agentCanvas = document.getElementById('agentCanvas');
    const agentMeasureBtn = document.getElementById('agentMeasureBtn');
    const agentBoxStatus = document.getElementById('agentBoxStatus');

    let history = [];

    // ── File picker → load into BoxDraw ──────────────────────────────────────
    agentFileInput.addEventListener('change', async (e) => {
        if (!e.target.files || !e.target.files[0]) return;
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = async (evt) => {
            agentCanvasWrap.classList.remove('hidden');
            if (!agentBoxDraw) {
                agentBoxDraw = new BoxDraw(agentCanvas, onAgentBoxChange);
            }
            await agentBoxDraw.loadImage(evt.target.result);
            agentBoxStatus.textContent = 'Draw Paper box first (white paper reference)';
            agentMeasureBtn.disabled = true;
            document.getElementById('agentMeasureResult').classList.add('hidden');
        };
        reader.readAsDataURL(file);
    });

    function onAgentBoxChange(boxes) {
        if (!boxes.paper) {
            agentBoxStatus.textContent = 'Draw Paper box first (white paper reference)';
            agentMeasureBtn.disabled = true;
        } else if (boxes.swatches.length === 0) {
            agentBoxStatus.textContent = 'Now draw your Swatch box';
            agentMeasureBtn.disabled = true;
        } else {
            agentBoxStatus.textContent = `Paper ✓ · ${boxes.swatches.length} swatch box(es). Ready to measure.`;
            agentMeasureBtn.disabled = false;
        }
    }

    window.runAgentMeasure = async () => {
        const boxes = agentBoxDraw.getBoxes();
        if (!boxes.paper || boxes.swatches.length === 0) {
            alert('Please draw a Paper box and at least one Swatch box first.');
            return;
        }
        agentMeasureBtn.disabled = true;
        agentBoxStatus.textContent = 'Measuring…';

        const formData = new FormData();
        // Re-read the uploaded file
        formData.append('file', agentFileInput.files[0]);
        formData.append('boxes', JSON.stringify({
            paper: boxes.paper,
            swatches: boxes.swatches,
        }));

        try {
            const res = await fetch('/api/measure', { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || res.statusText);
            }
            const data = await res.json();
            const sw = data.swatches[0];
            const lab = sw.corrected.lab;

            // Save reference to DB
            const refRes = await fetch('/api/references', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lab, hex: sw.corrected.hex, confidence: sw.confidence }),
            });
            const refData = await refRes.json();
            agentCurrentRef = refData.ref_code;

            // Show result
            document.getElementById('agentSwatchChip').style.backgroundColor = sw.corrected.hex;
            document.getElementById('agentHex').textContent = sw.corrected.hex;
            document.getElementById('agentLabDisplay').textContent =
                `L* ${lab[0]} · a* ${lab[1]} · b* ${lab[2]} · ${sw.corrected.depth} · ${sw.corrected.undertone} · confidence ${sw.confidence}%`;
            document.getElementById('agentRefCode').textContent = agentCurrentRef;
            document.getElementById('agentMeasureResult').classList.remove('hidden');
            agentBoxStatus.textContent = `Measured ✓ — your code: ${agentCurrentRef}`;
            agentMeasureBtn.disabled = false;
        } catch (err) {
            agentBoxStatus.textContent = 'Error: ' + err.message;
            agentMeasureBtn.disabled = false;
            alert('Measurement error: ' + err.message);
        }
    };

    // ── Chat Form ─────────────────────────────────────────────────────────────
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        appendMessage('user', message);
        userInput.value = '';

        const typingEl = appendTypingIndicator();

        try {
            const res = await fetch('/api/agent/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, history }),
            });
            const data = await res.json();
            typingEl.remove();

            appendMessage('agent', data.reply, data.cards);
            history.push({ role: 'user', content: message });
            history.push({ role: 'assistant', content: data.reply });
        } catch (err) {
            typingEl.remove();
            appendMessage('agent', 'Error processing request. Please check server logs.');
        }
    });

    // ── URL param: auto-search on ?ref= redirect ──────────────────────────────
    const urlParams = new URLSearchParams(window.location.search);
    const refParam = urlParams.get('ref');
    if (refParam) {
        userInput.value = `My shade is ${refParam}, find me a match`;
        setTimeout(() => chatForm.dispatchEvent(new Event('submit')), 400);
    }

    // ── Rendering helpers ─────────────────────────────────────────────────────
    function appendMessage(sender, text, cards = []) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `flex items-start gap-3 ${sender === 'user' ? 'flex-row-reverse' : ''}`;

        const avatar = document.createElement('div');
        avatar.className = `w-8 h-8 rounded-full font-bold flex items-center justify-center text-xs shrink-0 ${
            sender === 'user' ? 'bg-[#262626] text-white border border-[#333333]' : 'bg-[#a3e635] text-black font-black'
        }`;
        avatar.innerText = sender === 'user' ? 'You' : 'AI';

        const content = document.createElement('div');
        content.className = `rounded-2xl px-4 py-3 text-sm max-w-lg space-y-3 ${
            sender === 'user'
                ? 'bg-[#1a1a1a] text-white border border-[#333333] rounded-tr-sm'
                : 'bg-[#141414] text-white border border-[#262626] rounded-tl-sm'
        }`;

        const textP = document.createElement('p');
        textP.innerHTML = formatMarkdown(text);
        content.appendChild(textP);

        if (cards && cards.length > 0) {
            cards.forEach((card) => {
                if (card.type === 'matches') content.appendChild(renderMatchesCard(card.data));
                else if (card.type === 'checkout') content.appendChild(renderCheckoutCard(card.data));
            });
        }

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(content);
        chatContainer.appendChild(msgDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function renderMatchesCard(matches) {
        const cardBox = document.createElement('div');
        cardBox.className = 'space-y-2 pt-2 border-t border-[#262626]';

        matches.forEach((m) => {
            const item = document.createElement('div');
            item.className = 'bg-[#0d0d0d] rounded-xl p-3 border border-[#262626] flex items-center justify-between gap-3';

            let badgeClass = 'bg-[#141414] text-[#a3e635] border-[#262626]';
            let badgeText = `ΔE ${m.delta_e} · ${m.label}`;

            if (m.delta_e <= 2.0) {
                badgeClass = 'bg-[#141414] text-[#a3e635] border-[#a3e635]';
                badgeText = `ΔE ${m.delta_e} — hard to tell apart`;
            } else if (m.delta_e <= 4.0) {
                badgeClass = 'bg-[#141414] text-yellow-300 border-[#333333]';
                badgeText = `ΔE ${m.delta_e} — close`;
            } else {
                badgeClass = 'bg-[#141414] text-zinc-400 border-[#333333]';
                badgeText = `ΔE ${m.delta_e} — different`;
            }

            item.innerHTML = `
                <div class="flex items-center gap-2.5">
                    <span class="w-8 h-8 rounded-full border border-[#333333] shadow-inner" style="background-color: ${m.hex};"></span>
                    <div>
                        <div class="font-bold text-white text-xs">${m.shade_name}</div>
                        <div class="text-[10px] text-[#a1a1aa]">${m.product_name} &bull; $${m.price.toFixed(2)}</div>
                    </div>
                </div>
                <div class="text-right">
                    <span class="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${badgeClass}">
                        ${badgeText}
                    </span>
                    <button onclick="orderShade('${m.shade_id}')" class="btn-lime text-[10px] py-1 px-2.5 mt-1.5 block">
                        Order Shade &rarr;
                    </button>
                </div>
            `;
            cardBox.appendChild(item);
        });

        return cardBox;
    }

    function renderCheckoutCard(checkout) {
        const box = document.createElement('div');
        box.className = 'bg-[#0d0d0d] rounded-xl p-4 border border-[#262626] space-y-3';
        box.innerHTML = `
            <div class="flex justify-between items-center text-xs">
                <span class="font-bold text-white">PayPal Checkout Ready</span>
                <span class="font-mono text-[10px] bg-[#141414] text-[#a3e635] px-1.5 py-0.5 rounded border border-[#262626]">${checkout.custom_id}</span>
            </div>
            <div class="text-xs text-[#a1a1aa]">
                Total: <strong class="text-white font-mono">$${checkout.total.toFixed(2)} ${checkout.currency}</strong>
            </div>
            <a href="${checkout.approve_url}" class="btn-lime w-full text-center py-2.5 text-xs font-bold block">
                Approve in PayPal &rarr;
            </a>
            <p class="text-[10px] text-[#71717a] text-center">The agent prepares the order; you approve it in PayPal.</p>
        `;
        return box;
    }

    window.orderShade = (shadeId) => {
        userInput.value = `Order ${shadeId}`;
        chatForm.dispatchEvent(new Event('submit'));
    };

    function appendTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'flex items-center gap-2 text-stone-400 text-xs italic';
        div.innerText = 'Findable agent is evaluating Shade Passports…';
        chatContainer.appendChild(div);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return div;
    }

    function formatMarkdown(str) {
        return str
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code class="bg-[#1a1a1a] px-1 rounded text-[#a3e635] font-mono text-xs">$1</code>')
            .replace(/\n/g, '<br>');
    }

    window.setInput = (text) => {
        userInput.value = text;
        userInput.focus();
    };
});
