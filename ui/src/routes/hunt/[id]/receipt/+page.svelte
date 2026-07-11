<script>
	// Screen ④ — Purchase Receipt. Fetches GET /hunts/{id}/receipts, finds the
	// BUY receipt, renders the full receipt card: line items summing to landed,
	// escalation tier, decided_by, stopping snapshot, reasons.
	import { page } from '$app/state';
	import { getReceipts } from '$lib/api.js';
	import { eur } from '$lib/format.js';
	import LineItemTable from '$lib/components/LineItemTable.svelte';
	import ActionBadge from '$lib/components/ActionBadge.svelte';

	const huntId = page.params.id;

	let buy = $state(null);
	let loaded = $state(false);
	let error = $state('');

	const quote = $derived(buy?.chosen?.quote ?? null);

	$effect(() => {
		load();
	});

	async function load() {
		try {
			const rows = await getReceipts(huntId);
			buy = rows.find((r) => r.action === 'BUY') ?? null;
		} catch (e) {
			error = e.message;
		} finally {
			loaded = true;
		}
	}
</script>

<svelte:head><title>SolidHunt — Purchase receipt</title></svelte:head>

{#if error}
	<div class="banner error" role="alert">{error}</div>
{/if}

{#if buy && quote}
	<h1>Deal found at {eur(quote.landed_eur)} delivered</h1>
	<p class="muted">Hunt {huntId} · receipt {buy.id}</p>

	<div class="card receipt">
		<header>
			<ActionBadge action={buy.action} />
			<span class="muted small num">tick {buy.tick}</span>
			<span class="mono">{quote.listing_id}</span>
		</header>

		<LineItemTable items={quote.line_items} landed={quote.landed_eur} />

		<dl class="meta">
			<div>
				<dt>Escalation tier</dt>
				<dd>{buy.escalation_tier ?? '—'}</dd>
			</div>
			<div>
				<dt>Decided by</dt>
				<dd>{buy.decided_by}</dd>
			</div>
			<div>
				<dt>Trust</dt>
				<dd class="num">{buy.chosen.trust}</dd>
			</div>
			<div>
				<dt>Route</dt>
				<dd>{quote.kind}{quote.middleman_id ? ` via ${quote.middleman_id}` : ''} · seen from {quote.observation_geo}</dd>
			</div>
			<div>
				<dt>ETA</dt>
				<dd class="num">{quote.eta_ticks} ticks</dd>
			</div>
			{#if buy.stopping}
				<div>
					<dt>Stopping snapshot</dt>
					<dd class="num">
						p_better {buy.stopping.p_better ?? '—'} vs θ {buy.stopping.theta}
						· {buy.stopping.n_obs} observations · horizon {buy.stopping.horizon}
					</dd>
				</div>
			{/if}
		</dl>

		{#if buy.reasons?.length}
			<div>
				<h3>Why SolidHunt bought</h3>
				<ul>
					{#each buy.reasons as reason (reason)}
						<li>{reason}</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>
{:else if loaded && !error}
	<h1>No purchase yet</h1>
	<p class="muted">
		This hunt has no BUY receipt. <a href="/hunt/{huntId}/monitor">Back to the monitor</a>.
	</p>
{:else if !loaded}
	<p class="muted">Loading receipt…</p>
{/if}

<style>
	.receipt {
		max-width: 640px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.receipt header {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.meta {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 12px;
		margin: 0;
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

	ul {
		margin: 0;
		padding-left: 20px;
		font-size: 14px;
	}
</style>
