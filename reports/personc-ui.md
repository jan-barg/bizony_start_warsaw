# Branch report — personc (Work Order 4, UI portion)

## What is built

A SvelteKit SPA in `ui/` (Svelte 5, `@sveltejs/adapter-static` with `fallback: index.html`, `ssr=false`, `prerender=false`, plain JS, zero component libraries — hand-rolled CSS from `BRAND_GUIDELINES.md` tokens). The UI is a pure consumer of receipts and SSE events: no landed-cost math, no gate logic; every badge/color derives only from `action` / `eligibility` / order `state` / ask `kind` fields. All amounts render the API's decimal strings verbatim (`eur()` in `src/lib/format.js` does string prefixing only); `parseFloat` is used exclusively for chart y-geometry.

### Screens

| Screen | Route | Notes |
|---|---|---|
| ① New Hunt | `/` | Textarea + monitor/immediate toggle (immediate appends " now" to the text AND passes `mode`); `NEEDS_INFO` questions render chat-style; each reply POSTs `/intake/{id}/clarify`; on OK the payload is stashed in a store and the app navigates to confirm. |
| ② Mandate Confirm | `/hunt/[id]/confirm` | Human card: big cap number, mode, deadline, auto-buy conditions, middlemen, geo knob, over-cap band, alert budget, expiry. Cap / alert budget / geo / middlemen edits PATCH `/hunts/{id}/mandate` on change. Non-empty `mandate_diff` renders a red/orange changed-fields card + field highlights. Confirm → `confirm` then `run_immediate` (③a) or `start` (③b) by `mandate.mode`. Falls back to `GET /hunts/{id}` on refresh. |
| ③a Immediate Result | `/hunt/[id]/immediate` | BUY → winner card with full line-item table (landed bolded, never recomputed). ESCALATE_NONE_FOUND → "Nothing qualifies right now" + ranked near-misses (landed, one-line reasons, "approvable" badge straight from `eligibility === "OVER_CAP_BAND"`) + prominent "Switch to monitor" (POST start → ③b). |
| ③b Monitor Dashboard | `/hunt/[id]/monitor` | EventSource on `/hunts/{id}/events` with named-event listeners (tick/receipt/ask/status/order/done). Hand-rolled SVG chart: best landed per receipt tick (`chosen ?? considered[0]`), labeled cap line, dashed running observed-min, markers BUY dot / ALERT ring / ASK diamond, legend, crosshair+tooltip. Newest-first feed of receipt cards (action badge, tick, reasons, expandable line items) and order cards (PLACED / CONFIRMED+delivery / CANCELLED_BY_MERCHANT red+refund note / REFUNDED). Blocking ask modal: kind chip, narrative, fact table (line items, landed, ETA, p_cancel as %, comparison), truncated mono quote_hash, visible "World clock paused" indicator, Approve/Decline. Controls: client-side play/pause (events buffered while paused, flushed on resume) and Revoke (confirm dialog → terminal REVOKED banner). `done` with `PURCHASED` navigates to ④ after a short beat. |
| ④ Purchase Receipt | `/hunt/[id]/receipt` | Fetches receipts, finds the BUY row: full line-item table, escalation tier, decided_by, trust, route, ETA, stopping snapshot (p_better vs θ, n_obs, horizon), reasons. |

### Files

- `ui/package.json`, `ui/svelte.config.js`, `ui/vite.config.js`, `ui/src/app.html`, `ui/src/app.css`
- `ui/src/routes/+layout.js` (+`.svelte`), `+page.svelte`, `hunt/[id]/{confirm,immediate,monitor,receipt}/+page.svelte`
- `ui/src/lib/{api.js,stores.js,format.js}`
- `ui/src/lib/components/{ActionBadge,LineItemTable,ReceiptCard,OrderCard,AskModal,PriceChart}.svelte`
- `ui/static/brand/solidhunt-logo.svg` (copied from `assets/brand/`)

## How to run

```bash
# terminal 1 — API (repo root)
.venv/bin/uvicorn dealhunter.api.app:app --port 8000

# terminal 2 — UI
cd ui && npm install && npm run dev     # http://localhost:5173
# production build: npm run build  (static SPA in ui/build/)
# point at another API: VITE_API=http://host:port npm run dev
```

Demo click-through: type "nike dunks" → answer the clarifying questions ("size 43 under €80") → confirm mandate (edit cap/budget/geo live) → start → watch the feed → approve both ask modals (GRAY_ROUTE, then OVER_CAP; the gray order gets merchant-cancelled and refunded on-screen) → BUY lands → receipt screen.

## Verification status

- `cd ui && npm install && npm run build` → exit 0.
- `npm run dev` boots; every route module transforms cleanly (HTTP 200 from the vite dev server); SPA fallback serves deep routes.
- Full end-to-end driven from node (script mirrors the UI's exact calls, including a fetch-stream SSE consumer that parses the same named-event wire format): **34/34 checks passed** — NEEDS_INFO loop, all four PATCH fields, confirm/start, 42 ticks + 21 receipts streamed, both ask kinds approved with clock-paused status events, CANCELLED_BY_MERCHANT + REFUNDED + PLACED + CONFIRMED order events, done=PURCHASED, BUY receipt with line items summing to landed and a stopping snapshot, immediate flow (ESCALATE_NONE_FOUND + near-misses + switch-to-monitor), and revoke-during-ask terminating the stream with REVOKED.
- Chart marker palette (buy green / alert amber / ask purple `#7A3BBF` / reject red / info blue) validated with the dataviz palette validator on the light surface: all checks pass; markers are never color-alone (legend + badges carry labels).

## API shape issues found (reported, not changed)

1. **`mandate_diff` is unreachable in the fixture flow.** `FixtureEngine.mandate_diff` diffs against the *previous* round's result, but a previous `OK` promotes the intake to a hunt (further clarify → 409) and `NEEDS_INFO` rounds carry `mandate=None` → diff `[]`. So the confirm screen's red/orange diff highlighting can never fire on fixture data. The UI implements it anyway (renders any non-empty `mandate_diff`); worth wiring real diffs at S2.
2. **`POST /intake` ignores the `mode` body field.** The fixture parser derives IMMEDIATE only from "now"/"immediately" in the text. The UI sends `mode` *and* appends " now" for immediate, so it works, but the real intake should honor `mode`.
3. **`run_immediate` in the fixture always returns `ESCALATE_NONE_FOUND` with `chosen: null`.** The ③a BUY winner card is implemented per contract but only exercisable after the S2 engine swap.
4. **`GET /hunts/{id}/events` 409s when the hunt isn't RUNNING, but browser `EventSource` can't read error bodies.** The monitor screen pre-checks via `GET /hunts/{id}` and shows a plain-language banner instead. A `status`-first event (or allowing the stream pre-start) would be friendlier.
5. Minor: order events carry no line items/quote (only state + ids/ticks) — fine for cards; noting in case the receipt screen should ever show the cancelled order's math.

## Deferred

- **Screen ⑤ Judge View** — S3 per the work order; not built.
- Speed controls (×1/×5/×20) — the server supports `?tick_ms=`, but my brief scoped controls to play/pause + revoke; pause is client-side buffering. Trivial to add by reconnecting with `tick_ms`.
- Image-drop intake input (S2+; API accepts text only today).

## Acceptance commands

```bash
cd ui && npm install && npm run build          # must exit 0
.venv/bin/uvicorn dealhunter.api.app:app --port 8000 &   # from repo root
cd ui && npm run dev &                          # then click through per "How to run"
python3 -m pytest tests/test_api.py -q          # API contract tests (Person B's) still green
```
