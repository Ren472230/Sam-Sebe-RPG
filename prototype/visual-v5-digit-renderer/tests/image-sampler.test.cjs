const test = require('node:test');
const assert = require('node:assert/strict');
const sampler = require('../image-sampler.js');

test('computeGridGeometry preserves source aspect using measured cell aspect', () => {
  const g = sampler.computeGridGeometry({
    sourceWidth: 1600,
    sourceHeight: 900,
    columns: 240,
    cellAspect: 1,
  });
  assert.equal(g.columns, 240);
  assert.equal(g.rows, 135);
});

test('computeGridGeometry validates dimensions', () => {
  assert.throws(() => sampler.computeGridGeometry({ sourceWidth: 0, sourceHeight: 10, columns: 240, cellAspect: 1 }), /sourceWidth/);
  assert.throws(() => sampler.computeGridGeometry({ sourceWidth: 10, sourceHeight: 10, columns: 0, cellAspect: 1 }), /columns/);
});

test('sampleImageGrid averages more than one source pixel per cell in linear light', () => {
  const rgba = new Uint8ClampedArray([
    255,0,0,255, 0,255,0,255,
    0,0,255,255, 255,255,255,255,
  ]);
  const cells = sampler.sampleImageGrid(
    { data: rgba, width: 2, height: 2 },
    { columns: 1, rows: 1 },
    { patchWidth: 2, patchHeight: 2 }
  );
  assert.equal(cells.length, 1);
  assert.ok(cells[0].rgb[0] > 180 && cells[0].rgb[0] < 195);
  assert.ok(cells[0].variance > 0);
  assert.equal(cells[0].patch.length, 4);
});

test('sampleImageGrid returns stable geometry and normalized features', () => {
  const rgba = new Uint8ClampedArray([
    0,0,0,255, 255,255,255,255,
    0,0,0,255, 255,255,255,255,
  ]);
  const cells = sampler.sampleImageGrid(
    { data: rgba, width: 2, height: 2 },
    { columns: 2, rows: 1 },
    { patchWidth: 2, patchHeight: 2 }
  );
  assert.equal(cells.length, 2);
  assert.deepEqual([cells[0].x, cells[0].y], [0, 0]);
  assert.deepEqual([cells[1].x, cells[1].y], [1, 0]);
  for (const cell of cells) {
    assert.ok(cell.luminance >= 0 && cell.luminance <= 1);
    assert.ok(cell.variance >= 0);
    assert.ok(Number.isFinite(cell.gradientX));
    assert.ok(Number.isFinite(cell.gradientY));
  }
});
