<script>
	// Order lifecycle events: PLACED, CONFIRMED (+delivery), CANCELLED_BY_MERCHANT
	// (red, + refund note), REFUNDED. Style derives only from the state field.
	import { ORDER_BADGE, shortHash } from '$lib/format.js';

	let { tick, order } = $props();
	const badge = $derived(ORDER_BADGE[order.state] ?? { label: order.state, cls: 'badge-hold' });
</script>

<article class="card order-card" class:cancelled={order.state === 'CANCELLED_BY_MERCHANT'}>
	<header>
		<span class="badge {badge.cls}">{badge.label}</span>
		<span class="muted small num">day {tick}</span>
	</header>
	<div class="body small">
		{#if order.listing_id}
			<span class="mono">{order.listing_id}</span>
		{/if}
		{#if order.quote_hash}
			<span class="mono" title={order.quote_hash}>quote {shortHash(order.quote_hash)}</span>
		{/if}
		{#if order.state === 'CONFIRMED' && order.delivery_at_tick != null}
			<span>Arriving around day {order.delivery_at_tick}.</span>
		{/if}
		{#if order.state === 'CANCELLED_BY_MERCHANT'}
			<span>
				Merchant cancelled the order.
				{#if order.refund_at_tick != null}
					Refund due around day {order.refund_at_tick}.
				{/if}
				The hunt resumes automatically.
			</span>
		{/if}
		{#if order.state === 'REFUNDED'}
			<span>Refund settled.</span>
		{/if}
	</div>
</article>

<style>
	.order-card header {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 6px;
	}

	.order-card.cancelled {
		border-color: var(--state-reject);
	}

	.body {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
</style>
