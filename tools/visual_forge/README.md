# REN Visual Forge — бесплатный первый контур

Этот инструмент не является отдельной нейросетью. Его задача — сделать производство визуала для `Sam-Sebe-RPG` управляемым и воспроизводимым.

## Принцип

1. ChatGPT создаёт или локально редактирует один отдельный PNG-ассет.
2. Принятый ассет фиксируется и больше не перерисовывается целиком без причины.
3. Python выполняет детерминированные операции: инспекция, маски, проверка изменений и сборка слоёв.
4. GitHub хранит версии и автоматически проверяет production-слои.
5. Платные внешние API не входят в обязательный контур.

## Команды

Проверить PNG/WebP:

```bash
python tools/visual_forge/visual_forge.py inspect path/to/asset.png
```

Проверить локальную правку. Любой изменённый пиксель вне маски даёт ненулевой код возврата:

```bash
python tools/visual_forge/visual_forge.py validate-edit original.png edited.png mask.png
```

Собрать сцену из независимых слоёв:

```bash
python tools/visual_forge/visual_forge.py compose scene.json output.png
```

Собрать проверочный кадр прямо из текущего production-манифеста:

```bash
python tools/visual_forge/visual_forge.py compose-production-preview --root . --output visual-forge-preview.png
```

Проверить активный production-манифест проекта:

```bash
python tools/visual_forge/visual_forge.py verify-production --root .
```

Проверить реестр 14 канонических слотов:

```bash
python tools/visual_forge/visual_forge.py verify-registry web/public/assets/production/visual_forge_registry.json
```

## Формат scene.json

```json
{
  "canvas": {
    "width": 960,
    "height": 540,
    "background": [0, 0, 0, 0]
  },
  "layers": [
    {"path": "sky.png", "x": 0, "y": 0, "z": 0},
    {"path": "tavern.png", "x": 600, "y": 220, "z": 30, "scale": 0.6}
  ]
}
```

Сортировка идёт по `z`, а при одинаковом `z` — по исходному порядку в JSON. Результат сохраняется как RGBA PNG.

## Что проверяет автоматический gate

- тесты Visual Forge;
- наличие всех файлов, на которые реально ссылается production `manifest.json`;
- возможность открыть каждый активный PNG/WebP через Pillow;
- целостность реестра ровно из 14 канонических ID;
- отсутствие дублирующихся/неизвестных canonical ID в реестре;
- сборку реального preview из текущих материализованных village-слоёв.

## Что намеренно не входит в первую версию

- платные генеративные API;
- ComfyUI;
- SAM/Hunyuan/RevealLayer как обязательные зависимости;
- автоматическая перерисовка целой сцены;
- автоматическое объявление исторического ассета физически существующим, если его байтов нет в репозитории.

Если позже потребуется тяжёлая сегментация или 3D, это подключается как необязательный слой, не меняя контракт ассетов и проверок.
