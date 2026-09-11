# Release Reproducibility Audit – 2026-09-11

## Scope and source of truth

Repository: `Ren472230/Sam-Sebe-RPG`

Release/reproducibility work branch: `agent/release-reproducibility-v1`

Exact base used for this work: `7d7ec138cb15c253f22435f8d5c2983a2e1d1cd8`, the current HEAD of draft PR #49 (`integration/world-ready-svg-v1`) when this audit started. `main` remained at `813ac7beb233645546fcc1e7bda3827efe63dcdc`.

This audit changes dependency/repository/release concerns only. Browser navigation semantics, spatial helpers, browser retries/timeouts and gameplay are outside this branch.

## Findings and actions

### JavaScript / Node

Confirmed before changes:

- `web/package-lock.json` was absent.
- current browser/release workflows used Node.js 22 but installed packages with `npm install`.
- `phaser` was exact-pinned in `package.json`; TypeScript, Vite and Playwright used compatible-range declarations and therefore depended on live registry resolution.

Implemented:

- generated and committed `web/package-lock.json` using Node.js 22/npm on GitHub Actions;
- lockfile format is version 3 and includes package integrity hashes;
- changed current release/browser CI installation steps from `npm install` to `npm ci` without changing test order or browser-test semantics;
- changed the Windows launcher to use `npm ci` whenever the checked-in lockfile exists;
- retained a local human fallback to `npm install` only when the checkout itself is missing `web/package-lock.json`;
- added a cross-platform reproducibility gate that runs `npm ci`, web contracts, production build and `npx playwright --version` on Ubuntu and Windows.

No dependency was deliberately upgraded as part of the lockfile work. The lockfile materializes the dependency graph resolved from the pre-existing `package.json` ranges.

### Python

Confirmed before changes:

- `pyproject.toml` declared Python `>=3.12` and lower bounds for application/test dependencies;
- CI resolution could drift over time;
- the successful Windows candidate gate and Linux candidate jobs were already resolving slightly different ambient/transitive versions in some cases because hosted runner environments differ.

Decision:

A heavyweight Python lock tool is not justified for the current repository stage. A checked-in constraints snapshot gives the required release/CI control with a much smaller maintenance surface.

Implemented:

- added `constraints/python-3.12.txt` with exact application/test dependency versions observed from the current candidate's CI resolution;
- current release/browser CI installs with `python -m pip install -c constraints/python-3.12.txt -e ".[dev]"` (or the runtime-only editable equivalent in Prototype Web CI);
- the Windows launcher uses the same constraints file when bootstrapping Python dependencies;
- the dedicated reproducibility gate creates a fresh virtual environment on Ubuntu and Windows, installs through the same constraints file, then runs `pip check`, the full Python suite and Stream Slice preflight;
- retained lower-bound declarations in `pyproject.toml` so project package metadata stays usable outside the release snapshot;
- corrected the stale `multiplayer-first` package description to describe the persistent Living World/browser vertical slice.

Residual boundary:

- CI selects the Python 3.12 family rather than one exact patch release;
- `setuptools>=75` remains the isolated build-system requirement and is not locked by the application constraints snapshot.

These are deliberate residual drift points. They should be revisited only if patch-level/runtime/build-backend drift becomes a demonstrated release problem.

### Repository hygiene

Confirmed before changes:

- no root `.gitignore` existed;
- no checked-in `node_modules`, Vite `dist`, local SQLite database or Playwright result directory was found in the audited tree;
- historical evidence files already tracked in the repository were left intact.

Implemented root ignore rules for:

- Python caches, test caches, coverage files and local virtual environments;
- `node_modules`, Vite output and npm/yarn/pnpm debug logs;
- Playwright reports/results;
- local SQLite/DB state and process logs;
- `.env` files, private-key file extensions, editor and OS debris.

### Source-of-truth documents

Updated `README.md`, `RUN_STATE.json` and `CHAMPION_STATE.json` to record:

- PR #49 as OPEN / DRAFT / UNMERGED;
- candidate branch `integration/world-ready-svg-v1`;
- exact candidate SHA `7d7ec138cb15c253f22435f8d5c2983a2e1d1cd8`;
- exact `main` base SHA `813ac7beb233645546fcc1e7bda3827efe63dcdc`;
- current gate successes/failures from that exact candidate;
- the temporary complete SVG production manifest status;
- dependency-lock/constraints policy;
- the current browser-E2E blocker.

The previous fresh-ZIP `ModuleNotFoundError` bootstrap issue is no longer recorded as the current blocker because the launcher already contains dependency bootstrap logic. The release branch strengthens that bootstrap with deterministic dependency selection.

### GitHub Releases

The repository currently has no GitHub Releases. This audit intentionally does not publish one while PR #49 is still draft, unmerged and browser-E2E blocked. A release/tag should represent an accepted exact candidate, not a work-in-progress SHA.

## CI duplication map

| Workflow | Repeated setup/checks | Unique responsibility | Decision now |
| --- | --- | --- | --- |
| Prototype Web CI | Python setup, Node 22, web install, contracts, build, Chromium | broad browser-client regression on web changes | keep; switch install to lock/constraints |
| Playable Candidate Gate | Python setup/install/tests, Node 22, web install/contracts/build/Chromium | integrated backend + all browser acceptance suites | keep; switch install to lock/constraints |
| Living World Integration Gate | Python setup/install/tests, Node 22, web install/contracts/build/Chromium | Living World persistence/integration-specific gate | keep; switch install to lock/constraints |
| Stream Slice Gate | Python setup/install/preflight, Node 22, web install/contracts/build/Chromium | Stream Slice-specific acceptance | keep; switch install to lock/constraints |
| Windows Compatibility Gate | Python setup/tests/preflight, Node 22, web install/contracts/build | Windows timezone, SQLite and backend boot parity | keep; switch install to lock/constraints |
| Visual Forge Gate | Python setup/install | visual-forge asset validation with its own Python 3.11/Pillow dependency boundary | keep separate |

There is clear duplication around Python setup, Node setup, dependency installation, contracts and build. A reusable workflow/composite setup action could remove it later. That refactor is deliberately deferred because browser E2E stabilization is active in parallel and several of the same workflow files are conflict-prone. The small deterministic-install edits are independently cherry-pickable and have a much smaller conflict surface.

`DEV-2 backend integration` and `Living World acceptance` are older branch-specific workflows with special branch-composition behavior. They were audited but left unchanged in this release pass to avoid introducing a constraints-file dependency into branches that may not contain that file when those workflows reconstruct their QA checkout.

## Baseline gate evidence at PR #49 HEAD

Exact candidate: `7d7ec138cb15c253f22435f8d5c2983a2e1d1cd8`.

- Prototype Web CI `34473124187`: PASS.
- Windows Compatibility Gate `34473124237`: PASS, including 205 Python tests, Stream Slice preflight, 45 web contract tests, production build and Windows backend boot.
- Visual Forge Gate `34473124446`: PASS.
- Playable Candidate Gate `34473124248`: backend job PASS; browser job FAIL at `Real browser integrated route` after dependency install, web contracts, production build and Chromium install passed.
- Living World Integration Gate `34473124220`: backend job PASS; client dependency install/contracts/build/Chromium PASS; browser critical route FAIL. The inspected failure reported `player did not reach tavern entry band; last={"x":739,"y":455}`.
- Stream Slice Gate `34473124246`: Python tests/preflight/install/contracts/build/Chromium PASS; Stream Slice Chromium acceptance FAIL.

The current product/release blocker is therefore browser E2E stabilization rather than dependency bootstrap, backend installation, web dependency installation, contract tests or production build.

## Follow-up after E2E stabilization

1. integrate the E2E stabilization result with the release/reproducibility changes without altering browser semantics in this branch;
2. rerun Playable Candidate, Living World Integration and Stream Slice gates on one exact integrated SHA;
3. rerun Windows/reproducibility checks on that same SHA;
4. perform the next human experience gate;
5. only then choose whether to merge and tag/publish a GitHub Release.
