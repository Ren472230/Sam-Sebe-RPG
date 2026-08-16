(function (root, factory) {
  const api = factory(root);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) {
    root.DigitLabApp = api;
    root.addEventListener('DOMContentLoaded', () => api.initDigitLab(root.document));
  }
})(typeof window !== 'undefined' ? window : null, function (root) {
  const DEFAULTS = Object.freeze({
    columns: 240,
    zoom: 1,
    fontFamily: '"DejaVu Sans Mono", "Cascadia Mono", "SFMono-Regular", Consolas, monospace',
    fontSize: 8,
    lineHeight: 8,
    density: 0.40,
    shape: 0.35,
    edge: 0.20,
    continuity: 0.05,
    saturation: 1.35,
    contrast: 1.08,
    gamma: 1.00,
    minBrightness: 0.16,
    showMarker: true,
    showSource: false,
    background: '#050608',
  });

  function number(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function bool(value, fallback = false) {
    if (typeof value === 'boolean') return value;
    if (value === 'on' || value === 'true' || value === '1' || value === 1) return true;
    if (value === 'off' || value === 'false' || value === '0' || value === 0 || value == null) return false;
    return fallback;
  }

  function buildSettings(formValues = {}) {
    const get = (key, fallback) => {
      if (formValues && typeof formValues.get === 'function') {
        const value = formValues.get(key);
        return value == null ? fallback : value;
      }
      return Object.prototype.hasOwnProperty.call(formValues, key) ? formValues[key] : fallback;
    };
    const showMarker = bool(get('showMarker', DEFAULTS.showMarker), DEFAULTS.showMarker);
    return {
      columns: Math.max(1, Math.round(number(get('columns', DEFAULTS.columns), DEFAULTS.columns))),
      zoom: Math.max(0.2, Math.min(3, number(get('zoom', DEFAULTS.zoom * 100), DEFAULTS.zoom * 100) / 100)),
      font: {
        fontFamily: String(get('fontFamily', DEFAULTS.fontFamily)),
        fontSize: number(get('fontSize', DEFAULTS.fontSize), DEFAULTS.fontSize),
        lineHeight: number(get('lineHeight', DEFAULTS.lineHeight), DEFAULTS.lineHeight),
      },
      patch: { patchWidth: 4, patchHeight: 6 },
      weights: {
        density: number(get('density', DEFAULTS.density), DEFAULTS.density),
        shape: number(get('shape', DEFAULTS.shape), DEFAULTS.shape),
        edge: number(get('edge', DEFAULTS.edge), DEFAULTS.edge),
        continuity: number(get('continuity', DEFAULTS.continuity), DEFAULTS.continuity),
      },
      color: {
        saturation: number(get('saturation', DEFAULTS.saturation), DEFAULTS.saturation),
        contrast: number(get('contrast', DEFAULTS.contrast), DEFAULTS.contrast),
        gamma: number(get('gamma', DEFAULTS.gamma), DEFAULTS.gamma),
        minBrightness: number(get('minBrightness', DEFAULTS.minBrightness), DEFAULTS.minBrightness),
      },
      marker: showMarker ? { normalizedX: 0.68, normalizedY: 0.76, glyph: '@', color: [255, 240, 170] } : null,
      showSource: bool(get('showSource', DEFAULTS.showSource), DEFAULTS.showSource),
      background: DEFAULTS.background,
    };
  }

  function resolveBenchmarkUrl(options = {}) {
    return options && options.benchmarkUrl
      ? String(options.benchmarkUrl)
      : 'assets/benchmark-day.png';
  }

  function computeFitZoom({ availableWidth, outputWidth, minZoom = 0.2, maxZoom = 1 }) {
    if (!Number.isFinite(availableWidth) || availableWidth <= 0) {
      throw new TypeError('availableWidth must be positive');
    }
    if (!Number.isFinite(outputWidth) || outputWidth <= 0) {
      throw new TypeError('outputWidth must be positive');
    }
    return Math.max(minZoom, Math.min(maxZoom, availableWidth / outputWidth));
  }

  function computeStageAvailableWidth({ rectWidth, paddingLeft = 0, paddingRight = 0 }) {
    if (!Number.isFinite(rectWidth) || rectWidth <= 0) {
      throw new TypeError('rectWidth must be positive');
    }
    return Math.max(1, rectWidth - Math.max(0, paddingLeft) - Math.max(0, paddingRight));
  }

  function selectPreRenderZoom({ autoFit, isMobile, requestedZoom }) {
    return autoFit && isMobile ? 1 : requestedZoom;
  }

  function formObject(form) {
    const values = {};
    for (const element of form.elements) {
      if (!element.name) continue;
      if (element.type === 'checkbox') values[element.name] = element.checked;
      else if (element.type !== 'file') values[element.name] = element.value;
    }
    return values;
  }

  function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.decoding = 'async';
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(`Could not load source image: ${url}`));
      image.src = url;
    });
  }

  function setText(doc, id, text) {
    const node = doc.getElementById(id);
    if (node) node.textContent = String(text);
  }

  function updateControlOutputs(doc, settings) {
    setText(doc, 'columns-value', settings.columns);
    setText(doc, 'zoom-value', `${Math.round(settings.zoom * 100)}%`);
    setText(doc, 'font-size-value', settings.font.fontSize.toFixed(1).replace('.0', ''));
    setText(doc, 'line-height-value', settings.font.lineHeight.toFixed(1).replace('.0', ''));
    for (const key of ['density', 'shape', 'edge', 'continuity']) setText(doc, `${key}-value`, settings.weights[key].toFixed(2));
    for (const key of ['saturation', 'contrast', 'gamma']) setText(doc, `${key}-value`, settings.color[key].toFixed(2));
    setText(doc, 'min-brightness-value', settings.color.minBrightness.toFixed(2));
  }

  function initDigitLab(doc, options = {}) {
    if (!doc) throw new TypeError('document is required');
    const required = ['DigitGlyphProfiler', 'DigitImageSampler', 'DigitGlyphMapper', 'DigitTextRenderer'];
    for (const name of required) {
      if (!root || !root[name]) throw new Error(`${name} is not loaded`);
    }

    const form = doc.getElementById('controls');
    const output = doc.getElementById('digit-output');
    const stageScroll = doc.getElementById('stage-scroll');
    const debugPanel = doc.getElementById('source-debug-panel');
    const sourcePreview = doc.getElementById('source-preview');
    const fileInput = doc.getElementById('source-file');
    const renderButton = doc.getElementById('render-now');
    if (!form || !output || !stageScroll || !debugPanel || !sourcePreview || !fileInput || !renderButton) {
      throw new Error('Digit lab markup is incomplete');
    }

    const sourceCanvas = doc.createElement('canvas');
    const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true });
    const cache = {
      sourceImage: null,
      sourceSerial: 0,
      sourceObjectUrl: null,
      profileKey: null,
      font: null,
      samplingKey: null,
      geometry: null,
      samples: null,
      autoFit: true,
    };

    function currentSettings() {
      return buildSettings(formObject(form));
    }

    function invalidateSampling() {
      cache.samplingKey = null;
      cache.geometry = null;
      cache.samples = null;
    }

    function invalidateProfile() {
      cache.profileKey = null;
      cache.font = null;
      invalidateSampling();
    }

    async function setSource(url, isObjectUrl = false) {
      setText(doc, 'render-status', 'Loading source…');
      const image = await loadImage(url);
      if (cache.sourceObjectUrl) URL.revokeObjectURL(cache.sourceObjectUrl);
      cache.sourceObjectUrl = isObjectUrl ? url : null;
      cache.sourceImage = image;
      cache.sourceSerial += 1;
      sourcePreview.src = url;
      sourceCanvas.width = image.naturalWidth;
      sourceCanvas.height = image.naturalHeight;
      sourceContext.clearRect(0, 0, sourceCanvas.width, sourceCanvas.height);
      sourceContext.drawImage(image, 0, 0);
      invalidateSampling();
      await render();
    }

    async function ensureProfile(settings) {
      const key = JSON.stringify(settings.font);
      if (cache.profileKey !== key || !cache.font) {
        cache.font = await Promise.resolve(root.DigitGlyphProfiler.profileFont(settings.font));
        cache.profileKey = key;
        invalidateSampling();
      }
      return cache.font;
    }

    async function ensureSamples(settings, font) {
      const image = cache.sourceImage;
      if (!image) throw new Error('No source image loaded');
      const geometry = root.DigitImageSampler.computeGridGeometry({
        sourceWidth: image.naturalWidth,
        sourceHeight: image.naturalHeight,
        columns: settings.columns,
        cellAspect: font.cellAspect,
      });
      const key = JSON.stringify({
        source: cache.sourceSerial,
        columns: geometry.columns,
        rows: geometry.rows,
        cellAspect: geometry.cellAspect,
        patch: settings.patch,
      });
      if (cache.samplingKey !== key || !cache.samples) {
        const imageData = sourceContext.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
        cache.samples = root.DigitImageSampler.sampleImageGrid(
          { data: imageData.data, width: imageData.width, height: imageData.height },
          geometry,
          settings.patch,
        );
        cache.samplingKey = key;
        cache.geometry = geometry;
      }
      return { geometry: cache.geometry, samples: cache.samples };
    }

    async function render() {
      if (!cache.sourceImage) return;
      const settings = currentSettings();
      updateControlOutputs(doc, settings);
      debugPanel.hidden = !settings.showSource;
      const isMobile = Boolean(root.matchMedia && root.matchMedia('(max-width: 940px)').matches);
      output.style.zoom = String(selectPreRenderZoom({
        autoFit: cache.autoFit,
        isMobile,
        requestedZoom: settings.zoom,
      }));
      setText(doc, 'render-status', 'Rendering real glyphs…');
      const started = performance.now();
      try {
        const font = await ensureProfile(settings);
        const { geometry, samples } = await ensureSamples(settings, font);
        const cells = root.DigitGlyphMapper.mapSamples(samples, font.profiles, {
          weights: settings.weights,
          color: settings.color,
          columns: geometry.columns,
          rows: geometry.rows,
          marker: settings.marker,
        });
        root.DigitTextRenderer.renderTextGrid(output, cells, {
          ...geometry,
          ...font,
          background: settings.background,
        });
        if (cache.autoFit && isMobile) {
          const stageStyle = root.getComputedStyle(stageScroll);
          const availableWidth = computeStageAvailableWidth({
            rectWidth: stageScroll.getBoundingClientRect().width,
            paddingLeft: parseFloat(stageStyle.paddingLeft) || 0,
            paddingRight: parseFloat(stageStyle.paddingRight) || 0,
          });
          const fitZoom = computeFitZoom({ availableWidth, outputWidth: output.offsetWidth });
          const zoomControl = doc.getElementById('zoom');
          output.style.zoom = String(fitZoom);
          if (zoomControl) zoomControl.value = String(Math.floor(fitZoom * 100));
          setText(doc, 'zoom-value', `${Math.floor(fitZoom * 100)}%`);
        }
        const elapsed = performance.now() - started;
        setText(doc, 'status-columns', geometry.columns);
        setText(doc, 'status-rows', geometry.rows);
        setText(doc, 'status-aspect', font.cellAspect.toFixed(3));
        setText(doc, 'status-font', settings.font.fontFamily.split(',')[0].replaceAll('"', ''));
        setText(doc, 'status-duration', elapsed.toFixed(0));
        setText(doc, 'render-status', `${cells.length.toLocaleString()} selectable glyph cells`);
      } catch (error) {
        console.error(error);
        setText(doc, 'render-status', `Render failed: ${error.message}`);
      }
    }

    const scheduleRender = debounce(() => render(), 120);
    form.addEventListener('input', (event) => {
      const target = event.target;
      const settings = currentSettings();
      updateControlOutputs(doc, settings);
      debugPanel.hidden = !settings.showSource;
      if (target && (target.name === 'fontSize' || target.name === 'lineHeight')) invalidateProfile();
      if (target && target.name === 'columns') invalidateSampling();
      if (target && target.name === 'zoom') {
        cache.autoFit = false;
        output.style.zoom = String(settings.zoom);
        return;
      }
      if (target && target.name === 'showSource') return;
      scheduleRender();
    });

    renderButton.addEventListener('click', () => render());
    form.addEventListener('reset', () => {
      setTimeout(() => {
        cache.autoFit = true;
        invalidateProfile();
        render();
      }, 0);
    });

    fileInput.addEventListener('change', async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      await setSource(url, true);
    });

    setSource(resolveBenchmarkUrl(options)).catch((error) => {
      console.error(error);
      setText(doc, 'render-status', error.message);
    });

    return { render, setSource, cache };
  }

  return {
    DEFAULTS,
    buildSettings,
    initDigitLab,
    resolveBenchmarkUrl,
    computeFitZoom,
    computeStageAvailableWidth,
    selectPreRenderZoom,
  };
});
