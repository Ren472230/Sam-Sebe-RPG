# Living Conversation v2 — Release Runbook

## Статус

Living Conversation v2 — stacked release candidate поверх проверенного Stream Slice v1.

Ветка:

`feat/living-conversation-v2`

Draft PR:

`#45 — Living Conversation v2: живые NPC-разговоры`

Base branch:

`feat/stream-slice-v1`

PR остаётся draft и unmerged. Merge требует отдельного явного решения.

Цель v2 — сделать разговоры с Ореном, Мирой, Каспаром и Таленом менее похожими на универсального чат-бота и сильнее привязать речь к личности, текущему состоянию, отношениям, знаниям и общей истории конкретной пары NPC ↔ игрок.

## Что добавляет v2

### Различимые голоса

Для каждого из четырёх NPC задан отдельный voice profile:

- ценности;
- темперамент;
- стиль юмора;
- симпатии и антипатии;
- предпочтения в разговоре;
- избегаемые темы;
- сигналы теплоты;
- поведение в конфликте;
- характерные обороты;
- запрещённые assistant-like фразы;
- типичная длина ответа.

### Субъективное внутреннее состояние

Реплика строится не только из факта мира. Контекст содержит детерминированное текущее состояние NPC:

- mood;
- secondary mood;
- current concern;
- current desire;
- availability;
- subjective stance.

Один и тот же внешний факт не обязан означать одно и то же для разных NPC. Например, задержка каравана для Орена — риск снабжения, для Талена — лично увиденный дорожный факт, а Каспар и Мира сохраняют собственные приоритеты.

### Поведение отношений

Внутренний relation vector преобразуется в поведенческий режим (`guarded`, `neutral`, `comfortable`, `warm`, `distrustful`, `hostile`). Модель может учитывать этот режим, но viewer-facing API не публикует raw relationship numbers.

### Память конкретной пары

`conversation_memories` принадлежат конкретной паре NPC ↔ игрок.

Игрок может сообщить Мире личный факт, и этот факт не появляется автоматически в контексте Каспара. Это отдельный слой от world knowledge и не превращает слова игрока в объективную истину мира.

### Незавершённые темы и callback

Хранятся:

- open threads;
- pending question;
- last topic;
- turn count;
- last interaction tick.

После пересоздания `DialogueService` незавершённая тема остаётся доступной и может стать grounded initiative при следующем контакте.

### Инициатива NPC

NPC получает право начать или продолжить тему только из подтверждённого основания:

- незакрытый вопрос;
- актуальная просьба;
- собственное состояние;
- известный ему факт;
- собственное недавнее событие.

Отсутствие основания не даёт права выдумывать новый world fact.

### Conversation acts

Поддерживаются bounded типы ответа:

- `answer`;
- `ask`;
- `challenge`;
- `refuse`;
- `tease`;
- `observe`;
- `recall`;
- `redirect`.

NPC может отказывать, спорить, менять тему или отвечать коротко вместо обязательного согласия и обязательного вопроса в конце.

## Anti-chatbot rules

Live provider получает явные ограничения:

- оставаться персонажем мира, а не сервисным ассистентом;
- не использовать шаблоны вроде «интересный вопрос» и «чем я могу помочь»;
- не соглашаться автоматически;
- не заканчивать каждый ответ вопросом;
- не превращать обычную речь в списки;
- не пересказывать вопрос игрока;
- не объяснять собственный personality profile;
- не выдумывать инвентарь, награды, завершённые действия, локации, приватные разговоры или world facts.

## Offline fallback v2

Без `OPENAI_API_KEY`, при timeout или ошибке live provider игра продолжает работать через deterministic grounded fallback.

Обычные fallback-реплики теперь выбираются из небольших state-aware пулов:

- текущий authoritative state выбирает смысловой пул;
- relationship behavior детерминированно сдвигает вариант;
- pair turn count меняет формулировку;
- предыдущая реплика исключается, если в пуле есть другой вариант.

Рандом и скрытое глобальное состояние не используются.

Критические Stream Slice факты остаются каноническими и grounded: обещание Мире, источник знания Каспара, дорожная новость Талена и Орена, хлебный hospitality loop.

## Публичная граница API

`POST /api/dialogue` сохраняет frozen viewer-facing контракт из пяти полей:

- `text`;
- `proposal`;
- `used_fallback`;
- `social_action`;
- `npc_id`.

Внутренние поля `conversation_act`, `memory_candidates`, `relationship_behavior`, relation vector, trust и другие числовые параметры отношений наружу не публикуются.

## Автоматический NPC Vitality gate

Фокусный acceptance-файл:

`tests/test_living_conversation_acceptance.py`

Локальный запуск:

```powershell
python -m pytest -q tests/test_living_conversation_acceptance.py
```

Gate проверяет:

1. voice-profile fingerprints четырёх NPC различаются;
2. один внешний дорожный факт приводит к различным subjective stances;
3. приватная disclosure Мире не появляется у Каспара;
4. память и open thread переживают пересоздание сервиса;
5. pending question создаёт grounded `unfinished_thread` initiative;
6. `refuse` проходит как валидный conversation act без forced fallback;
7. viewer-facing `/api/dialogue` не раскрывает внутренние поля отношений и conversation metadata.

Этот acceptance дополнительно встроен в:

- `.github/workflows/stream-slice.yml`;
- `.github/workflows/playable-candidate.yml`.

Полный release gate также сохраняет существующие Stream Slice, Living World, web contract, build, Chromium и Windows проверки.

## Качественный human vitality gate

Автоматические тесты доказывают архитектурные и причинные инварианты, но не должны подменять человеческую оценку естественности текста.

Перед публичным показом рекомендуются две ручные проверки.

### Blind identity

Собрать 10 обезличенных реплик из свободного разговора четырёх NPC. Рецензент, которому известны персонажи, должен правильно определить говорящего минимум в 8 из 10 случаев.

Это критерий качества, а не текущая автоматически доказанная метрика.

### 10-minute anti-bot transcript

Провести около 10 минут свободного диалога с несколькими NPC и проверить, что transcript не скатывается в:

- одинаковый service tone;
- постоянное согласие;
- постоянные вопросы в конце;
- повтор одного и того же fallback;
- выдуманные факты;
- одинаковую реакцию разных персонажей на одну ситуацию.

Если live model недоступна, отдельно проверить offline fallback route.

## Запуск игры

Living Conversation v2 использует существующий Stream Slice launcher. Из корня репозитория:

```powershell
python -m pip install -e ".[dev]"
cd web
npm install
cd ..
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1 -Reset
```

Открыть:

`http://127.0.0.1:5173/?stream=1`

Для продолжения существующей Stream Slice БД без reset:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1
```

## Что проверить вручную за короткий rehearsal

1. Поговорить с Мирой о её текущей работе и повторить нейтральный вопрос дважды — offline fallback не должен дословно повториться подряд.
2. Дать Мире личное утверждение или незавершённую тему через live provider и вернуться к ней позже — callback должен быть уместным и локальным этой паре.
3. Спросить Каспара о том же приватном факте до реальной передачи знания — он не должен знать его автоматически.
4. Сравнить реакцию Талена и Орена на восточную дорогу — источник и субъективный смысл должны различаться.
5. Спровоцировать ситуацию, где персонажу уместно отказаться или не согласиться, и убедиться, что он не превращает отказ в сервисный ответ.
6. Перезагрузить страницу/перезапустить сервис и проверить persistence пары и мира.

## Safety / causal boundaries

Living Conversation v2 не меняет authoritative gameplay contract.

Модель не может сама:

- переносить предметы;
- завершать quest;
- менять локацию;
- создавать награду;
- записывать произвольный world truth;
- делиться приватной памятью с другим NPC без отдельного causal mechanism.

Server-side действия и существующая система `npc_knowledge` остаются источником истины для мира.

## Release evidence

Финальные exact-head GitHub Actions run IDs, test counts и artifact digests фиксируются в PR #45 после последнего validation pass. Runbook намеренно не встраивает временные run IDs до финального head, чтобы не превращать обновление evidence в бесконечную смену release SHA.

Минимальный release verdict:

- full Python suite GREEN;
- named Living Conversation vitality acceptance GREEN;
- Stream Slice focused Python + preflight GREEN;
- web contract GREEN;
- production build GREEN;
- canonical Chromium GREEN;
- Living NPC Chromium GREEN;
- Social World Chromium GREEN;
- Stream Slice Chromium GREEN;
- Windows Compatibility Gate GREEN.

## Граница готовности

Living Conversation v2 означает готовность архитектуры разговоров и автоматических причинных инвариантов для stream-ready vertical slice. Это не заявление, что любая свободная LLM-реплика гарантированно художественно идеальна.

Для публичного статуса «персонажи убедительно живые» автоматический gate должен быть дополнен реальным human rehearsal по blind identity и anti-bot transcript критериям выше.
