<script>
	// Screen ④ — Purchase Receipt, in the confirm-screen design language:
	// aurora, one centered card, plain words. The line-item arithmetic stays
	// front and center (brand: cost math is a receipt, not fine print).
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { getReceipts } from '$lib/api.js';
	import { eur } from '$lib/format.js';
	import LineItemTable from '$lib/components/LineItemTable.svelte';
	import AuroraBackdrop from '$lib/components/AuroraBackdrop.svelte';

	const huntId = page.params.id;

	let buy = $state(null);
	let loaded = $state(false);
	let error = $state('');

	const quote = $derived(buy?.chosen?.quote ?? null);

	// plain-language "who decided" line — derived only from receipt fields
	const decidedLine = $derived.by(() => {
		if (!buy) return '';
		if (buy.decided_by === 'HUMAN') {
			return 'Bought after your one-time approval — the price was slightly over your ceiling and you said yes.';
		}
		return 'Bought by SolidHunt, inside your mandate — no rules were bent.';
	});

	const ROUTE_LABEL = {
		DOMESTIC: 'shipped domestically',
		INTL_DIRECT: 'shipped internationally',
		INTL_FORWARD: 'reshipped via a forwarding service'
	};

	onMount(load); // not $effect — see confirm page note (self-retriggering effect)

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

<svelte:head><title>SolidHunt — Your receipt</title></svelte:head>

<AuroraBackdrop />

<section class="wrap">
	{#if error}
		<div class="banner error" role="alert">{error}</div>
	{/if}

	{#if buy && quote}
		<header class="hero">
			<h1>Yours for {eur(quote.landed_eur)}, all-in</h1>
			<p class="muted sub">
				Secured on day {buy.tick} · arrives in about {quote.eta_ticks} days
				{#if ROUTE_LABEL[quote.kind]}· {ROUTE_LABEL[quote.kind]}{/if}
			</p>
		</header>

		<div class="card receipt">
			<LineItemTable items={quote.line_items} landed={quote.landed_eur} />

			<p class="decided">{decidedLine}</p>

			{#if buy.reasons?.length}
				<div class="why">
					<h3>Why this one</h3>
					<ul>
						{#each buy.reasons as reason (reason)}
							<li>{reason}</li>
						{/each}
					</ul>
				</div>
			{/if}

			<details class="fine-print">
				<summary>The fine print</summary>
				<dl class="meta">
					<div>
						<dt>Listing</dt>
						<dd class="mono">{quote.listing_id}</dd>
					</div>
					<div>
						<dt>Vendor trust</dt>
						<dd class="num">{buy.chosen.trust}</dd>
					</div>
					<div>
						<dt>Seen from</dt>
						<dd>{quote.observation_geo}</dd>
					</div>
					<div>
						<dt>Decision</dt>
						<dd>{buy.escalation_tier ?? '—'} · {buy.decided_by} · receipt {buy.id}</dd>
					</div>
					{#if buy.stopping}
						<div class="span2">
							<dt>Why now and not later</dt>
							<dd class="num">
								Chance a better deal was still coming: {Math.round(
									parseFloat(buy.stopping.p_better ?? '0') * 100
								)}% — below the {Math.round(parseFloat(buy.stopping.theta) * 100)}% bar,
								after {buy.stopping.n_obs} price checks.
							</dd>
						</div>
					{/if}
				</dl>
			</details>
		</div>

		<a class="again" href="/">Start another hunt</a>
	{:else if loaded && !error}
		<header class="hero">
			<h1>No purchase yet</h1>
			<p class="muted sub">
				This hunt has no receipt. <a href="/hunt/{huntId}/monitor">Back to the monitor</a>.
			</p>
		</header>
	{:else if !loaded}
		<p class="muted center">Loading…</p>
	{/if}
</section>

<style>
	.wrap {
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
		font-size: clamp(30px, 5vw, 42px);
		margin: 0 0 10px;
		view-transition-name: sh-title;
	}

	.sub {
		margin: 0;
		font-size: 16px;
	}

	.receipt {
		border-radius: 16px;
		padding: 24px;
		box-shadow: 0 10px 36px rgb(8 8 8 / 9%);
		display: flex;
		flex-direction: column;
		gap: 16px;
		view-transition-name: sh-card; /* morphs into the composer on "Start another hunt" */
	}

	.decided {
		margin: 0;
		font-size: 16px;
		text-align: center;
	}

	.why h3 {
		font-size: 15px;
		margin-bottom: 4px;
	}

	.why ul {
		margin: 0;
		padding-left: 20px;
		font-size: 14px;
	}

	.fine-print summary {
		cursor: pointer;
		font-size: 14px;
		color: var(--ink-muted);
		text-align: center;
		list-style: none;
	}

	.fine-print summary::-webkit-details-marker {
		display: none;
	}

	.fine-print summary::after {
		content: ' ▾';
	}

	.fine-print[open] summary::after {
		content: ' ▴';
	}

	.meta {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 12px;
		margin: 12px 0 0;
	}

	.meta .span2 {
		grid-column: 1 / -1;
	}

	dt {
		font-size: 13px;
		color: var(--ink-muted);
		margin-bottom: 2px;
	}

	dd {
		margin: 0;
		font-weight: 600;
		font-size: 14px;
	}

	.again {
		align-self: center;
		font-size: 15px;
	}

	.center {
		text-align: center;
	}
</style>
