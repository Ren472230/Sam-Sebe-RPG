(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.DigitTextRenderer = api;
})(typeof window !== 'undefined' ? window : null, function () {
  function groupCellsIntoRows(cells, columns) {
    if (!Array.isArray(cells)) throw new TypeError('cells must be an array');
    if (!Number.isInteger(columns) || columns <= 0) throw new TypeError('columns must be a positive integer');
    if (!cells.length) return [];
    const maxY = Math.max(...cells.map((cell) => Number(cell.y) || 0));
    const rows = Array.from({ length: maxY + 1 }, () => Array(columns));
    for (const cell of cells) {
      const x = Number(cell.x);
      const y = Number(cell.y);
      if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || x >= columns || y < 0) continue;
      rows[y][x] = cell;
    }
    return rows.map((row, y) => row.map((cell, x) => cell || { x, y, glyph: ' ', color: [0, 0, 0] }));
  }

  function rgbCss(color) {
    const rgb = [0, 1, 2].map((i) => Math.max(0, Math.min(255, Math.round(Number(color && color[i]) || 0))));
    return `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]})`;
  }

  function renderTextGrid(root, cells, {
    columns,
    rows,
    cellWidth,
    cellHeight,
    fontFamily,
    fontSize,
    lineHeight,
    background = '#050608',
  }) {
    if (!root || typeof root.replaceChildren !== 'function') throw new TypeError('root must be a DOM element');
    if (!Number.isInteger(columns) || columns <= 0) throw new TypeError('columns must be a positive integer');
    if (!Number.isInteger(rows) || rows <= 0) throw new TypeError('rows must be a positive integer');
    const grouped = groupCellsIntoRows(cells, columns);
    const frame = document.createDocumentFragment();

    root.classList.add('digit-grid');
    root.style.setProperty('--grid-columns', String(columns));
    root.style.setProperty('--grid-rows', String(rows));
    root.style.setProperty('--cell-width', `${cellWidth}px`);
    root.style.setProperty('--cell-height', `${cellHeight}px`);
    root.style.setProperty('--digit-grid-background', background);
    root.style.fontFamily = fontFamily;
    root.style.fontSize = `${fontSize}px`;
    root.style.lineHeight = `${lineHeight}px`;

    for (let y = 0; y < rows; y += 1) {
      const rowElement = document.createElement('div');
      rowElement.className = 'glyph-row';
      rowElement.setAttribute('role', 'presentation');
      const rowFragment = document.createDocumentFragment();
      const row = grouped[y] || [];
      for (let x = 0; x < columns; x += 1) {
        const cell = row[x] || { x, y, glyph: ' ', color: [0, 0, 0] };
        const span = document.createElement('span');
        span.className = 'glyph-cell';
        span.textContent = cell.glyph;
        span.dataset.glyph = cell.glyph;
        span.style.width = `${cellWidth}px`;
        span.style.height = `${cellHeight}px`;
        span.style.color = rgbCss(cell.color);
        rowFragment.appendChild(span);
      }
      rowElement.appendChild(rowFragment);
      frame.appendChild(rowElement);
    }
    root.replaceChildren(frame);
    return root;
  }

  return { groupCellsIntoRows, renderTextGrid };
});
