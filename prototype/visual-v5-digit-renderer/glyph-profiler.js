(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.DigitGlyphProfiler = api;
})(typeof window !== 'undefined' ? window : null, function () {
  const ALLOWED_GLYPHS = Object.freeze(['0','1','2','3','4','5','6','7','8','9','.',':','-']);

  function clamp01(value) {
    return Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  }

  function validateMask(mask, width, height) {
    if (!mask || typeof mask.length !== 'number') throw new TypeError('mask must be array-like');
    if (!Number.isInteger(width) || width <= 0) throw new TypeError('width must be a positive integer');
    if (!Number.isInteger(height) || height <= 0) throw new TypeError('height must be a positive integer');
    if (mask.length < width * height) throw new RangeError('mask is smaller than width * height');
  }

  function downsampleMask(mask, width, height, patchWidth, patchHeight) {
    const patch = new Array(patchWidth * patchHeight).fill(0);
    for (let py = 0; py < patchHeight; py += 1) {
      const y0 = (py * height) / patchHeight;
      const y1 = ((py + 1) * height) / patchHeight;
      const sy0 = Math.max(0, Math.floor(y0));
      const sy1 = Math.min(height, Math.max(sy0 + 1, Math.ceil(y1)));
      for (let px = 0; px < patchWidth; px += 1) {
        const x0 = (px * width) / patchWidth;
        const x1 = ((px + 1) * width) / patchWidth;
        const sx0 = Math.max(0, Math.floor(x0));
        const sx1 = Math.min(width, Math.max(sx0 + 1, Math.ceil(x1)));
        let sum = 0;
        let count = 0;
        for (let y = sy0; y < sy1; y += 1) {
          for (let x = sx0; x < sx1; x += 1) {
            sum += clamp01(mask[y * width + x]);
            count += 1;
          }
        }
        patch[py * patchWidth + px] = count ? sum / count : 0;
      }
    }
    return patch;
  }

  function analyzeMask(mask, width, height, patchWidth = 4, patchHeight = 6) {
    validateMask(mask, width, height);
    let total = 0;
    let weightedX = 0;
    let weightedY = 0;
    let horizontalConnections = 0;
    let verticalConnections = 0;
    let horizontalPairs = 0;
    let verticalPairs = 0;
    let edgeX = 0;
    let edgeY = 0;

    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const v = clamp01(mask[y * width + x]);
        total += v;
        weightedX += v * (width === 1 ? 0.5 : x / (width - 1));
        weightedY += v * (height === 1 ? 0.5 : y / (height - 1));
        if (x + 1 < width) {
          const n = clamp01(mask[y * width + x + 1]);
          horizontalConnections += Math.min(v, n);
          edgeX += Math.abs(n - v);
          horizontalPairs += 1;
        }
        if (y + 1 < height) {
          const n = clamp01(mask[(y + 1) * width + x]);
          verticalConnections += Math.min(v, n);
          edgeY += Math.abs(n - v);
          verticalPairs += 1;
        }
      }
    }

    const count = width * height;
    const density = total / count;
    return {
      density,
      centerX: total ? weightedX / total : 0.5,
      centerY: total ? weightedY / total : 0.5,
      horizontal: horizontalPairs ? horizontalConnections / horizontalPairs : 0,
      vertical: verticalPairs ? verticalConnections / verticalPairs : 0,
      edgeX: horizontalPairs ? edgeX / horizontalPairs : 0,
      edgeY: verticalPairs ? edgeY / verticalPairs : 0,
      patch: downsampleMask(mask, width, height, patchWidth, patchHeight),
    };
  }

  function profileFont({
    fontFamily,
    fontSize,
    lineHeight,
    glyphs = ALLOWED_GLYPHS,
    patchWidth = 4,
    patchHeight = 6,
  }) {
    if (typeof document === 'undefined') {
      throw new Error('profileFont requires a browser DOM');
    }
    if (!fontFamily) throw new TypeError('fontFamily is required');
    if (!Number.isFinite(fontSize) || fontSize <= 0) throw new TypeError('fontSize must be positive');
    if (!Number.isFinite(lineHeight) || lineHeight <= 0) throw new TypeError('lineHeight must be positive');

    const measurement = document.createElement('canvas');
    const measureCtx = measurement.getContext('2d', { willReadFrequently: true });
    measureCtx.font = `${fontSize}px ${fontFamily}`;
    measureCtx.textBaseline = 'top';
    const cellWidth = Math.max(1, measureCtx.measureText('0').width);
    const cellHeight = lineHeight;
    const rasterWidth = Math.max(8, Math.ceil(cellWidth * 4));
    const rasterHeight = Math.max(8, Math.ceil(cellHeight * 4));
    const profiles = {};

    for (const glyph of glyphs) {
      const canvas = document.createElement('canvas');
      canvas.width = rasterWidth;
      canvas.height = rasterHeight;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.clearRect(0, 0, rasterWidth, rasterHeight);
      ctx.fillStyle = '#fff';
      ctx.textBaseline = 'top';
      ctx.font = `${fontSize * 4}px ${fontFamily}`;
      ctx.fillText(glyph, 0, 0);
      const image = ctx.getImageData(0, 0, rasterWidth, rasterHeight);
      const mask = new Float32Array(rasterWidth * rasterHeight);
      for (let i = 0; i < mask.length; i += 1) mask[i] = image.data[i * 4 + 3] / 255;
      const features = analyzeMask(mask, rasterWidth, rasterHeight, patchWidth, patchHeight);
      profiles[glyph] = { ...features, mask, width: rasterWidth, height: rasterHeight };
    }

    return {
      fontFamily,
      fontSize,
      lineHeight,
      cellWidth,
      cellHeight,
      cellAspect: cellWidth / cellHeight,
      profiles,
    };
  }

  return { ALLOWED_GLYPHS, analyzeMask, profileFont };
});
