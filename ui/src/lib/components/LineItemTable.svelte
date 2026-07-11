<script>
	// Renders receipt line items exactly as they arrive. The total row shows
	// landed_eur from the quote — the UI never recomputes the sum.
	import { eur } from '$lib/format.js';

	let { items = [], landed } = $props();
</script>

<table class="line-items">
	<thead>
		<tr>
			<th scope="col">Code</th>
			<th scope="col">Item</th>
			<th scope="col" class="amount">Amount</th>
		</tr>
	</thead>
	<tbody>
		{#each items as li (li.code + li.label + li.amount_eur)}
			<tr>
				<td class="mono">{li.code}</td>
				<td>{li.label}</td>
				<td class="amount num">{eur(li.amount_eur)}</td>
			</tr>
		{/each}
		<tr class="total">
			<td></td>
			<td>Landed total</td>
			<td class="amount num">{eur(landed)}</td>
		</tr>
	</tbody>
</table>
