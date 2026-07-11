<script>
	// Screen ③a — Immediate Result. BUY → winner card with the full line-item
	// table; ESCALATE_NONE_FOUND → ranked near-misses ("approvable" badge comes
	// straight from the eligibility field) + a prominent "Switch to monitor".
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { get } from 'svelte/store';
	import { getReceipts, startHunt } from '$lib/api.js';
	import { immediateByHunt } from '$lib/stores.js';
	import { eur } from '$lib/format.js';
	import LineItemTable from '$lib/components/LineItemTable.svelte';
	import ActionBadge from '$lib/components/ActionBadge.svelte';

	const huntId = page.params.id;

	let result = $state(null); // {action, near_misses, receipt, ...}
	let busy = $state(false);
	let error = $state('');

	const receipt = $derived(result?.receipt ?? null);
	const winner = $derived(receipt?.chosen ?? null);

	$effect(() => {
		load();
	});

	async function load() {
		const stashed = get(immediateByHunt)[huntId];
		if (stashed) {
			result = stashed;
			return;
		}
		// Refresh fallback: rebuild the same shape from the stored receipt.
		try {
			const rows = await getReceipts(huntId);
			const r = rows[rows.length - 1];
			if (!r) {
				error = 'No immediate result found for this hunt.';
				return;
			}
			result = {
				action: r.action,
				receipt: r,
				near_misses: (r.considered ?? []).map((e) => ({
					listing_id: e.quote.listing_id,
					landed_eur: e.quote.landed_eur,
					reasons: e.gate_failures?.length ? e.gate_failures : ['qualifies'],
					eligibility: e.eligibility,
					approvable: e.eligibility === 'OVER_CAP_BAND'
				}))
			};
		} catch (e) {
			error = e.message;
		}
	}

	async function switchToMonitor() {
		busy = true;
		error = '';
		try {
			await startHunt(huntId);
			goto(`/hunt/${huntId}/monitor`);
		} catch (e) {
			error = e.message;
			busy = false;
		}
	}
</script>

<svelte:head><title>SolidHunt — Immediate result</title></svelte:head>

{#if error}
	<div class="banner error" role="alert">{error}</div>
{/if}

{#if result}
	{#if result.action === 'BUY' && winner}
		<h1>Deal found at {eur(winner.quote.landed_eur)} delivered</h1>
		<div class="card winner">
			<header>
				<ActionBadge action="BUY" />
				<span class="mono">{winner.quote.listing_id}</span>
			</header>
			<LineItemTable items={winner.quote.line_items} landed={winner.quote.landed_eur} />
			<p class="small muted">
				ETA {winner.quote.eta_ticks} ticks · trust {winner.trust} · decided by
				{receipt.decided_by}
			</p>
			{#if receipt.reasons?.length}
				<ul class="small">
					{#each receipt.reasons as reason (reason)}
						<li>{reason}</li>
					{/each}
				</ul>
			{/if}
		</div>
	{:else}
		<h1>Nothing qualifies right now</h1>
		{#if receipt?.reasons?.length}
			<p class="muted">{receipt.reasons.join(' · ')}</p>
		{/if}

		{#if result.near_misses?.length}
			<h3>Closest misses</h3>
			<ol class="near-misses">
				{#each result.near_misses as nm (nm.listing_id)}
					<li class="card near-miss">
						<div class="nm-head">
							<span class="mono">{nm.listing_id}</span>
							<span class="num landed">{eur(nm.landed_eur)}</span>
							{#if nm.approvable}
								<span class="badge badge-alert">approvable</span>
							{/if}
						</div>
						<p class="small muted reasons">{nm.reasons.join(' · ')}</p>
					</li>
				{/each}
			</ol>
		{/if}

		<button class="primary switch-btn" onclick={switchToMonitor} disabled={busy}>
			{busy ? 'Starting…' : 'Switch to monitor — keep watching for me'}
		</button>
	{/if}
{:else if !error}
	<p class="muted">Loading result…</p>
{/if}

<style>
	.winner {
		max-width: 560px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.winner header {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.near-misses {
		list-style: none;
		padding: 0;
		margin: 0 0 24px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.nm-head {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.nm-head .landed {
		font-weight: 700;
	}

	.reasons {
		margin: 4px 0 0;
	}

	.switch-btn {
		font-size: 18px;
		padding: 12px 32px;
	}
</style>
