(function () {
  'use strict';

  const THEMES = {
    day: {
      label: 'День',
      weather: 'Лёгкий ветер',
      toggleLabel: '☾ Ночь',
      pressed: 'false',
    },
    night: {
      label: 'Ночь',
      weather: 'Прохладно · лёгкий туман',
      toggleLabel: '☀ День',
      pressed: 'true',
    },
  };

  const S = (cls, text) => ({ cls, text });

  const SCENE_LINES = [
    [S('sky', '         .       .       ~~~        .                   .          ~~~~                  .      ')],
    [S('sky', '    .          ~~~~~              .       .                 .                 .               ')],
    [S('sky', '             .             .                 ~~~                  .                           ')],
    [S('leaf', '     /\\        /\\  /\\                      /\\                 /\\       /\\              ')],
    [S('leaf', '    /^^\\      /^^\\/^^\\      /\\            /^^\\       /\\      /^^\\     /^^\\             ')],
    [S('leaf', '   /^^^^\\    /^^^^^^^^\\    /^^\\          /^^^^\\     /^^\\    /^^^^\\   /^^^^\\            ')],
    [S('leaf', '  /^^^^^^\\  /^^^^^^^^^^\\  /^^^^\\        /^^^^^^\\   /^^^^\\  /^^^^^^\\ /^^^^^^\\           ')],
    [S('ambient', '       '), S('wood', '      __/\\__'), S('ambient', '            '), S('stone', '       ___'), S('ambient', '             '), S('wood', '          _____________'), S('ambient', '                    ')],
    [S('ambient', '   '), S('wood', '___/_______\\___'), S('ambient', '       '), S('stone', '      /___\\'), S('ambient', '       '), S('wood', '       /^^^^^^^^^^^^^\\'), S('ambient', '              ')],
    [S('ambient', '  '), S('wood', '/  ДОМ СТАРОСТЫ  \\'), S('ambient', '     '), S('stone', '     /_____\\'), S('ambient', '      '), S('wood', '     /^^^^^^^^^^^^^^^^^\\'), S('ambient', '           ')],
    [S('ambient', '  '), S('wood', '|  []      []   |'), S('ambient', '     '), S('stone', '     | [] |'), S('ambient', '      '), S('wood', '     |  '), S('focal', 'КУЗНИЦА'), S('wood', '           |'), S('ambient', '           ')],
    [S('ambient', '  '), S('wood', '|      __       |'), S('ambient', '     '), S('stone', '     | __ |'), S('ambient', '      '), S('wood', '     |--------------------|'), S('ambient', '           ')],
    [S('ambient', '  '), S('wood', '|_____|  |______|'), S('ambient', '     '), S('stone', ' ____|_||_|____'), S('ambient', '   '), S('wood', '     |  '), S('hot-light', ' /\\/\\ '), S('wood', '   _|_      |'), S('ambient', '           ')],
    [S('road', '.......................'), S('ambient', '    '), S('stone', '|   КОЛОДЕЦ   |'), S('ambient', '   '), S('wood', '     | '), S('hot-light', ' /^^^^\\ '), S('wood', ' /___\\  '), S('focal', 'МИРА'), S('wood', ' |'), S('ambient', '           ')],
    [S('road', '...........'), S('focal', 'ВОРОН'), S('road', '........'), S('ambient', '    '), S('stone', '|      O      |'), S('ambient', '   '), S('wood', '     |'), S('hot-light', '  |^^^^|  '), S('wood', ' |===|   /|\\  |'), S('ambient', '           ')],
    [S('road', '..........'), S('shadow', '  /\\_  '), S('road', '.......'), S('ambient', '    '), S('stone', '|_____/\\_____|'), S('ambient', '   '), S('wood', '     |'), S('hot-light', '  |____|  '), S('stone', ' |___|  /_|_\\ |'), S('ambient', '           ')],
    [S('road', '.........'), S('shadow', ' (    > '), S('road', '.......'), S('ambient', '    '), S('stone', '   /____\\'), S('ambient', '       '), S('wood', '     |___________|______|'), S('ambient', '           ')],
    [S('wood', '---+------+---'), S('shadow', '--|__/'), S('wood', '---+----------'), S('ambient', '      '), S('road', '..............................................')],
    [S('leaf', '  ,,,   ,,,   ,,,      '), S('road', '......................'), S('ambient', '          '), S('wood', '      _________'), S('ambient', '             ')],
    [S('leaf', ' ,^^^^,^^^^,^^^^,       '), S('road', '..............'), S('focal', ' @ '), S('road', '.......'), S('ambient', '          '), S('wood', ' ____/  ТАВЕРНА  \\____'), S('ambient', '       ')],
    [S('leaf', ',^^^^^^^,^^^^^^^,       '), S('road', '.......................'), S('ambient', '          '), S('wood', '/^^^^^^^^^^^^^^^^^^^^^^\\'), S('ambient', '       ')],
    [S('leaf', '^^^^,^^^^^^,^^^^^       '), S('road', '.......................'), S('ambient', '          '), S('wood', '|  '), S('warm-light', '[]  []  []'), S('wood', '    _____     |'), S('ambient', '       ')],
    [S('leaf', '^^^^^^^,^^^^^^^,        '), S('road', '......................'), S('ambient', '           '), S('wood', '|               |   |     |'), S('ambient', '       ')],
    [S('leaf', ' ,^^^^,  ,^^^^,         '), S('road', '.....................'), S('ambient', '            '), S('wood', '|_____     _____|___|_____|'), S('ambient', '       ')],
    [S('leaf', '   ,,      ,,           '), S('road', '....................'), S('ambient', '             '), S('wood', '   | |     | |   '), S('warm-light', '[ кружка ]'), S('ambient', '      ')],
    [S('wood', '---+---+---+---+---'), S('road', '.....................'), S('wood', '---+---+---+---+---+---+---+---+---')],
    [S('leaf', '  .  .  .     .   .  '), S('road', '....................'), S('leaf', '  .   .   .'), S('ambient', '      '), S('wood', '[X]  [ ]    _|_    [X]'), S('ambient', '        ')],
    [S('leaf', ' ,, ,, ,,,   ,,  ,,, '), S('road', '...................'), S('leaf', ' ,,,  ,,, ,,'), S('ambient', '     '), S('wood', ' |_____|    /___\\   |_|'), S('ambient', '        ')],
    [S('leaf', ',^^,^^,^^^^,^^^^,^^^^,'), S('road', '.................'), S('leaf', ',^^^,^^^^,^^^,'), S('ambient', '   '), S('wood', ' /_____/\\________\\____\\'), S('ambient', '      ')],
    [S('leaf', '^^^^^^^^^^^^^^^^^^^^^^'), S('road', '...............'), S('leaf', '^^^^^^^^^^^^^^^'), S('ambient', '   '), S('shadow', '::::::::::::::::::::::::'), S('ambient', '      ')],
  ];

  function escapeHtml(text) {
    return text
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function getThemeContext(theme) {
    return THEMES[theme] || THEMES.day;
  }

  function nextTheme(theme) {
    return theme === 'day' ? 'night' : 'day';
  }

  function buildSceneHtml() {
    return SCENE_LINES.map((line) => {
      const segments = line.map(({ cls, text }) =>
        `<span class="scene-token ${cls}">${escapeHtml(text)}</span>`
      ).join('');
      return `<div class="ascii-line">${segments}</div>`;
    }).join('');
  }

  function applyTheme(root, label, weather, toggle, theme) {
    const context = getThemeContext(theme);
    root.dataset.theme = theme;
    label.textContent = context.label;
    weather.textContent = context.weather;
    toggle.textContent = context.toggleLabel;
    toggle.setAttribute('aria-pressed', context.pressed);
    return context;
  }

  function selectChoice(buttons, selectedButton) {
    buttons.forEach((button) => {
      const selected = button === selectedButton;
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }

  function initGame(doc) {
    const root = doc.querySelector('#game');
    const scene = doc.querySelector('#scene');
    const label = doc.querySelector('#theme-label');
    const weather = doc.querySelector('#weather-label');
    const toggle = doc.querySelector('#theme-toggle');
    const choices = Array.from(doc.querySelectorAll('.choice'));

    scene.innerHTML = buildSceneHtml();

    toggle.addEventListener('click', () => {
      const theme = nextTheme(root.dataset.theme);
      applyTheme(root, label, weather, toggle, theme);
    });

    choices.forEach((choice) => {
      choice.addEventListener('click', () => selectChoice(choices, choice));
    });
  }

  const api = {
    getThemeContext,
    nextTheme,
    buildSceneHtml,
    applyTheme,
    selectChoice,
    initGame,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => initGame(document));
    } else {
      initGame(document);
    }
  }
})();
