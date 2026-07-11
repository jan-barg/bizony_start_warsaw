<script>
	// Screen ② — Mandate Confirm. Renders the compiled mandate as a human card.
	// Editable fields PATCH /hunts/{id}/mandate on change (pre-confirm only);
	// Confirm → POST confirm, then run_immediate (③a) or start (③b) by mode.
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { get } from 'svelte/store';
	import {
		getHunt,
		patchMandate,
		confirmHunt,
		runImmediate,
		startHunt
	} from '$lib/api.js';
	import { intakeByHunt, immediateByHunt, stash } from '$lib/stores.js';
	import { eur, pct, GEO_ARB_LABEL } from '$lib/format.js';

	const huntId = page.params.id;

	let brief = $state(null);
	let mandate = $state(null);
	let changed = $state(new Set()); // field paths from mandate_diff, e.g. "mandate.cap_landed_eur"
	let diffRows = $state([]);
	let busy = $state(false);
	let error = $state('');

	// editable field bindings (kept as strings; sent verbatim — the API owns parsing)
	let capInput = $state('');
	let alertBudgetInput = $state('');

	// onMount, NOT $effect: load() writes state it also reads (mandate →
	// capInput), which inside $effect self-retriggers until Svelte kills the
	// effect tree (effect_update_depth_exceeded) — after that, goto() updates
	// the URL but nothing re-renders. One-shot async loads never belong in
	// $effect.
	onMount(load);

	async function load() {
		try {
			const stashed = get(intakeByHunt)[huntId];
			if (stashed) {
				brief = stashed.brief;
				mandate = stashed.mandate;
				diffRows = stashed.mandate_diff ?? [];
				changed = new Set(diffRows.map((d) => d.field));
			} else {
				const hunt = await getHunt(huntId);
				brief = hunt.brief;
				mandate = hunt.mandate;
			}
			capInput = mandate.cap_landed_eur;
			alertBudgetInput = String(mandate.alert_budget_per_week);
		} catch (e) {
			error = e.message;
		}
	}

	async function patch(fields) {
		error = '';
		try {
			mandate = await patchMandate(huntId, fields);
			capInput = mandate.cap_landed_eur;
			alertBudgetInput = String(mandate.alert_budget_per_week);
		} catch (e) {
			error = e.message;
		}
	}

	async function confirm() {
		busy = true;
		error = '';
		try {
			await confirmHunt(huntId);
			if (mandate.mode === 'IMMEDIATE') {
				const res = await runImmediate(huntId);
				stash(immediateByHunt, huntId, res);
				goto(`/hunt/${huntId}/immediate`);
			} else {
				await startHunt(huntId);
				goto(`/hunt/${huntId}/monitor`);
			}
		} catch (e) {
			error = e.message;
			busy = false;
		}
	}
</script>

<svelte:head><title>SolidHunt — Confirm mandate</title></svelte:head>

{#if error}
	<div class="banner error" role="alert">{error}</div>
{/if}

{#if mandate}
	<h1>Confirm your mandate</h1>
	<p class="muted">
		{brief?.product_query}{brief?.style_code ? ` · ${brief.style_code}` : ''}
		{#if brief?.size_eu}· EU {brief.size_eu}{/if}
	</p>

	{#if diffRows.length}
		<div class="card diff-card">
			<h3>Changed in the last clarification</h3>
			<ul>
				{#each diffRows as d (d.field)}
					<li class="diff-row">
						<span class="mono">{d.field}</span>: {d.old} → <strong>{d.new}</strong>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<div class="card mandate-card">
		<div class="cap-block" class:highlight={changed.has('mandate.cap_landed_eur')}>
			<span class="small muted">Landed-cost cap</span>
			<span class="cap num">{eur(mandate.cap_landed_eur)}</span>
			<label class="small">
				Edit cap (EUR)
				<input
					type="number"
					step="0.01"
					min="1"
					bind:value={capInput}
					onchange={() => patch({ cap_landed_eur: String(capInput) })}
				/>
			</label>
		</div>

		<dl class="facts">
			<div class:highlight={changed.has('mandate.mode')}>
				<dt>Mode</dt>
				<dd>{mandate.mode}</dd>
			</div>
			<div class:highlight={changed.has('mandate.need_within_ticks')}>
				<dt>Deadline</dt>
				<dd>
					{mandate.need_within_ticks != null
						? `within ${mandate.need_within_ticks} ticks`
						: 'no deadline'}
				</dd>
			</div>
			<div class:highlight={changed.has('mandate.auto_buy')}>
				<dt>Auto-buy</dt>
				<dd>
					{#if mandate.auto_buy?.enabled}
						enabled — within {eur(mandate.auto_buy.within_eur_of_target)} of target{mandate
							.auto_buy.require_stock_low
							? ', only when stock is low'
							: ''}{mandate.auto_buy.require_trust_high
							? ', only high-trust vendors'
							: ''}{mandate.auto_buy.require_colorway_confirmed
							? ', colorway must be confirmed'
							: ''}
					{:else}
						off — SolidHunt asks before buying
					{/if}
				</dd>
			</div>
			<div class:highlight={changed.has('mandate.overcap_ask_band_pct')}>
				<dt>Over-cap ask band</dt>
				<dd>{pct(mandate.overcap_ask_band_pct)} above cap may trigger a one-time ask</dd>
			</div>
			<div class:highlight={changed.has('mandate.expires_tick')}>
				<dt>Mandate expires</dt>
				<dd>tick {mandate.expires_tick}</dd>
			</div>
			<div class:highlight={changed.has('mandate.allow_middlemen')}>
				<dt>Middlemen</dt>
				<dd>
					<label class="inline">
						<input
							type="checkbox"
							checked={mandate.allow_middlemen}
							onchange={(e) => patch({ allow_middlemen: e.currentTarget.checked })}
						/>
						allow forwarding middlemen
					</label>
				</dd>
			</div>
			<div class:highlight={changed.has('mandate.geo_arbitrage')}>
				<dt>Geo arbitrage</dt>
				<dd>
					<select
						value={mandate.geo_arbitrage}
						aria-label="Geo arbitrage policy"
						onchange={(e) => patch({ geo_arbitrage: e.currentTarget.value })}
					>
						{#each ['NEVER', 'ASK', 'ALLOW'] as opt (opt)}
							<option value={opt}>{GEO_ARB_LABEL[opt]}</option>
						{/each}
					</select>
				</dd>
			</div>
			<div class:highlight={changed.has('mandate.alert_budget_per_week')}>
				<dt>Alert budget</dt>
				<dd>
					<label class="inline">
						<input
							type="number"
							min="0"
							max="20"
							class="narrow"
							bind:value={alertBudgetInput}
							onchange={() => patch({ alert_budget_per_week: Number(alertBudgetInput) })}
						/>
						interruptions per week
					</label>
				</dd>
			</div>
		</dl>

		<button class="primary confirm-btn" onclick={confirm} disabled={busy}>
			{busy ? 'Confirming…' : mandate.mode === 'IMMEDIATE' ? 'Confirm & find now' : 'Confirm & start watching'}
		</button>
	</div>
{:else if !error}
	<p class="muted">Loading mandate…</p>
{/if}

<style>
	.mandate-card {
		margin-top: 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.cap-block {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 12px;
		border-radius: var(--radius-card);
		background: var(--surface-soft);
	}

	.cap {
		font-size: 56px;
		line-height: 1;
		font-weight: 700;
	}

	.cap-block label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-width: 200px;
		color: var(--ink-muted);
	}

	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
		gap: 12px;
		margin: 0;
	}

	.facts > div {
		border: 1px solid var(--border);
		border-radius: var(--radius-card);
		padding: 10px 12px;
	}

	/* mandate_diff highlighting — changed authority in red/orange */
	.highlight {
		border-color: var(--state-hold) !important;
		background: #fdf3e5;
	}

	.diff-card {
		border-color: var(--state-hold);
		margin-bottom: 4px;
	}

	.diff-card h3 {
		color: var(--state-hold);
	}

	.diff-card ul {
		margin: 0;
		padding-left: 20px;
	}

	.diff-row {
		color: var(--state-reject);
		font-size: 14px;
	}

	dt {
		font-size: 13px;
		color: var(--ink-muted);
		margin-bottom: 2px;
	}

	dd {
		margin: 0;
		font-weight: 600;
	}

	label.inline {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-weight: 400;
	}

	input.narrow {
		width: 72px;
	}

	.confirm-btn {
		align-self: flex-start;
		font-size: 18px;
		padding: 12px 32px;
	}
</style>
