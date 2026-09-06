# Stream Slice v1 — Stream Runbook

## Статус

Stream Slice v1 — демонстрационный vertical slice одного причинно связанного вечера в стартовой деревне.

Проверенный implementation SHA перед фиксацией этого runbook:

`e07472d3e7e3182363ec93518b0707e7fc35d2c1`

Ветка:

`feat/stream-slice-v1`

Draft PR:

`#43 — Stream Slice v1: один живой час в деревне`

Stream mode меняет подачу для зрителя, но не создаёт второй игровой контур: MOVE / WAIT / TAKE / GIVE и диалоги идут через существующий authoritative backend.

## Что нужно на машине

Из корня репозитория должны быть установлены Python- и web-зависимости:

```powershell
python -m pip install -e ".[dev]"
cd web
npm install
cd ..
```

Python: 3.12.
Node.js: 22 рекомендуется и используется в CI.

OpenAI API key опционален. Без ключа Stream Slice работает на детерминированных grounded fallback-репликах. Ошибка или timeout live-провайдера также переводит диалог в fallback вместо остановки игры.

## Чистый запуск

Для новой демонстрации сначала сбросить только изолированную Stream Slice БД:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1 -Reset
```

Затем открыть:

`http://127.0.0.1:5173/?stream=1`

`-Reset` может удалить только:

- `data/stream-slice.sqlite3`;
- `data/stream-slice.sqlite3-wal`;
- `data/stream-slice.sqlite3-shm`.

`data/world.sqlite3` и e2e-БД этим reset не затрагиваются.

## Повторный запуск без сброса

Чтобы продолжить существующее Stream Slice состояние:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1
```

Launcher перед стартом автоматически запускает `scripts/stream_preflight.py`. При нарушении обязательных инвариантов launcher завершится до демонстрации.

## Зафиксированное начало

Stream Slice использует отдельную БД:

`data/stream-slice.sqlite3`

Стартовые часы зафиксированы на:

`2026-08-24 17:00 UTC`

Это сделано для воспроизводимой демонстрации одного и того же causal route.

## Ожидаемые сюжетные beats

В свежей БД ориентир такой:

1. **Шаг 0** — вечер начинается, деревня живёт обычным ритмом.
2. **Около шага 5** — у Миры заканчивается пригодная древесина, она просит помощь.
3. Игрок может пообещать Мире принести древесину. Это знание сначала остаётся у Миры.
4. Каспар до реального контакта с Мирой не знает об обещании игрока.
5. **Около шага 9**, если игрок не перехватил ситуацию, Каспар самостоятельно находит древесину и приносит её Мире. После этого контакта он может узнать от Миры об обещании игрока.
6. **Шаг 10** — в таверну приходит путник Тален с новостью: сильные дожди размыли часть восточной дороги, следующий торговый караван задержится.
7. Орен узнаёт эту новость от Талена и просит принести хлеб для гостя.
8. Хлеб можно подобрать на площади и физически передать Орену через существующие TAKE / GIVE действия.
9. После передачи Орен подтверждает помощь с гостем.
10. После reload социальное знание о новости Талена сохраняется.

Точные реплики могут отличаться при включённом live-провайдере, но факты, причинность и server-side эффекты остаются bounded существующими контрактами.

## Что должен видеть зритель

Использовать именно URL с `?stream=1`.

Stream presentation показывает:

- текущий шаг и фазу вечера;
- кто находится рядом;
- короткие публичные события мира;
- имена NPC, включая `Тален` вместо внутренних actor id;
- обычные игровые действия и свободный диалог.

Зрительский слой не должен показывать raw `npc_*`, `source_knowledge_id`, внутренние relation/trust поля или JSON payloads.

## Быстрое восстановление

### Состояние ушло от демонстрационного маршрута

Остановить launcher и выполнить:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1 -Reset
```

### Порт 8000 или 5173 занят

Остановить ранее запущенный backend/Vite процесс и повторить launcher.

### Live OpenAI недоступен

Продолжать демонстрацию: диалоги должны перейти в локальный grounded fallback. Для гарантированно офлайн-предсказуемого показа запускать без `OPENAI_API_KEY`.

### Launcher остановлен через Ctrl+C

Web server завершается, а backend, запущенный `RUN_STREAM_SLICE.ps1`, останавливается в `finally`.

## Рекомендуемый 60-минутный формат показа

Это host guide, а не заявление о 60 минутах уникального контента.

- 0–5 мин: объяснить, что NPC и мир имеют самостоятельное состояние; показать старт.
- 5–20 мин: довести до просьбы Миры, поговорить с ней и Каспаром, дать миру развиться самостоятельно.
- 20–35 мин: показать последствие реального контакта Миры и Каспара.
- 35–50 мин: встретить Талена, получить дорожную новость, поговорить с Ореном и закрыть хлебный hospitality loop.
- 50–60 мин: reload, повторный разговор с Ореном, свободное исследование и обсуждение того, что сохранилось в мире.

## Проверенная release evidence

Implementation SHA:

`e07472d3e7e3182363ec93518b0707e7fc35d2c1`

На нём GREEN:

- Stream Slice Gate — run `34029136225`;
- Windows Compatibility Gate — run `34029136163`;
- Living World Integration Gate — run `34029136149`;
- Playable Candidate Gate — run `34029136236`;
- Prototype Web CI — run `34029136122`.

Проверки включали:

- full Python suite: `168 passed` на Windows;
- Stream Slice focused Python: `22 passed`;
- Stream Slice preflight до tick 20;
- web contract: `35 passed`;
- production TypeScript/Vite build;
- canonical Chromium route;
- Living NPC Chromium acceptance;
- Social World Chromium acceptance;
- Stream Slice Chromium acceptance;
- SQLite integrity / foreign key / reopen checks;
- Windows backend boot и API state.

Stream Slice evidence artifact:

- artifact id: `9988034448`;
- digest: `sha256:235995086580cdd49e8c80f115efbe348123a946893900eb5fee288c5db0572a`.

В artifact подтверждены пять отдельных кадров:

- `stream-01-opening.png`;
- `stream-02-kaspar-after-contact.png`;
- `stream-03-wayfarer.png`;
- `stream-04-oren-bread.png`;
- `stream-05-reloaded.png`.

В `stream-03-wayfarer.png` заголовок NPC отображается как `Тален`; внутренний `npc_wayfarer_1` в viewer-facing диалоге отсутствует.

## Граница готовности

Этот документ описывает **stream-ready vertical slice**, а не полную RPG.

Стабильность этого build означает, что один воспроизводимый причинный вечер можно показать из отдельной БД с автоматическим preflight, browser acceptance, Windows gate и сохранённой evidence. Расширение контента, боевой системы, прогрессии, новых зон и более широкой emergent simulation остаётся следующими этапами проекта.
