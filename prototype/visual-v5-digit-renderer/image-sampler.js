(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.DigitImageSampler = api;
})(typeof window !== 'undefined' ? window : null, function () {
  const REC709 = [0.2126, 0.7152, 0.0722];

  function assertPositiveNumber(value, name) {
    if (!Number.isFinite(value) || value <= 0) {
      throw new TypeError(`${name} must be a positive finite number`);
    }
  }

  function srgbChannelToLinear(v) {
    const c = Math.max(0, Math.min(1, v));
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }

  function linearChannelToSrgb(v) {
    const c = Math.max(0, Math.min(1, v));
    return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
  }

  function linearLuminance(rgbLinear) {
    return rgbLinear[0] * REC709[0] + rgbLinear[1] * REC709[1] + rgbLinear[2] * REC709[2];
  }

  function computeGridGeometry({ sourceWidth, sourceHeight, columns = 240, cellAspect }) {
    assertPositiveNumber(sourceWidth, 'sourceWidth');
    assertPositiveNumber(sourceHeight, 'sourceHeight');
    assertPositiveNumber(columns, 'columns');
    assertPositiveNumber(cellAspect, 'cellAspect');
    const normalizedColumns = Math.max(1, Math.round(columns));
    const sourceAspect = sourceWidth / sourceHeight;
    const rows = Math.max(1, Math.round((normalizedColumns * cellAspect) / sourceAspect));
    return { columns: normalizedColumns, rows, sourceAspect, cellAspect };
  }

  function validateImage(image) {
    if (!image || !(image.data instanceof Uint8ClampedArray)) {
      throw new TypeError('image.data must be a Uint8ClampedArray');
    }
    assertPositiveNumber(image.width, 'width');
    assertPositiveNumber(image.height, 'height');
    if (image.data.length < image.width * image.height * 4) {
      throw new RangeError('image.data is smaller than width * height * 4');
    }
  }

  function getLinearPixel(image, x, y) {
    const ix = Math.max(0, Math.min(image.width - 1, x));
    const iy = Math.max(0, Math.min(image.height - 1, y));
    const i = (iy * image.width + ix) * 4;
    const alpha = image.data[i + 3] / 255;
    return [
      srgbChannelToLinear((image.data[i] / 255) * alpha),
      srgbChannelToLinear((image.data[i + 1] / 255) * alpha),
      srgbChannelToLinear((image.data[i + 2] / 255) * alpha),
    ];
  }

  function averageRegion(image, x0, y0, x1, y1) {
    const startX = Math.max(0, Math.floor(x0));
    const startY = Math.max(0, Math.floor(y0));
    const endX = Math.min(image.width, Math.max(startX + 1, Math.ceil(x1)));
    const endY = Math.min(image.height, Math.max(startY + 1, Math.ceil(y1)));
    const sum = [0, 0, 0];
    let count = 0;
    for (let y = startY; y < endY; y += 1) {
      for (let x = startX; x < endX; x += 1) {
        const p = getLinearPixel(image, x, y);
        sum[0] += p[0];
        sum[1] += p[1];
        sum[2] += p[2];
        count += 1;
      }
    }
    if (!count) return [0, 0, 0];
    return [sum[0] / count, sum[1] / count, sum[2] / count];
  }

  function regionPatch(image, x0, y0, x1, y1, patchWidth, patchHeight) {
    const patch = new Float32Array(patchWidth * patchHeight);
    const regionWidth = Math.max(1e-9, x1 - x0);
    const regionHeight = Math.max(1e-9, y1 - y0);
    for (let py = 0; py < patchHeight; py += 1) {
      for (let px = 0; px < patchWidth; px += 1) {
        const sx0 = x0 + (px / patchWidth) * regionWidth;
        const sx1 = x0 + ((px + 1) / patchWidth) * regionWidth;
        const sy0 = y0 + (py / patchHeight) * regionHeight;
        const sy1 = y0 + ((py + 1) / patchHeight) * regionHeight;
        const rgbLinear = averageRegion(image, sx0, sy0, sx1, sy1);
        patch[py * patchWidth + px] = linearLuminance(rgbLinear);
      }
    }
    return patch;
  }

  function computeVariance(patch) {
    if (!patch.length) return 0;
    let mean = 0;
    for (const v of patch) mean += v;
    mean /= patch.length;
    let sum = 0;
    for (const v of patch) {
      const d = v - mean;
      sum += d * d;
    }
    return sum / patch.length;
  }

  function computeGradients(patch, width, height) {
    if (width < 2 || height < 2) return [0, 0];
    let gx = 0;
    let gy = 0;
    let gxCount = 0;
    let gyCount = 0;
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width - 1; x += 1) {
        gx += patch[y * width + x + 1] - patch[y * width + x];
        gxCount += 1;
      }
    }
    for (let y = 0; y < height - 1; y += 1) {
      for (let x = 0; x < width; x += 1) {
        gy += patch[(y + 1) * width + x] - patch[y * width + x];
        gyCount += 1;
      }
    }
    return [gxCount ? gx / gxCount : 0, gyCount ? gy / gyCount : 0];
  }

  function sampleImageGrid(image, geometry, { patchWidth = 4, patchHeight = 6 } = {}) {
    validateImage(image);
    assertPositiveNumber(geometry && geometry.columns, 'columns');
    assertPositiveNumber(geometry && geometry.rows, 'rows');
    assertPositiveNumber(patchWidth, 'patchWidth');
    assertPositiveNumber(patchHeight, 'patchHeight');

    const columns = Math.max(1, Math.round(geometry.columns));
    const rows = Math.max(1, Math.round(geometry.rows));
    const pw = Math.max(1, Math.round(patchWidth));
    const ph = Math.max(1, Math.round(patchHeight));
    const cells = new Array(columns * rows);

    for (let gy = 0; gy < rows; gy += 1) {
      const y0 = (gy * image.height) / rows;
      const y1 = ((gy + 1) * image.height) / rows;
      for (let gx = 0; gx < columns; gx += 1) {
        const x0 = (gx * image.width) / columns;
        const x1 = ((gx + 1) * image.width) / columns;
        const avgLinear = averageRegion(image, x0, y0, x1, y1);
        const patch = regionPatch(image, x0, y0, x1, y1, pw, ph);
        const [gradientX, gradientY] = computeGradients(patch, pw, ph);
        cells[gy * columns + gx] = {
          x: gx,
          y: gy,
          rgb: avgLinear.map((v) => Math.round(linearChannelToSrgb(v) * 255)),
          luminance: linearLuminance(avgLinear),
          variance: computeVariance(patch),
          gradientX,
          gradientY,
          patch: Array.from(patch),
        };
      }
    }
    return cells;
  }

  return {
    computeGridGeometry,
    sampleImageGrid,
    srgbChannelToLinear,
    linearChannelToSrgb,
  };
});
