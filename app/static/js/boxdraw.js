/**
 * boxdraw.js — Reusable canvas module for drawing Paper + Swatch boxes.
 * Usage: const bd = new BoxDraw(canvasEl, onChangeCallback);
 * bd.loadImage(dataURL) — load photo onto canvas
 * bd.getBoxes() — returns {paper:[x0,y0,x1,y1], swatches:[[...],...]} as fractions 0-1
 * bd.undo() / bd.clear()
 */
class BoxDraw {
    constructor(canvas, onChange) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.onChange = onChange || (() => {});
        this.boxes = []; // [{label, x0, y0, x1, y1}] in fractional coords
        this.img = null;
        this.imgW = 0;
        this.imgH = 0;
        this._dragging = false;
        this._startX = 0;
        this._startY = 0;
        this._currentRect = null;

        this._bindEvents();
    }

    loadImage(dataURL) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                this.img = img;
                this.imgW = img.naturalWidth;
                this.imgH = img.naturalHeight;
                // Fit canvas to container width while keeping aspect ratio
                const displayW = this.canvas.parentElement
                    ? this.canvas.parentElement.clientWidth || 600
                    : 600;
                const scale = displayW / img.naturalWidth;
                this.canvas.width = displayW;
                this.canvas.height = img.naturalHeight * scale;
                this.boxes = [];
                this._draw();
                resolve();
            };
            img.onerror = reject;
            img.src = dataURL;
        });
    }

    getBoxes() {
        const paper = this.boxes.find(b => b.label === 'Paper');
        const swatches = this.boxes.filter(b => b.label !== 'Paper');
        return {
            paper: paper ? [paper.x0, paper.y0, paper.x1, paper.y1] : null,
            swatches: swatches.map(b => [b.x0, b.y0, b.x1, b.y1]),
        };
    }

    undo() {
        this.boxes.pop();
        this._draw();
        this.onChange(this.getBoxes());
    }

    clear() {
        this.boxes = [];
        this._draw();
        this.onChange(this.getBoxes());
    }

    _nextLabel() {
        const hasPaper = this.boxes.some(b => b.label === 'Paper');
        if (!hasPaper) return 'Paper';
        const swatchCount = this.boxes.filter(b => b.label !== 'Paper').length;
        return `Swatch ${swatchCount + 1}`;
    }

    _toFrac(px, py) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const cx = (px - rect.left) * scaleX;
        const cy = (py - rect.top) * scaleY;
        // Convert canvas pixels to image fractions
        const imgScaleX = this.imgW / this.canvas.width;
        const imgScaleY = this.imgH / this.canvas.height;
        return {
            fx: (cx * imgScaleX) / this.imgW,
            fy: (cy * imgScaleY) / this.imgH,
            cx, cy,
        };
    }

    _bindEvents() {
        const startDrag = (px, py) => {
            const { fx, fy, cx, cy } = this._toFrac(px, py);
            this._dragging = true;
            this._startX = cx;
            this._startY = cy;
            this._startFX = fx;
            this._startFY = fy;
            this._currentRect = null;
        };

        const moveDrag = (px, py) => {
            if (!this._dragging) return;
            const { cx, cy } = this._toFrac(px, py);
            this._currentRect = {
                x: Math.min(this._startX, cx),
                y: Math.min(this._startY, cy),
                w: Math.abs(cx - this._startX),
                h: Math.abs(cy - this._startY),
            };
            this._draw();
        };

        const endDrag = (px, py) => {
            if (!this._dragging) return;
            this._dragging = false;
            const { fx, fy } = this._toFrac(px, py);
            const x0 = Math.min(this._startFX, fx);
            const y0 = Math.min(this._startFY, fy);
            const x1 = Math.max(this._startFX, fx);
            const y1 = Math.max(this._startFY, fy);
            if ((x1 - x0) * this.imgW > 5 && (y1 - y0) * this.imgH > 5) {
                this.boxes.push({ label: this._nextLabel(), x0, y0, x1, y1 });
            }
            this._currentRect = null;
            this._draw();
            this.onChange(this.getBoxes());
        };

        // Mouse
        this.canvas.addEventListener('mousedown', e => startDrag(e.clientX, e.clientY));
        this.canvas.addEventListener('mousemove', e => moveDrag(e.clientX, e.clientY));
        this.canvas.addEventListener('mouseup', e => endDrag(e.clientX, e.clientY));

        // Touch
        this.canvas.addEventListener('touchstart', e => {
            e.preventDefault();
            const t = e.touches[0];
            startDrag(t.clientX, t.clientY);
        }, { passive: false });
        this.canvas.addEventListener('touchmove', e => {
            e.preventDefault();
            const t = e.touches[0];
            moveDrag(t.clientX, t.clientY);
        }, { passive: false });
        this.canvas.addEventListener('touchend', e => {
            e.preventDefault();
            const t = e.changedTouches[0];
            endDrag(t.clientX, t.clientY);
        }, { passive: false });
    }

    _draw() {
        const cv = this.canvas;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, cv.width, cv.height);
        if (this.img) {
            ctx.drawImage(this.img, 0, 0, cv.width, cv.height);
        }

        // Draw committed boxes
        this.boxes.forEach(b => {
            const isPaper = b.label === 'Paper';
            const x = b.x0 * cv.width * (this.imgW / this.imgW); // = b.x0 * cv.width
            const y = b.y0 * cv.height;
            const w = (b.x1 - b.x0) * cv.width;
            const h = (b.y1 - b.y0) * cv.height;
            ctx.strokeStyle = isPaper ? '#ffffff' : '#a3e635';
            ctx.lineWidth = 2;
            ctx.setLineDash(isPaper ? [6, 3] : []);
            ctx.strokeRect(x, y, w, h);
            ctx.fillStyle = isPaper ? 'rgba(255,255,255,0.08)' : 'rgba(163,230,53,0.08)';
            ctx.fillRect(x, y, w, h);
            // Label
            ctx.fillStyle = isPaper ? '#ffffff' : '#a3e635';
            ctx.font = 'bold 12px monospace';
            ctx.fillText(b.label, x + 4, y + 14);
        });

        // Draw in-progress rectangle
        if (this._currentRect) {
            const hasPaper = this.boxes.some(b => b.label === 'Paper');
            ctx.strokeStyle = hasPaper ? '#a3e635' : '#ffffff';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.strokeRect(
                this._currentRect.x,
                this._currentRect.y,
                this._currentRect.w,
                this._currentRect.h
            );
        }

        ctx.setLineDash([]);
    }
}
