<script>
	// Screen ② — Mandate Confirm, ChatGPT-style: one big editable ceiling, a
	// plain-language promise, one dominant CTA. Everything technical lives
	// under "Advanced". Editable fields PATCH /hunts/{id}/mandate on change
	// (pre-confirm only); Confirm → POST confirm, then run_immediate (③a) or
	// start (③b) by mode. The card and title carry view-transition-names, so
	// navigating from the prompt morphs the composer into this card.
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
	import AuroraBackdrop from '$lib/components/AuroraBackdrop.svelte';

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

	// One sentence, no jargon: what SolidHunt will actually do. Ticks are
	// simulated days, so they read as days here.
	const promise = $derived.by(() => {
		if (!mandate) return '';
		if (mandate.mode === 'IMMEDIATE') {
			return 'SolidHunt will find the best qualifying deal on the market right now — and ask you first about anything unusual.';
		}
		const buying = mandate.auto_buy?.enabled
			? 'strike the moment a qualifying deal appears'
			: 'ask you before it buys';
		const deadline =
			mandate.need_within_ticks != null
				? ` You need it within ${mandate.need_within_ticks} days.`
				: '';
		return `SolidHunt will watch every verified offer for up to ${mandate.expires_tick} days and ${buying}.${deadline}`;
	});

	// "mandate.cap_landed_eur" → "price ceiling", for the friendly diff note
	const FIELD_LABEL = {
		'mandate.cap_landed_eur': 'price ceiling',
		'mandate.mode': 'mode',
		'mandate.need_within_ticks': 'deadline (days)',
		'mandate.expires_tick': 'watch window (days)',
		'brief.size_eu': 'size',
		'brief.product_query': 'product'
	};
	const friendly = (field) =>
		FIELD_LABEL[field] ?? field.split('.').pop().replaceAll('_', ' ');

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

<svelte:head><title>SolidHunt — Confirm the hunt</title></svelte:head>

<AuroraBackdrop />

<section class="confirm">
	{#if error}
		<div class="banner error" role="alert">{error}</div>
	{/if}

	{#if mandate}
		<header class="hero">
			<h1>Ready to hunt</h1>
			<p class="muted product">
				{brief?.product_query}{brief?.style_code ? ` · ${brief.style_code}` : ''}
				{#if brief?.size_eu}· EU {brief.size_eu}{/if}
			</p>
		</header>

		{#if diffRows.length}
			<div class="note" role="status">
				Updated from your answers —
				{#each diffRows as d, i (d.field)}
					{i > 0 ? ' · ' : ''}{friendly(d.field)}: <s>{d.old ?? '—'}</s> <strong>{d.new}</strong>
				{/each}
			</div>
		{/if}

		<div class="card mandate">
			<div class="ceiling" class:highlight={changed.has('mandate.cap_landed_eur')}>
				<span class="small muted">Your all-in ceiling — shipping and taxes included</span>
				<div class="cap-edit num">
					<span aria-hidden="true">€</span>
					<input
						type="text"
						inputmode="decimal"
						bind:value={capInput}
						aria-label="All-in price ceiling in euros"
						style:width="{String(capInput).length + 1}ch"
						onfocus={(e) => e.currentTarget.select()}
						onchange={() => patch({ cap_landed_eur: String(capInput).trim() })}
						onkeydown={(e) => {
							if (e.key === 'Enter') e.currentTarget.blur();
						}}
					/>
				</div>
				<span class="small muted edit-hint">Tap the number to change it</span>
			</div>

			<p class="promise">{promise}</p>

			<button class="primary cta" onclick={confirm} disabled={busy}>
				{busy ? 'Starting…' : mandate.mode === 'IMMEDIATE' ? 'Find it now' : 'Start watching'}
			</button>
			<p class="muted small reassure">
				Nothing is bought outside this mandate, and you can stop the hunt anytime.
			</p>

			<details class="advanced">
				<summary>Advanced settings</summary>
				<div class="adv-rows">
					<label class="adv-row" class:highlight={changed.has('mandate.geo_arbitrage')}>
						<span>Buying from cheaper countries</span>
						<select
							value={mandate.geo_arbitrage}
							onchange={(e) => patch({ geo_arbitrage: e.currentTarget.value })}
						>
							{#each ['NEVER', 'ASK', 'ALLOW'] as opt (opt)}
								<option value={opt}>{GEO_ARB_LABEL[opt]}</option>
							{/each}
						</select>
					</label>

					<label class="adv-row" class:highlight={changed.has('mandate.allow_middlemen')}>
						<span>Reshipping through a forwarding service</span>
						<input
							type="checkbox"
							checked={mandate.allow_middlemen}
							onchange={(e) => patch({ allow_middlemen: e.currentTarget.checked })}
						/>
					</label>

					<label class="adv-row" class:highlight={changed.has('mandate.alert_budget_per_week')}>
						<span>Interruptions allowed per week</span>
						<input
							type="number"
							min="0"
							max="20"
							class="narrow"
							bind:value={alertBudgetInput}
							onchange={() => patch({ alert_budget_per_week: Number(alertBudgetInput) })}
						/>
					</label>

					<p class="small muted adv-note">
						A standout deal up to {pct(mandate.overcap_ask_band_pct)} over your ceiling
						({eur(mandate.cap_landed_eur)}) may trigger a single ask — never a purchase.
					</p>
				</div>
			</details>
		</div>
	{:else if !error}
		<p class="muted center">Loading…</p>
	{/if}
</section>

<style>
	.confirm {
		min-height: calc(100dvh - 200px);
		max-width: 620px;
		margin: 0 auto;
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 20px;
	}

	.hero {
		text-align: center;
	}

	.hero h1 {
		font-size: clamp(32px, 5vw, 44px);
		margin: 0 0 10px;
		view-transition-name: sh-title; /* pairs with the prompt-page headline */
	}

	.product {
		margin: 0;
		font-size: 17px;
	}

	/* friendly clarify-diff note — amber = "changed authority", per brand */
	.note {
		border: 1px solid var(--state-hold);
		background: #fdf3e5;
		color: var(--state-hold);
		border-radius: var(--radius-card);
		padding: 10px 16px;
		font-size: 14px;
		text-align: center;
	}

	.note s {
		opacity: 0.6;
	}

	.mandate {
		border-radius: 16px;
		padding: 24px;
		box-shadow: 0 10px 36px rgb(8 8 8 / 9%);
		display: flex;
		flex-direction: column;
		gap: 16px;
		view-transition-name: sh-card; /* pairs with the prompt-page composer */
	}

	.ceiling {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		padding: 16px;
		border-radius: var(--radius-card);
		background: var(--surface-soft);
		text-align: center;
	}

	.cap-edit {
		display: inline-flex;
		align-items: baseline;
		font-size: 56px;
		font-weight: 700;
		line-height: 1.1;
	}

	.cap-edit input {
		font-size: inherit;
		font-weight: inherit;
		font-family: inherit;
		font-variant-numeric: tabular-nums;
		color: var(--ink);
		background: transparent;
		border: none;
		padding: 0;
		min-width: 2ch;
		max-width: 8ch;
	}

	.cap-edit input:focus-visible {
		outline: none;
		box-shadow: none;
		border-bottom: 3px solid var(--brand-solid);
	}

	.edit-hint {
		font-size: 13px;
	}

	.promise {
		margin: 0;
		font-size: 17px;
		text-align: center;
		max-width: 460px;
		align-self: center;
	}

	.cta {
		font-size: 18px;
		padding: 14px 32px;
		width: 100%;
	}

	.reassure {
		margin: -6px 0 0;
		text-align: center;
	}

	/* ---- advanced disclosure ---- */
	.advanced summary {
		cursor: pointer;
		font-size: 14px;
		color: var(--ink-muted);
		text-align: center;
		list-style: none;
	}

	.advanced summary::-webkit-details-marker {
		display: none;
	}

	.advanced summary::after {
		content: ' ▾';
	}

	.advanced[open] summary::after {
		content: ' ▴';
	}

	.adv-rows {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 12px;
	}

	.adv-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		border: 1px solid var(--border);
		border-radius: var(--radius-card);
		padding: 10px 14px;
		font-size: 14px;
		cursor: pointer;
	}

	.adv-note {
		margin: 4px 0 0;
		text-align: center;
	}

	input.narrow {
		width: 64px;
	}

	/* mandate_diff highlighting — changed authority in amber */
	.highlight {
		border: 1px solid var(--state-hold) !important;
		background: #fdf3e5;
	}

	.center {
		text-align: center;
	}
</style>
