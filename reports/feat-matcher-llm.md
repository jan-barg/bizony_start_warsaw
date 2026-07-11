# `feat/matcher-llm` delivery proof

Date: 2026-07-11  
Runtime: Python 3.12.13  
Branch point: local `develop` (`0f0216a`)  
Read-only integration target: `origin/develop` (`5c4fef8`, 15 incoming commits)

## Delivered

- OpenAI Responses contract: `openai>=2.44,<3`, pinned `gpt-5.6-terra`, low reasoning, bounded output, `store=false`, strict caller-owned schemas.
- Matcher tiers 1–3: NFKC/style-code identity, bounded multilingual evidence, exhaustive size lookup, deterministic color/condition/kids safety flags, fuzzy floor/accept/margin.
- Veto-only tier 4: exactly three candidates; outside-list, malformed, refusal, and Null outcomes abstain; choices always unconfirmed and `LLM_MATCH_ONLY`.
- Strict SQLite cache: model-scoped canonical key, WARM/REPLAY modes, read-only replay, corrupt-row failure, successful normalized responses only.
- Intake: deterministic 1–8 candidate/size/positive-cap/deadline gate, MONITOR-only user-field default, max-three code-selected questions, unknown/unseen style-code clearing.
- Clarification/vision: digest-only transcripts, API-owned image resolver, full transcript+original-image reparse, private partial drafts, Hunt creation only after sufficiency, sorted sensitive `brief.*`/`mandate.*` diffs.
- Placeholder-safe narration: typed facts, provider receives placeholder names only, foreign digit/name/placeholder/imperative rejection, visibly quoted code-owned substitution, deterministic fallback.
- S3 tooling: seven reviewed manifest cases/eight calls, explicit fresh-approval phrase, semantic checks before publish, no-overwrite behavior, two byte-identical offline replay passes.
- Seeds 1–5 generated-world and all-alert-only policy acceptance tests, marked `integration` so this branch remains runnable before sync.

## Commits

- `6c7c562` — `build(llm): adopt OpenAI responses contract`
- `4fbad55` — `feat(matcher): add deterministic fuzzy identity scoring`
- `0222fa7` — `feat(llm): add OpenAI replay client and cache`
- `bd82158` — `feat(llm): add deterministic vision intake`
- `9425540` — `feat(llm): add veto-only adjudication`
- `2d80894` — `feat(llm): add placeholder-safe narration`
- `06c4560` — `chore(llm): add reviewed cache warming manifest`
- `24fd9ff` — `test(matcher): add generated-world acceptance gate`
- `b23a3f0` — `fix(llm): avoid hidden-label narration token`
- `4a3e8c3` — `fix(matcher): fail closed on ambiguous colorways`
- `a7b89ef` — `test(policy): assert matcher alert-only safety`
- `d7d665a` — `fix(llm): canonicalize Responses mapping input`
- `0e39f07` — `chore(llm): add warmed deterministic demo cache`
- `b080a64` — `fix(llm): make cache artifact deterministic`

Tasks 1–3 share one matcher commit and tasks 5–6 share one intake commit because their evidence extraction/state paths are inseparable in the frozen public seams. Behavior remains independently covered by focused tests.

## Proof gates

Baseline before work:

- `python3 -m pytest -q` → 19 passed, 12 xfailed.
- `mypy dealhunter` → green.
- `ruff check .` → five pre-existing failures; fixed in contract-readiness commit.

Focused:

- `.venv/bin/python -m pytest -o addopts='' -q tests/test_matcher.py` → 57 passed; 32-title nasty table; mini-world identity 8/8; colorway trap flagged.
- `.venv/bin/python -m pytest -o addopts='' -q tests/test_llm_client.py` → 10 passed.
- `.venv/bin/python -m pytest -o addopts='' -q tests/test_llm_intake.py` → 15 passed.
- `.venv/bin/python -m pytest -o addopts='' -q tests/test_llm_adjudicate.py` → 13 passed.
- `.venv/bin/python -m pytest -o addopts='' -q tests/test_llm_narrate.py` → 12 passed.
- `.venv/bin/python -m pytest -o addopts='' -q tests/test_llm_warm.py tests/test_llm_offline.py` → 5 passed.

Final offline gate:

- `.venv/bin/python -m pytest -o "addopts=-m 'not integration'" -q` → 133 passed, 6 deselected, 12 pre-existing xfailed.
- `.venv/bin/ruff check .` → all checks passed.
- `.venv/bin/mypy dealhunter` → success across 28 source files.
- Hidden-label grep over `dealhunter/engine` → clean.
- Dossier-import grep over `dealhunter/engine dealhunter/llm` → clean.
- NullClient/replay surfaces with `socket.create_connection` blocked → passed.

Live OpenAI / cache gate (fresh human approval on 2026-07-11):

- First reviewed-manifest attempt failed closed before publication with OpenAI 400: mapping `input` must be translated to a string/array. Adapter regression added and fixed in `d7d665a`.
- Retry: `gpt-5.6-terra`, seven reviewed cases/eight live calls → all semantic checks passed.
- Corrective review gate: real rendered adversarial screenshot includes hostile cap/auto-buy instructions; server diff marks `mandate.cap_landed_eur` and `mandate.auto_buy.enabled` sensitive.
- Warming now rejects any narration response that fails post-validation instead of accepting its fallback.
- `fixtures/llm_cache.sqlite` → 8 normalized rows; SHA-256 `cd848b85b00884d2f3b6c82b5cd4b8f1d66bc5cbc5fa95f9c59d277534404698`.
- Replay with sockets blocked → two normalized output runs byte-identical.
- Independently rebuilt cache from replay → SQLite files byte-identical. `created` is deterministic `1970-01-01T00:00:00+00:00`; no wall-clock reads.

Historical read-only overlay on pre-fix `origin/develop` (no merge/rebase):

- Full non-integration suite → 207 passed, 2 deselected, 1 incoming xfailed.
- Alert-only policy matrix → 4/4 passed: `COLORWAY_CONFLICT`, `COLORWAY_UNCONFIRMED`, `LLM_MATCH_ONLY`, and `SIZE_AMBIGUOUS` never purchase.
- Generated seeds 1–5 → 88.4679% (978/1106) non-trap style identity; all 10 colorway traps flagged; all 10 `gs_kids` traps unflagged.
- Incoming `origin/develop` itself is not full-gate clean: six Ruff failures and 15 mypy failures in API/world/engine files. These are outside this branch diff.

## Cross-branch findings

- The historical overlay exposed insufficient matcher-visible evidence in generated titles and `gs_kids` traps. The generator contract was corrected before PR #1 merged; runtime still does not inspect hidden truth or image filename leaks.
- Current synchronized seeds 1–5 result: 1,177/1,214 non-trap identities correct (**96.952224%**) and zero unflagged matcher traps. The ≥95% M4 gate is green.
- All four alert-only flags pass the incoming immediate policy integration. Matcher memoization is still absent from incoming `evaluate_tick`; Person B owns `(hunt.id, listing.id)` caching.
- Person C still owns API image decode/validation, in-memory digest map, and clarify response transport.

## Integration obligations

`WORK-ORDER-STATUS.md` is the canonical remaining-work checklist; this report
records evidence and retains explicitly labeled historical snapshots.

1. **Complete:** synchronized `origin/develop` under explicit consent; the generator/matcher observability contract now passes at 96.952224% with zero missed traps.
2. **Pending B:** add run-scoped matcher memoization; policy safety already has a four-flag integration gate.
3. **Pending S3:** preserve the committed reviewed cache until a validated seed-42 candidate replaces it; any live rewarm requires fresh human approval immediately beforehand.
4. **Pending final gate:** run the full offline path twice from the committed cache and verify missing keys raise `LLMCacheMiss`.

## Exact acceptance commands

```sh
.venv/bin/python --version
.venv/bin/python -m pytest -o "addopts=-m 'not integration'" -q
.venv/bin/ruff check .
.venv/bin/mypy dealhunter
pytest -m integration tests/test_matcher_integration.py -q
rg -n 'is_bait|is_counterfeit|true_product_id|p_cancel\b' dealhunter/engine
rg -n 'world\.dossier' dealhunter/engine dealhunter/llm
```

## Post-merge completion audit

Audit date: 2026-07-11. Integration base: `origin/develop` at `481c409`.

| Requirement | Evidence | Status |
|---|---|---|
| WO-3 task 1 — deterministic tiers 1–2 | `tests/test_matcher.py`; 57 focused matcher tests | complete |
| WO-3 task 2 — fuzzy tier 3 and accuracy | `tests/test_matcher_integration.py`; current seeds 1–5: 1,177/1,214 (**96.952224%**), zero missed traps | complete |
| WO-3 task 3 — OpenAI/Null clients and strict cache | `tests/test_llm_client.py`, `tests/test_llm_offline.py`; live manifest proof above | complete |
| WO-3 task 4 — intake, clarify, vision, diff | `tests/test_llm_intake.py`; digest-only transcript and sensitive diff cases | complete |
| WO-3 task 5 — veto-only adjudication | `tests/test_llm_adjudicate.py`; outside-list/refusal/Null abstention | complete |
| WO-3 task 6 — placeholder-safe narration | `tests/test_llm_narrate.py`; hostile-name, digit, placeholder, imperative fallbacks | complete |
| WO-3 task 7 — final demo cache | Current reviewed 8-row artifact is valid; exact seed-42 S3 demo requests are not frozen | blocked by final demo script |
| S2 monitor memoization | Context-local `(hunt.id, listing.id)` cache; 6 matcher integration tests, 21 combined focused tests, and V10 pass | complete |
| S3 intake/narration API/UI wiring | D modules are ready; `api/app.py` still uses regex intake and fixed narration | blocked by C integration |
| Full integrated static gate | Person B/D-owned paths are green | blocked by A/C failures listed in `WORK-ORDER-STATUS.md` |
| Offline/browser rehearsal | Real monitor is available and module replay is deterministic; API/UI still use fixtures | blocked by C integration |

### S2 handoff finding

Person B's merged S2 engine removed the Stage-0 fallback and added matcher reuse
across ticks, but the first implementation stored results in a module-global
cache. D's regression reproduced cross-run leakage with the same deterministic
hunt ID. Commit `c9a81fc` replaced the cache with a context-local execution
scope keyed exactly by `(hunt.id, listing.id)`. The first and second executions
now each call the matcher once per listing; V10 remains byte-identical.

Person D is **not yet complete** under the post-merge checklist. WO-3 tasks 1–6
are complete; task 7 and the S2/S3 cross-person acceptance gates remain blocked
and must not be checked off without passing evidence.

### Post-merge execution log

- Repeated `git fetch origin` detected B's merge at `481c409`; it was merged into `feat/matcher-llm` as `e7ce513` with the status-board conflict resolved from both intents.
- Person C's latest fetched work remains on `origin/personc` at `895f7c2` and does not wire LLM intake/narration.
- Full default `pytest -q`: 238 passed, 0 xfailed. Person B/D-focused Ruff and mypy gates are green.
- Full Ruff remains red with 6 pre-existing A/C-owned findings; full mypy remains red with 12 pre-existing A/C-owned findings. Exact ownership is recorded in `WORK-ORDER-STATUS.md`.
- Extended matcher integration: 5 passed, 1 failed on the run-scoped memo contract against the real monitor.
- Current generated-world proof: 1,177/1,214 non-trap identities correct (96.952224%), zero missed matcher traps.
- No new live OpenAI call was made: the existing reviewed manifest/cache is already proven, while the exact seed-42 final-demo request set is not yet frozen. Human approval for necessary final calls is available but must be reconfirmed immediately before warming.

Local post-merge commits (not pushed):

- `89cf40f` — `docs(llm): define post-merge completion gates`
- `bd905e3` — `test(matcher): require run-scoped monitor memo`
- `39267d0` — `docs(llm): correct post-merge audit evidence`
- `a674258` — `docs(llm): reconcile final S3 obligations`
- `08977f6` — `docs(llm): record post-merge integration proof`
- `e7ce513` — `merge: integrate S2 engine into matcher branch`
- `c9a81fc` — `fix(matcher): scope monitor memo per execution`
