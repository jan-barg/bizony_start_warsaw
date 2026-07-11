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

Read-only overlay on `origin/develop` (no merge/rebase):

- Full non-integration suite → 207 passed, 2 deselected, 1 incoming xfailed.
- Alert-only policy matrix → 4/4 passed: `COLORWAY_CONFLICT`, `COLORWAY_UNCONFIRMED`, `LLM_MATCH_ONLY`, and `SIZE_AMBIGUOUS` never purchase.
- Generated seeds 1–5 → 88.4679% (978/1106) non-trap style identity; all 10 colorway traps flagged; all 10 `gs_kids` traps unflagged.
- Incoming `origin/develop` itself is not full-gate clean: six Ruff failures and 15 mypy failures in API/world/engine files. These are outside this branch diff.

## Cross-branch findings

- Local branch files still contain Person A/B stubs because the new work is only on `origin/develop`; no branch sync was authorized. Compatibility was tested through a `/private/tmp` overlay.
- The ≥95% generated-world target is not met. Generator `_messy_title` intentionally removes colorway from 20% of normal titles, frequently among duplicate brand/model variants; choosing the true style code is then impossible from matcher inputs. Runtime deliberately does not exploit style codes leaked by generated `image_url` filenames. Sanctioned fail-closed result: 88.4679%, measured honestly.
- Generated `gs_kids` traps replace the kids title with the adult brand/model/colorway and bare EU 43, with no kids marker or other matcher-visible evidence. Flagging them would require a trap-specific heuristic or hidden truth. Generator/policy contract needs correction.
- All four alert-only flags pass the incoming immediate policy integration. Matcher memoization is still absent from incoming `evaluate_tick`; Person B owns `(hunt.id, listing.id)` caching.
- Person C still owns API image decode/validation, in-memory digest map, and clarify response transport.

## Integration obligations

1. Sync `origin/develop` only with explicit branch-change consent, then resolve the generator/matcher observability contract above.
2. Add Person B matcher memoization; policy safety already has a four-flag integration gate.
3. Preserve the committed reviewed cache as a versioned replay input; any future rewarm requires new human approval.
4. Run the full offline gate twice from the committed cache; verify missing keys raise `LLMCacheMiss`.

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
