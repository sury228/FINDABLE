// Findable AI Shopping Agent: Conversational loop, match cards & telemetry stream

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatContainer = document.getElementById('chatContainer');
    const toggleTelemetryBtn = document.getElementById('toggleTelemetryBtn');
    const telemetryPanel = document.getElementById('telemetryPanel');
    const telemetryLog = document.getElementById('telemetryLog');

    let history = [];

    // Toggle Behind-the-Scenes telemetry drawer if present
    if (toggleTelemetryBtn && telemetryPanel) {
        toggleTelemetryBtn.addEventListener('click', () => {
            telemetryPanel.classList.toggle('hidden');
        });
    }

    const cameraBtn = document.getElementById('cameraBtn');
    const agentFileInput = document.getElementById('agentFileInput');

    window.setInput = (text) => {
        userInput.value = text;
        userInput.focus();
    };

    if (agentFileInput) {
        agentFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                const file = e.target.files[0];
                logTelemetry(`Reading swatch image: ${file.name}...`);
                const typingEl = appendTypingIndicator();
                typingEl.innerText = `Measuring swatch photo: extracting CIELAB coordinates...`;

                const reader = new FileReader();
                reader.onload = (event) => {
                    const img = new Image();
                    img.onload = async () => {
                        try {
                            const canvas = document.createElement('canvas');
                            const ctx = canvas.getContext('2d');
                            canvas.width = img.width;
                            canvas.height = img.height;
                            ctx.drawImage(img, 0, 0);

                            const sx = Math.floor(img.width * 0.3);
                            const sy = Math.floor(img.height * 0.3);
                            const sw = Math.max(1, Math.floor(img.width * 0.4));
                            const sh = Math.max(1, Math.floor(img.height * 0.4));

                            const imgData = ctx.getImageData(sx, sy, sw, sh).data;
                            let r = 0, g = 0, b = 0, count = 0;
                            for (let i = 0; i < imgData.length; i += 4) {
                                if (imgData[i + 3] > 128) {
                                    r += imgData[i];
                                    g += imgData[i + 1];
                                    b += imgData[i + 2];
                                    count++;
                                }
                            }

                            const avgR = count > 0 ? Math.round(r / count) : 192;
                            const avgG = count > 0 ? Math.round(g / count) : 140;
                            const avgB = count > 0 ? Math.round(b / count) : 108;

                            const measureRes = await fetch('/api/measure-reference', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ rgb: [avgR, avgG, avgB], confidence: 95 })
                            });
                            const data = await measureRes.json();
                            typingEl.remove();

                            logTelemetry(`CIELAB Extracted: L* ${data.lab[0]}, a* ${data.lab[1]}, b* ${data.lab[2]} (${data.hex}) -> ${data.ref_code}`);

                            // Automatically trigger match search
                            userInput.value = `My shade is ${data.ref_code} (CIELAB L* ${data.lab[0]}, a* ${data.lab[1]}, b* ${data.lab[2]}), find me a match under $30`;
                            chatForm.dispatchEvent(new Event('submit'));
                        } catch (err) {
                            typingEl.remove();
                            alert('Measurement error: ' + err);
                        }
                    };
                    img.src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        // Append User Message
        appendMessage('user', message);
        userInput.value = '';

        logTelemetry(`User -> Agent: "${message}"`);

        // Typing indicator
        const typingEl = appendTypingIndicator();

        try {
            const res = await fetch('/api/agent/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message, history: history }),
            });
            const data = await res.json();
            typingEl.remove();

            // Stream tool calls to Behind-the-Scenes panel
            if (data.tools_called && data.tools_called.length > 0) {
                data.tools_called.forEach((t) => {
                    logTelemetry(`[MCP Tool Invoked] ${t.tool}(${JSON.stringify(t.args)})`);
                });
            }

            // Append Agent Response
            appendMessage('agent', data.reply, data.cards);

            history.push({ role: 'user', content: message });
            history.push({ role: 'assistant', content: data.reply });
        } catch (err) {
            typingEl.remove();
            appendMessage('agent', 'I encountered an issue processing your request. Please check server logs.');
            logTelemetry(`[Error] ${err}`);
        }
    });

    function logTelemetry(msg) {
        if (!telemetryLog) return;
        const line = document.createElement('div');
        const time = new Date().toLocaleTimeString();
        line.innerHTML = `<span class="text-stone-500">[${time}]</span> ${msg}`;
        telemetryLog.appendChild(line);
        telemetryLog.scrollTop = telemetryLog.scrollHeight;
    }

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

        // Render interactive cards if present
        if (cards && cards.length > 0) {
            cards.forEach((card) => {
                if (card.type === 'matches') {
                    content.appendChild(renderMatchesCard(card.data));
                } else if (card.type === 'checkout') {
                    content.appendChild(renderCheckoutCard(card.data));
                }
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
            let badgeText = `ΔE ${m.delta_e} • Match`;
            
            if (m.delta_e <= 2.0) {
                badgeClass = 'bg-[#141414] text-[#a3e635] border-[#a3e635]';
                badgeText = `Exact Match (ΔE ${m.delta_e})`;
            } else if (m.delta_e <= 4.0) {
                badgeClass = 'bg-[#141414] text-yellow-300 border-[#333333]';
                badgeText = `Close Match (ΔE ${m.delta_e})`;
            } else {
                badgeClass = 'bg-[#141414] text-zinc-400 border-[#333333]';
                badgeText = `Nearest Candidate (ΔE ${m.delta_e})`;
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
                Approve in PayPal Sandbox &rarr;
            </a>
            <p class="text-[10px] text-[#71717a] text-center">Funds captured only upon your approval.</p>
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
        div.innerText = 'Findable agent is evaluating Shade Passports...';
        chatContainer.appendChild(div);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return div;
    }

    function formatMarkdown(str) {
        return str
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    // Auto-search if redirected from Seller Studio with ?ref=
    const urlParams = new URLSearchParams(window.location.search);
    const refParam = urlParams.get('ref');
    if (refParam) {
        userInput.value = `My shade is ${refParam}, find me a match`;
        setTimeout(() => {
            chatForm.dispatchEvent(new Event('submit'));
        }, 300);
    }
});

