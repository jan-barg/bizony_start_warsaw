<script>
	// One receipt event as a feed card: action badge, tick, reasons, and (when
	// the receipt has a chosen quote) landed + expandable line items.
	import ActionBadge from './ActionBadge.svelte';
	import LineItemTable from './LineItemTable.svelte';
	import { eur } from '$lib/format.js';

	let { receipt } = $props();
	const quote = $derived(receipt.chosen?.quote ?? null);
</script>

<article class="card receipt-card">
	<header>
		<ActionBadge action={receipt.action} />
		<span class="muted small num">day {receipt.tick}</span>
		{#if receipt.escalation_tier}
			<span class="muted small">tier {receipt.escalation_tier}</span>
		{/if}
		<span class="muted small">by {receipt.decided_by}</span>
	</header>

	{#if receipt.reasons?.length}
		<ul class="reasons">
			{#each receipt.reasons as reason (reason)}
				<li>{reason}</li>
			{/each}
		</ul>
	{/if}

	{#if quote}
		<p class="landed num">
			{quote.listing_id} — landed <strong>{eur(quote.landed_eur)}</strong>
		</p>
		<details>
			<summary class="small">Line items</summary>
			<LineItemTable items={quote.line_items} landed={quote.landed_eur} />
		</details>
	{/if}
</article>

<style>
	.receipt-card header {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 8px;
	}

	.reasons {
		margin: 0;
		padding-left: 20px;
		font-size: 14px;
	}

	.landed {
		margin: 8px 0 4px;
		font-size: 14px;
	}

	details {
		margin-top: 4px;
	}

	summary {
		cursor: pointer;
		color: var(--ink-muted);
	}
</style>
