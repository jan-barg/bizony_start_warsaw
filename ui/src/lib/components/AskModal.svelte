<script>
	// Blocking consent modal for an `ask` event. The world clock is paused
	// server-side while the ask is pending — shown explicitly.
	import LineItemTable from './LineItemTable.svelte';
	import { ASK_KIND_LABEL, eur, pct, shortHash } from '$lib/format.js';

	let { ask, busy = false, onapprove, ondecline } = $props();
	const quote = $derived(ask.quote);
</script>

<div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="ask-title">
	<div class="modal">
		<header>
			<span class="badge badge-ask">{ASK_KIND_LABEL[ask.kind] ?? ask.kind}</span>
			<span class="paused small" role="status">
				<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
					<rect x="2" y="1" width="3.5" height="12" rx="1" fill="currentColor" />
					<rect x="8.5" y="1" width="3.5" height="12" rx="1" fill="currentColor" />
				</svg>
				World clock paused
			</span>
		</header>

		<h3 id="ask-title">Your approval is needed</h3>
		<p class="narrative">{ask.narrative}</p>

		<LineItemTable items={quote.line_items} landed={quote.landed_eur} />

		<table class="line-items facts">
			<tbody>
				<tr>
					<td>Landed cost</td>
					<td class="amount num"><strong>{eur(quote.landed_eur)}</strong></td>
				</tr>
				<tr>
					<td>ETA</td>
					<td class="amount num">{quote.eta_ticks} ticks</td>
				</tr>
				<tr>
					<td>Estimated cancellation risk</td>
					<td class="amount num">{pct(quote.p_cancel_est)}</td>
				</tr>
				{#if ask.comparison_landed_eur != null}
					<tr>
						<td>Best alternative landed</td>
						<td class="amount num">{eur(ask.comparison_landed_eur)}</td>
					</tr>
				{/if}
			</tbody>
		</table>

		<p class="small muted">
			Approval binds to this exact quote:
			<span class="mono" title={ask.quote_hash}>{shortHash(ask.quote_hash)}</span>
		</p>

		<footer>
			<button class="primary" disabled={busy} onclick={onapprove}>Approve</button>
			<button disabled={busy} onclick={ondecline}>Decline</button>
		</footer>
	</div>
</div>

<style>
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 12px;
	}

	.paused {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--state-hold);
		font-weight: 600;
	}

	.narrative {
		margin: 0 0 16px;
	}

	.facts {
		margin-top: 12px;
	}

	footer {
		display: flex;
		gap: 12px;
		margin-top: 16px;
	}
</style>
