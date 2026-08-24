# TASK — Visual Art Direction / Production -> P0 Game Assets

Продолжаем существующий проект «Сам-себе-RPG / Emergent RPG / Living World».

Визуальный стиль уже LOCKED. Это **не новый R&D**.

Технический vertical slice уже проходит полный реальный Chromium-маршрут:

`деревня -> таверна -> Орен -> 5 дров -> сдача -> trust/memory/reward -> reload persistence`.

Сейчас от Visual Production нужен **не concept art**, а первый production-ready пакет файлов для прямой интеграции в игру.

## Источник истины

- MASTER STYLE REFERENCE v1 / VISUAL STYLE BIBLE v1.0;
- `docs/production/visual-asset-handoff-v1.md` — технический контракт.

Не менять визуальное направление и не пересматривать палитру.

## Нужный P0-пакет

Подготовить:

```text
village/
  sky.webp
  far_world.webp
  mid_world.webp
  foreground.webp          optional for first pass

tavern/
  background.webp
  foreground.webp          optional for first pass

characters/
  player.webp
  oren.webp

props/
  firewood.webp

ui/
  dialogue_frame.webp      optional for first pass
```

## Главный технический стандарт

Village full-scene layers:
- одна и та же canvas geometry;
- базовый gameplay canvas 960x540 или точный integer multiple;
- `sky` opaque;
- остальные scene layers transparent;
- слои нельзя tight-crop — они должны совпадать по origin.

Tavern:
- `background` 960x540 или integer multiple;
- optional foreground на том же canvas.

Character/prop exports:
- transparent WebP;
- player — вертикальный cutout, стабильная нижняя foot baseline;
- Oren — то же правило;
- firewood — один крупный читаемый игровой prop без россыпи мелких деталей.

## Gameplay anchors — их надо уважать композицией

Village:
- player start ~ `(430,455)`;
- tavern door / entrance focus ~ `(825,250)`;
- firewood strip ~ `x=112..260`, `y=428..449`;
- well ~ `(485,360)`;
- workshop ~ left side around `(230,264)`.

Tavern:
- player entry ~ `(270,425)`;
- Oren ~ `(650,325)`;
- exit ~ `(110,420)`.

Не надо рисовать красные/технические метки координат — нужно просто строить композицию так, чтобы реальные двери/объекты находились рядом с этими зонами.

## Visual lock

Обязательно сохранить:
- 2.5D physical cardboard theatre / handcrafted diorama;
- крупные формы;
- realistic atmospheric distant natural world + volumetric sky;
- молочно-мраморная + графитовая база;
- заметная фирменная бирюза;
- дозированные алый + чёрный;
- янтарь только как тепло/огонь/свет;
- дозированные удмуртские + армянские мотивы;
- минимум micro-detail;
- никаких нейросетевых россыпей и декоративного мусора;
- никаких dominant brown/beige/green generic medieval grades.

## Очень важный QA

Не отдавать в игру ассет, если есть:
- псевдотекст / случайные буквы;
- дублированные двери/окна/конструкции;
- архитектурные мутации;
- сломанные руки/лицо персонажа;
- floating props;
- лишняя мелкая рябь;
- грязная transparency;
- композиция, где gameplay entrance/character/prop визуально не совпадают с утверждёнными anchors.

## Результат работы этого чата

Не артборд и не ещё одна концепция.

Результат = конкретные final exports, которые можно положить в:

`web/public/assets/production/...`

После передачи Game Core сам подключит их и повторно прогонит production build + полный Chromium acceptance.
