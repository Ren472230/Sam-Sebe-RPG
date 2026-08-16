(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.DigitGlyphMapper = api;
})(typeof window !== 'undefined' ? window : null, function () {
  const CANONICAL_GLYPHS = Object.freeze(['0','1','2','3','4','5','6','7','8','9','.',':','-']);
  const DEFAULT_WEIGHTS = Object.freeze({ density: 0.40, shape: 0.35, edge: 0.20, continuity: 0.05 });
  const DEFAULT_COLOR = Object.freeze({ saturation: 1.20, contrast: 1.08, gamma: 1.00, minBrightness: 0.16 });
  const DEFAULT_DIVERSITY = Object.freeze({ scoreTolerance: 0.028, maxVariance: 0.003, maxGradient: 0.006 });
  const REC709 = [0.2126, 0.7152, 0.0722];

  function clamp(value, min = 0, max = 1) {
    return Math.max(min, Math.min(max, Number.isFinite(value) ? value : min));
  }

  function normalizedWeights(weights) {
    return { ...DEFAULT_WEIGHTS, ...(weights || {}) };
  }

  function meanAbsolutePatchError(a, b) {
    if (!a || !b || !a.length || !b.length) return 1;
    const length = Math.min(a.length, b.length);
    let error = 0;
    for (let i = 0; i < length; i += 1) error += Math.abs(clamp(a[i]) - clamp(b[i]));
    const mismatchPenalty = Math.abs(a.length - b.length) / Math.max(a.length, b.length);
    return clamp((error / length) + mismatchPenalty * 0.25);
  }

  function scoreGlyph(sample, profile, previousGlyph, weights = DEFAULT_WEIGHTS, glyph = null) {
    const w = normalizedWeights(weights);
    const densityError = Math.abs(clamp(sample && sample.luminance) - clamp(profile && profile.density));
    const shapeError = meanAbsolutePatchError(sample && sample.patch, profile && profile.patch);
    const sx = Math.abs(Number(sample && sample.gradientX) || 0);
    const sy = Math.abs(Number(sample && sample.gradientY) || 0);
    const px = Math.abs(Number(profile && profile.edgeX) || 0);
    const py = Math.abs(Number(profile && profile.edgeY) || 0);
    const edgeError = clamp((Math.abs(sx - px) + Math.abs(sy - py)) / 2);
    const continuityPenalty = previousGlyph && glyph && previousGlyph !== glyph ? 1 : 0;
    return (
      densityError * w.density +
      shapeError * w.shape +
      edgeError * w.edge +
      continuityPenalty * w.continuity
    );
  }

  function orderedGlyphs(profiles) {
    const keys = Object.keys(profiles || {});
    const known = CANONICAL_GLYPHS.filter((glyph) => Object.prototype.hasOwnProperty.call(profiles, glyph));
    const extra = keys.filter((glyph) => !CANONICAL_GLYPHS.includes(glyph)).sort();
    return known.concat(extra);
  }

  function scoreOrderedGlyphs(sample, profiles, previousGlyph, weights) {
    return orderedGlyphs(profiles).map((glyph) => ({
      glyph,
      score: scoreGlyph(sample, profiles[glyph], previousGlyph, weights, glyph),
    }));
  }

  function bestScoredGlyph(scored) {
    if (!scored.length) throw new Error('profiles must contain at least one glyph');
    let bestGlyph = scored[0].glyph;
    let bestScore = Number.POSITIVE_INFINITY;
    for (const candidate of scored) {
      if (candidate.score < bestScore - 1e-12) {
        bestScore = candidate.score;
        bestGlyph = candidate.glyph;
      }
    }
    return { glyph: bestGlyph, score: bestScore };
  }

  function chooseGlyph(sample, profiles, previousGlyph = null, weights = DEFAULT_WEIGHTS) {
    return bestScoredGlyph(scoreOrderedGlyphs(sample, profiles, previousGlyph, weights)).glyph;
  }

  function isFlatSample(sample, diversity = DEFAULT_DIVERSITY) {
    const d = { ...DEFAULT_DIVERSITY, ...(diversity || {}) };
    const variance = Math.max(0, Number(sample && sample.variance) || 0);
    const gx = Number(sample && sample.gradientX) || 0;
    const gy = Number(sample && sample.gradientY) || 0;
    const gradient = Math.hypot(gx, gy);
    return variance <= d.maxVariance && gradient <= d.maxGradient;
  }

  function deterministicIndex(x, y, length) {
    if (length <= 1) return 0;
    let value = Math.imul((Number(x) || 0) + 1, 0x9e3779b1) ^ Math.imul((Number(y) || 0) + 1, 0x85ebca77);
    value ^= value >>> 16;
    value = Math.imul(value, 0x7feb352d);
    value ^= value >>> 15;
    value = Math.imul(value, 0x846ca68b);
    value ^= value >>> 16;
    return (value >>> 0) % length;
  }

  function chooseGlyphForCell(sample, profiles, previousGlyph = null, weights = DEFAULT_WEIGHTS, diversity = DEFAULT_DIVERSITY) {
    const strictScored = scoreOrderedGlyphs(sample, profiles, previousGlyph, weights);
    const strictBest = bestScoredGlyph(strictScored);
    if (!isFlatSample(sample, diversity)) return strictBest.glyph;

    const d = { ...DEFAULT_DIVERSITY, ...(diversity || {}) };
    const tolerance = Math.max(0, Number(d.scoreTolerance) || 0);
    const flatWeights = { ...normalizedWeights(weights), continuity: 0 };
    const flatScored = scoreOrderedGlyphs(sample, profiles, null, flatWeights);
    const flatBest = bestScoredGlyph(flatScored);
    const candidates = flatScored
      .filter((candidate) => candidate.score <= flatBest.score + tolerance + 1e-12)
      .map((candidate) => candidate.glyph);

    if (candidates.length < 2) return strictBest.glyph;
    return candidates[deterministicIndex(sample && sample.x, sample && sample.y, candidates.length)];
  }

  function correctForegroundColor(rgb, tuning = DEFAULT_COLOR) {
    const t = { ...DEFAULT_COLOR, ...(tuning || {}) };
    let channels = [0, 1, 2].map((i) => clamp((Number(rgb && rgb[i]) || 0) / 255));
    const luminance = channels[0] * REC709[0] + channels[1] * REC709[1] + channels[2] * REC709[2];
    channels = channels.map((c) => clamp(luminance + (c - luminance) * t.saturation));
    channels = channels.map((c) => clamp(0.5 + (c - 0.5) * t.contrast));
    const gamma = Number.isFinite(t.gamma) && t.gamma > 0 ? t.gamma : 1;
    channels = channels.map((c) => clamp(Math.pow(c, 1 / gamma)));
    const maxChannel = Math.max(...channels);
    const minBrightness = clamp(t.minBrightness);
    if (maxChannel > 0 && maxChannel < minBrightness) {
      const scale = minBrightness / maxChannel;
      channels = channels.map((c) => clamp(c * scale));
    } else if (maxChannel === 0 && minBrightness > 0) {
      channels = [minBrightness, minBrightness, minBrightness];
    }
    return channels.map((c) => Math.round(c * 255));
  }

  function markerIndex(marker, columns, rows) {
    if (!marker) return -1;
    const nx = clamp(Number(marker.normalizedX));
    const ny = clamp(Number(marker.normalizedY));
    const x = Math.min(columns - 1, Math.max(0, Math.round(nx * (columns - 1))));
    const y = Math.min(rows - 1, Math.max(0, Math.round(ny * (rows - 1))));
    return y * columns + x;
  }

  function mapSamples(samples, profiles, options = {}) {
    if (!Array.isArray(samples)) throw new TypeError('samples must be an array');
    const columns = Math.max(1, Math.round(options.columns || (samples.length ? Math.max(...samples.map((s) => s.x)) + 1 : 1)));
    const rows = Math.max(1, Math.round(options.rows || Math.ceil(samples.length / columns)));
    const weights = { ...DEFAULT_WEIGHTS, ...(options.weights || {}) };
    const color = { ...DEFAULT_COLOR, ...(options.color || {}) };
    const diversity = options.diversity === false ? false : { ...DEFAULT_DIVERSITY, ...(options.diversity || {}) };
    const cells = [];
    let previousGlyph = null;
    for (const sample of samples) {
      const glyph = diversity
        ? chooseGlyphForCell(sample, profiles, previousGlyph, weights, diversity)
        : chooseGlyph(sample, profiles, previousGlyph, weights);
      cells.push({
        x: sample.x,
        y: sample.y,
        glyph,
        color: correctForegroundColor(sample.rgb, color),
      });
      previousGlyph = glyph;
    }

    const index = markerIndex(options.marker, columns, rows);
    if (index >= 0) {
      const target = cells.find((cell) => cell.y * columns + cell.x === index);
      if (target) {
        target.glyph = options.marker.glyph || '@';
        target.color = Array.isArray(options.marker.color) ? options.marker.color.slice(0, 3) : [255, 240, 170];
      }
    }
    return cells;
  }

  return {
    CANONICAL_GLYPHS,
    DEFAULT_WEIGHTS,
    DEFAULT_COLOR,
    DEFAULT_DIVERSITY,
    scoreGlyph,
    chooseGlyph,
    chooseGlyphForCell,
    isFlatSample,
    correctForegroundColor,
    mapSamples,
  };
});
