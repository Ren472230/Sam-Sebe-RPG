# Integrated Release Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the existing playable candidate, integrate the already-prepared telemetry foundation without enabling unsafe transport, verify one exact release HEAD, and merge PR #53 only if every required gate is green.

**Architecture:** Keep gameplay architecture unchanged. Browser acceptance navigation remains real physical WASD input, but becomes a closed-loop controller: target coordinates guide steering while the requested interaction hint is the only success condition. Telemetry is manually rebased onto the stabilized integration branch so current gameplay/E2E changes are preserved; PostHog transport remains fail-closed until privacy is confirmed.

**Tech Stack:** TypeScript, Phaser 3.90, Playwright 1.55, Vite 7, Node test runner, Python/pytest, SQLite, GitHub Actions, PostHog.

**Spec:** PR #53 `Integration: audit results consolidation v1` plus the user-approved stabilization/integration design from 2026-09-11.

## Global Constraints

- Continue existing repository `Ren472230/Sam-Sebe-RPG`; do not restart or rewrite working architecture without evidence.
- Work on `integration/audit-results-v1`; do not change `main` before the final release gate.
- Do not merge PR #49 separately.
- Browser acceptance must use real keyboard input; no teleport, backend shortcut, collision disable, gameplay speed changes, giant timeout increases, or retry masking.
- Preserve deterministic/headless backend behavior and existing SQLite semantics.
- Integrate telemetry only after the critical Stream Slice browser route is stable.
- PostHog sending must remain disabled while `anonymize_ips=false`.
- Final release evidence must come from one exact candidate SHA; do not mix green checks from different commits.
- Real human validation must remain `PENDING HUMAN VALIDATION` until a human actually plays.

---

### Task 1: Replace brittle spatial stopping with interaction-driven physical navigation

**Files:**
- Modify: `web/tests/helpers/spatial-navigation.ts`
- Regression acceptance: `web/tests-stream-slice/stream-slice.spec.ts`

**Interfaces:**
- Consumes: `document.body.dataset.playerX`, `document.body.dataset.playerY`, `#interaction-hint`, Playwright keyboard events.
- Produces: `moveTowardInteraction(page, targetX, targetY, hintText, timeout)` that succeeds only when the requested hint is visible inside the stable interaction radius.

- [ ] **Step 1: Preserve the current RED regression evidence**

Run the existing Stream Slice gate at candidate `4d644eec677196acd7130e036e0011d45b9f0ea8`. Expected failure: Mira approach stops near `(279,385)` with hint `E — подобрать дрова` instead of `поговорить с Мирой`; canonical mutation count remains zero.

- [ ] **Step 2: Change the steering termination rule, not gameplay**

In `moveTowardInteraction`, remove the broad ±44 px axis stop band as the terminal condition. Determine one initial key per axis from the target side, hold both axes concurrently, release an axis only after it reaches/crosses the target coordinate, and never reverse that axis during the same approach. Continue polling the requested hint while either key is active. Keep `stableInteractionRadius = 68`, diagnostics, physical keyboard input, and current timeout.

Expected behavior for Mira: starting from the workshop anchor, A+W continues through the firewood-priority overlap until the player is physically close enough to Mira that `поговорить с Мирой` becomes the active hint.

- [ ] **Step 3: Run the Stream Slice regression**

Run: GitHub `Stream Slice Gate` for the new exact HEAD.

Expected: the Mira commitment step passes. If a later step fails, inspect the exact job log and fix only the newly proven root cause before continuing.

- [ ] **Step 4: Run the dependent browser gates on the same HEAD**

Expected green: `Stream Slice Gate`, browser portion of `Playable Candidate Gate`, `Prototype Web CI`, and `Living World Integration Gate`.

### Task 2: Prove E2E stability instead of one lucky pass

**Files:**
- No production-file changes unless a new reproducible defect is proven.

**Interfaces:**
- Consumes: exact candidate SHA from Task 1 and GitHub Actions rerun APIs.
- Produces: repeated same-SHA evidence for critical browser acceptance.

- [ ] **Step 1: Re-run critical failed/successful browser jobs without changing SHA**

Re-run the Stream Slice workflow at least three sequential times on the same commit. Do not create commits between runs.

- [ ] **Step 2: Compare failures by phase and diagnostics**

If any rerun fails, treat it as a real stability defect: inspect coordinates, hint, key trace, canonical mutations, browser errors, and measured step durations. Do not increase the global 180 s test timeout merely to obtain green.

- [ ] **Step 3: Establish browser stabilization gate**

Acceptance: three consecutive Stream Slice passes on one SHA and green dependent browser workflows on that same SHA.

### Task 3: Manually integrate telemetry foundation from PR #52

**Files:**
- Create from PR #52: `web/src/telemetry.ts`
- Create from PR #52: `web/tests/telemetry.test.ts`
- Create/update from PR #52: `docs/release/TELEMETRY_FOUNDATION_V1.md`
- Modify manually: `web/src/main.ts`
- Modify manually: `web/src/scenes/VillageScene.ts`
- Modify manually: `web/src/scenes/TavernScene.ts`
- Modify manually: `web/src/ui/DialoguePanel.ts`
- Modify: `web/package.json`
- Modify: `web/package-lock.json`

**Interfaces:**
- Consumes: narrow telemetry event/property whitelist and privacy gate from PR #52.
- Produces: best-effort event capture that never blocks gameplay and never sends raw dialogue text, keys, arbitrary payloads, or PII.

- [ ] **Step 1: Read every PR #52 patch before copying code**

Compare each of the eight changed files against the stabilized integration HEAD. Apply additions manually rather than replacing current scene files wholesale.

- [ ] **Step 2: Integrate telemetry module and tests**

Preserve the whitelist, `VITE_POSTHOG_PRIVACY_CONFIRMED === "true"` gate, host/key checks, swallowed transport failures, and dialogue metadata-only behavior.

- [ ] **Step 3: Integrate gameplay event hooks**

Keep first movement tied to real coordinate change, first interaction tied to actual E interaction, dialogue completion free of raw text, and main/world/WAIT/client-error events best-effort.

- [ ] **Step 4: Synchronize dependency lock**

Update `web/package-lock.json` to match `web/package.json`; `npm ci --no-audit --no-fund` must succeed.

- [ ] **Step 5: Run telemetry and web contracts**

Expected: telemetry tests, existing contract tests, TypeScript check, production build and bundle budget all pass. Sending remains disabled because PostHog project privacy is not confirmed.

### Task 4: Build one exact-head release evidence set

**Files:**
- Update only after verification: `README.md`, `docs/release/RUN_STATE.md`, `docs/release/CHAMPION_STATE.md` when present on the branch.

**Interfaces:**
- Consumes: one final candidate SHA after telemetry integration.
- Produces: exact-SHA release record and truthful readiness verdict.

- [ ] **Step 1: Run all required GitHub Actions on the exact candidate SHA**

Required green set: backend/pytest acceptance, Stream Slice, Playable Candidate, Prototype Web CI, Living World Integration, Visual Forge, Windows Compatibility, Release Reproducibility, web contract/type/build/bundle checks, and telemetry tests.

- [ ] **Step 2: Run autonomous browser playtest review**

Use Game Studio playtest workflow after technical green. Evaluate control clarity, hints, NPC discoverability, quest comprehension, visible world change, WAIT, tavern loop, persistence, Stream Slice coherence, browser errors, and whether the slice creates a credible desire to continue.

- [ ] **Step 3: Update release state documents with evidence**

Record exact SHA, gate conclusions, telemetry privacy state (`transport disabled while anonymize_ips=false`), run instructions, remaining P0/P1/P2 issues, and `PENDING HUMAN VALIDATION` for real-human playtest.

### Task 5: Final verification and controlled merge

**Files:**
- PR #53 metadata only unless verification exposes a documentation error.

**Interfaces:**
- Consumes: final exact-head CI/playtest evidence.
- Produces: either a merged release candidate on `main` or a documented NO-GO with the specific blocker.

- [ ] **Step 1: Run verification-before-completion review**

Re-check the exact branch HEAD, every required workflow conclusion, PR status, PostHog privacy state, and release-state documents before making any completion claim.

- [ ] **Step 2: Apply merge gate**

If any P0/P1 release blocker or required workflow is red, leave PR #53 draft/unmerged and report NO-GO. If all technical gates are green, mark PR #53 ready and merge it to `main` as authorized by the user's master brief.

- [ ] **Step 3: Verify post-merge truth**

Fetch `main` again and record its actual new SHA and post-merge workflow state. PR #49 remains unmerged.
