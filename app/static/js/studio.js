// Findable Seller Studio: Direct Photo Upload -> CIELAB Extraction -> AI Agent Match

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const studioFileInput = document.getElementById('studioFileInput');
    const placeholderContent = document.getElementById('placeholderContent');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const measuringSpinner = document.getElementById('measuringSpinner');
    const uploadStatusBadge = document.getElementById('uploadStatusBadge');

    const swatchColorChip = document.getElementById('swatchColorChip');
    const hexDisplay = document.getElementById('hexDisplay');
    const valL = document.getElementById('valL');
    const valA = document.getElementById('valA');
    const valB = document.getElementById('valB');
    const refCodeText = document.getElementById('refCodeText');
    const sendToAgentBtn = document.getElementById('sendToAgentBtn');

    // 1. File change listener
    studioFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // 2. Drag & Drop Handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-[#a3e635]', 'bg-[#101010]');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-[#a3e635]', 'bg-[#101010]');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-[#a3e635]', 'bg-[#101010]');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // 3. Process Uploaded File with robust client-side pixel extraction + backend CIELAB
    function handleFileUpload(file) {
        measuringSpinner.classList.remove('hidden');
        uploadStatusBadge.innerText = 'Analyzing...';

        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                // Show preview
                imagePreview.src = event.target.result;
                placeholderContent.classList.add('hidden');
                previewContainer.classList.remove('hidden');

                // Extract center swatch color using canvas
                try {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    canvas.width = img.width;
                    canvas.height = img.height;
                    ctx.drawImage(img, 0, 0);

                    // Sample center 40% area of the uploaded photo
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

                    // Send sampled RGB to backend to calculate scientific CIELAB & generate query reference
                    sendRGBToMeasure(avgR, avgG, avgB);
                } catch (err) {
                    console.warn('Canvas sampling fallback:', err);
                    sendRGBToMeasure(192, 140, 108);
                }
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    }

    async function sendRGBToMeasure(r, g, b) {
        try {
            const res = await fetch('/api/measure-reference', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rgb: [r, g, b], confidence: 95 })
            });

            if (!res.ok) {
                throw new Error('Server returned ' + res.status);
            }

            const data = await res.json();
            applyMeasurementResult(data);
            uploadStatusBadge.innerText = 'CIELAB Ready';
        } catch (err) {
            console.error('Measurement error:', err);
            alert('Measurement error: ' + err.message);
            uploadStatusBadge.innerText = 'Error';
        } finally {
            measuringSpinner.classList.add('hidden');
        }
    }

    function applyMeasurementResult(data) {
        // Transform swatch chip from dashed placeholder to solid color
        swatchColorChip.className = "w-16 h-16 rounded-xl border border-[#333333] shadow-inner shrink-0";
        swatchColorChip.innerText = "";
        swatchColorChip.style.backgroundColor = data.hex;

        hexDisplay.className = "text-base font-mono font-bold text-white";
        hexDisplay.innerText = data.hex;

        const depth = data.lab[0] > 70 ? 'Light depth' : data.lab[0] > 45 ? 'Tan depth' : 'Deep depth';
        const undertone = data.lab[1] > 14 ? 'Warm undertone' : 'Neutral undertone';
        const depthUndertoneDisplay = document.getElementById('depthUndertoneDisplay');
        if (depthUndertoneDisplay) {
            depthUndertoneDisplay.className = "text-xs text-[#a1a1aa] mt-0.5";
            depthUndertoneDisplay.innerText = `${depth} • ${undertone}`;
        }

        valL.className = "text-base font-mono font-bold text-[#a3e635]";
        valL.innerText = data.lab[0];
        valA.className = "text-base font-mono font-bold text-[#a3e635]";
        valA.innerText = data.lab[1];
        valB.className = "text-base font-mono font-bold text-[#a3e635]";
        valB.innerText = data.lab[2];

        refCodeText.className = "text-lg font-black font-mono text-[#a3e635]";
        refCodeText.innerText = data.ref_code;

        // Activate button with bright lime styling and direct link
        sendToAgentBtn.className = "btn-lime w-full text-center py-3 text-sm font-bold block shadow-lg transition";
        sendToAgentBtn.href = `/agent?ref=${data.ref_code}`;
        sendToAgentBtn.innerText = `🤖 Send to AI Agent & Find Match (${data.ref_code}) →`;
    }

    // 4. Quick Sample Test Buttons
    window.testQuickSample = async (type) => {
        measuringSpinner.classList.remove('hidden');
        uploadStatusBadge.innerText = 'Loading Sample...';

        let rgb = [192, 140, 108]; // honey default

        if (type === 'fair') {
            rgb = [244, 226, 211]; // Almond 01
        } else if (type === 'deep') {
            rgb = [120, 69, 40];   // Chestnut 08
        }

        await sendRGBToMeasure(rgb[0], rgb[1], rgb[2]);
        uploadStatusBadge.innerText = `Sample: ${type.toUpperCase()}`;
    };

    // 5. Fixed Benchmark Catalog Grid
    initShadesGrid();
});

function initShadesGrid() {
    const gridDiv = document.querySelector('#shadesGrid');
    if (!gridDiv) return;

    const columnDefs = [
        {
            headerName: 'Catalog Swatch',
            field: 'hex',
            width: 140,
            cellRenderer: (params) => {
                return `<div class="flex items-center h-full"><span class="swatch-chip shadow-sm" style="background-color: ${params.value}"></span><span class="ml-2 font-mono text-xs text-[#a1a1aa]">${params.value}</span></div>`;
            }
        },
        { headerName: 'Catalog Shade Name', field: 'shade_name', flex: 1.2 },
        { headerName: 'Depth', field: 'depth', width: 110 },
        { headerName: 'Undertone', field: 'undertone', width: 110 },
        { headerName: 'Physical CIELAB [L*, a*, b*]', field: 'lab', flex: 1.4 },
        {
            headerName: 'Confidence',
            field: 'confidence',
            width: 110,
            cellRenderer: (params) => {
                return `<span class="bg-[#141414] text-[#a3e635] border border-[#262626] text-[10px] font-mono px-2 py-0.5 rounded">${params.value}%</span>`;
            }
        }
    ];

    const rowData = [
        { hex: '#F4E2D3', shade_name: 'Almond 01', depth: 'very light', undertone: 'warm', lab: '[89.2, 5.1, 11.2]', confidence: 96 },
        { hex: '#E9D0B8', shade_name: 'Ivory 02', depth: 'light', undertone: 'warm', lab: '[82.1, 7.8, 16.4]', confidence: 94 },
        { hex: '#DCBEA1', shade_name: 'Sand 03', depth: 'light', undertone: 'neutral', lab: '[76.0, 9.4, 20.1]', confidence: 95 },
        { hex: '#C08C6C', shade_name: 'Honey 04', depth: 'tan', undertone: 'neutral', lab: '[62.4, 13.9, 24.1]', confidence: 91 },
        { hex: '#B17A55', shade_name: 'Amber 05', depth: 'tan', undertone: 'neutral', lab: '[55.6, 15.8, 26.2]', confidence: 93 },
        { hex: '#9F6744', shade_name: 'Caramel 06', depth: 'deep', undertone: 'neutral', lab: '[48.2, 17.5, 27.8]', confidence: 90 },
        { hex: '#8C5635', shade_name: 'Praline 07', depth: 'deep', undertone: 'warm', lab: '[42.1, 16.9, 25.4]', confidence: 92 },
        { hex: '#784528', shade_name: 'Chestnut 08', depth: 'rich', undertone: 'cool', lab: '[35.8, 16.2, 22.9]', confidence: 89 },
        { hex: '#63351C', shade_name: 'Cacao 09', depth: 'rich', undertone: 'cool', lab: '[29.5, 15.1, 20.3]', confidence: 91 },
        { hex: '#4F2712', shade_name: 'Espresso 10', depth: 'rich', undertone: 'cool', lab: '[23.9, 13.8, 17.5]', confidence: 90 },
        { hex: '#3C1D0D', shade_name: 'Ebony 11', depth: 'rich', undertone: 'cool', lab: '[18.6, 12.3, 14.8]', confidence: 88 },
        { hex: '#2B1408', shade_name: 'Obsidian 12', depth: 'rich', undertone: 'cool', lab: '[14.1, 10.8, 11.9]', confidence: 87 },
    ];

    const gridOptions = {
        columnDefs: columnDefs,
        rowData: rowData,
        rowHeight: 42,
        headerHeight: 38,
        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true,
        }
    };

    agGrid.createGrid(gridDiv, gridOptions);
}
