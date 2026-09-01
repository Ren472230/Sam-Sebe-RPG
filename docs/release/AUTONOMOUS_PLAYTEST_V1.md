# Autonomous Playtest System v1

## Цель

Технический QA выполняется автоматически. Пользователь запускает игру вручную только как Human Experience Gate: оценить интерес, понятность, ощущение живого мира, внешний вид и удовольствие от игрового цикла.

## Источники истины

- `action_events` – канонические действия игрока и квестовые действия.
- `world_events` – события Living World.
- `playtest_events` – только клиентские факты, отсутствующие в канонических журналах: старт сессии, загрузка игры, вход в сцену, открытие диалога, перезагрузка и ошибки браузера.

`SESSION_END` является опциональным. Отчёт восстанавливается без него.

## Автоматические режимы

### Canonical Route

`web/tests/vertical-slice.spec.ts`

Проверяет полный основной цикл: загрузка, таверна, Орен, принятие квеста, 4/5 дров, ожидаемый отказ ранней сдачи, пятые дрова, завершение, награда, reload, WAIT через интерфейс, Living World и итоговый playtest report.

### Exploratory Route

`web/tests/exploratory.spec.ts`

Выполняет 60 детерминированных действий с фиксированным seed. Использует движение, безопасные взаимодействия, WAIT и reload. После каждых пяти действий проверяет основные инварианты состояния. В конце возвращает игрока в исходную локацию.

### Visual QA

Канонический маршрут сохраняет контрольные screenshots ключевых состояний. Playwright дополнительно сохраняет screenshot, trace и video при падении. Browser console и page errors прикладываются как текстовые artifacts.

## Playtest Session Report

API:

- `POST /api/playtest/event`
- `GET /api/playtest/report/{session_id}?commit=<sha>`

Отчёт возвращается как JSON и содержит готовый Markdown в поле `markdown`. В CI канонический маршрут сохраняет оба формата в `web/test-results`.

Ожидаемый игровой отказ `QUEST_TURN_IN / INSUFFICIENT_FIREWOOD` учитывается отдельно и не считается дефектом. Остальные неуспешные backend actions считаются неожиданными отказами.

## Windows Compatibility Gate

`.github/workflows/windows-compatibility.yml` выполняется на `windows-latest` с Python 3.12 после чистой установки. Он проверяет `tzdata`, `ZoneInfo("UTC")`, импорт сервера, создание SQLite, boot backend, `/api/health`, создание session и первый `/api/state`.

## Human Experience Gate

Ручной запуск пользователем имеет смысл только когда одновременно выполнены все условия:

- backend tests PASS;
- Living World acceptance PASS;
- web contract PASS;
- production build PASS;
- canonical browser route PASS;
- exploratory route PASS;
- Windows compatibility PASS;
- P0 = 0;
- P1 = 0;
- playtest report сформирован и имеет `PASS`;
- browser evidence просмотрен при значимых визуальных изменениях.

После зелёного технического gate пользователь оценивает только впечатление от игры.
