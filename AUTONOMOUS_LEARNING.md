# Autonomous learning log

## Run cycle 1 - mobile playability in the first viewport

- Champion before cycle: `c7a1b192d613b316bdb59bc50fac4238091cac52` as the technically green branch head under review.
- Observation: at 390x844 the full page was 390x967 and touch controls were pushed below a large empty game-container area.
- Confirmed cause: the canvas scaled down on narrow screens while `#game` kept the desktop `min-height: 540px`.
- Hypothesis: remove the desktop minimum height only on narrow screens so the touch controls follow the real canvas and stay in the first viewport.
- RED evidence: `588dc611b70e9d16e81571978b60bbf719aa11e9` measured document height 967px against an 844px viewport.
- Implementation: `ae719563b70c721d338ba19007edd471cd550d81` added the narrow-screen `#game { min-height: 0; }` override.
- Result: document height fell to 852px and the complete touch-control block became visible inside the 844px viewport.
- Test refinement: `9e8d27405fa3c4aa3a24ac86c4d1930cdb38a31f` replaced the proxy metric of zero page scroll with the product invariant that the entire touch-control block is reachable in the first viewport and that touch input actually moves the player.
- Verification: all five mandatory repository gates succeeded on `9e8d27405fa3c4aa3a24ac86c4d1930cdb38a31f`; final browser evidence visually confirms the controls are reachable.
- Decision: ACCEPT.
- Confirmed lesson: browser screenshots can expose a real usability failure that a green interaction test misses.
- Incorrect assumption: total document height must be no greater than viewport height. The remaining 8px outer page overflow had no effect on control reachability.
- Do not repeat without new evidence: changing production layout only to remove harmless outer scroll after the actual control-reachability invariant is satisfied.
- Next main question: can Stream Slice keep canonical location IDs internally while presenting the same Russian location names already used by normal mode?

## Run cycle 2 - Stream Slice location localization

- Champion before cycle: `9e8d27405fa3c4aa3a24ac86c4d1930cdb38a31f`.
- Observation: Stream Slice showed English location names such as `Workshop Yard` and `The Wayfarer's Hearth` inside an otherwise Russian presentation.
- Confirmed cause: Stream mode rendered `snapshot.world.location_name` directly while normal mode already used `hudLocationName(locationId, fallback)`.
- Hypothesis: reuse the existing location presentation helper in Stream Slice without changing canonical location IDs or backend state.
- RED evidence: `8412882e2b296f84db19446c659725cc0c91be52` failed the Stream Slice browser acceptance because `Место: Workshop Yard` appeared where `Место: Мастерская` was required.
- Implementation: `8ff8d00f73d5be8d20b0dc1d80dea3a17cc7389a` routed Stream HUD and Stream status through the existing location-name helper.
- Result: Stream screenshots show `Мастерская`, `Площадь`, `Берег реки`, and `Таверна` while canonical internal IDs remain unchanged.
- Verification: all five mandatory gates succeeded on `8ff8d00f73d5be8d20b0dc1d80dea3a17cc7389a`.
- Decision: ACCEPT.
- Confirmed lesson: presentation localization should be applied at the UI projection boundary, not by mutating canonical world data.
- Next main question: does the visible control hint match the actual input method on a touch viewport?

## Run cycle 3 - responsive control hints

- Champion before cycle: `8ff8d00f73d5be8d20b0dc1d80dea3a17cc7389a`.
- Observation: mobile controls were fully reachable, but the visible hint still instructed the player to use `WASD` and `E`; the same mismatch existed for contextual actions in Village and Tavern.
- Confirmed cause: VillageScene and TavernScene hard-coded keyboard-facing hint text regardless of viewport/input presentation.
- Hypothesis: use one responsive hint formatter so touch-sized viewports say `Экранные кнопки` / `Действие`, while desktop keeps the existing keyboard language.
- RED evidence: the browser suite on `97dff78c73a0b10099fc48f60f391ea20b5e9be5` produced exactly three expected failures: base mobile hint, firewood action hint, and Oren action hint. Five unrelated browser scenarios passed and browser diagnostics were clean.
- Implementation: `87a9b2c04351c0b7401c19aae479563c384d0275` added a shared responsive hint formatter and connected it to Village and Tavern without changing input mechanics.
- Test correction: the first GREEN attempt exposed a brittle test helper that demanded an exact player X coordinate even though the screenshot already showed the correct `Действие – подобрать дрова` text. `c619d9bb84a0dd96e2978275d077d8002ef4336f` changed the test route to stop on the actual product condition instead of an exact coordinate.
- Result: mobile screenshots show on-screen-control language; desktop screenshots retain `WASD` / `E`; contextual hints in both scenes follow the same rule.
- Verification: all five mandatory gates succeeded on `c619d9bb84a0dd96e2978275d077d8002ef4336f`; Playable Candidate run `34239456018`, Stream Slice run `34239456030`.
- Decision: ACCEPT.
- Confirmed lesson: interaction tests should wait for the player-visible state that matters, not an incidental world coordinate that can vary with frame timing.
- Presentation update from product owner: Nichey will play and stream from a desktop computer. Desktop player clarity and stream audience readability are now the primary presentation target; mobile remains supported but is no longer the next optimization target.
- Fresh desktop observation: normal mode can expose raw English Living World event text, e.g. `Talen arrived at The Wayfarer's Hearth with news from the eastern road.`, inside an otherwise Russian HUD.
- Next main question: can normal desktop mode localize audience-facing Living World event summaries while preserving canonical event payloads and Stream Slice causality?

## Run cycle 4 - desktop Living World event localization

- Champion before cycle: `c619d9bb84a0dd96e2978275d077d8002ef4336f`.
- Observation: the final desktop Living World frame mixed Russian UI with raw English event text and incorrectly rendered Oren's bread request as another Mira wood request.
- Confirmed cause: normal mode used a separate `eventText()` projection with incomplete event coverage, a generic `NPC_REQUESTED_RESOURCE` mapping to Mira, and a raw `event.summary` fallback; Stream Slice already had correct audience-safe labels.
- Hypothesis: reuse the existing `streamEventLabel()` projection for normal desktop Living World summaries without changing canonical server events.
- RED evidence: `325bfee0d2a33126a3a2e5338dec4dcd4a5cb81d` failed the deterministic desktop vertical slice with `Мира просит древесину Мира просит древесину Тален: Talen arrived at The Wayfarer's Hearth...`; seven unrelated browser scenarios passed and diagnostics were clean.
- Implementation: `252c27a5d839e4e04687279d9efb5279e6207548` made normal `eventText()` delegate to the already-tested `streamEventLabel()` projection.
- Result: final desktop screenshot shows `Мира просит древесину для мастерской`, `Орен ищет хлеб для гостя`, and `Тален прибыл в таверну с новостями с дороги`, with no raw English event summary.
- Verification: all five mandatory gates succeeded on `252c27a5d839e4e04687279d9efb5279e6207548`; Playable Candidate run `34242348031`, Stream Slice run `34242348012`. Full browser route: 8/8 main scenarios, 1/1 Living NPC, 1/1 Social World, 1/1 Stream Slice. Bundle: 1,141,485 bytes against a 1,200,000-byte budget.
- Decision: ACCEPT.
- Confirmed lesson: player-facing and audience-facing summaries of canonical world events should share one safe UI projection; raw server summaries should remain internal evidence, not public presentation text.
- Fresh stream observation: dialogue overlays still display the prototype-facing label `локальная реплика` below the player controls, visible directly to the audience.
- Next main question: can the dialogue overlay remove prototype-only chrome while preserving NPC name, transcript, free-text input, action buttons, and deterministic dialogue behavior?
