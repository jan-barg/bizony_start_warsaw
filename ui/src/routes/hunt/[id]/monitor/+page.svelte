<script>
	// Screen ③b — Monitor Dashboard. EventSource on /hunts/{id}/events
	// (envelope {type, tick, payload}; named events tick/receipt/ask/status/
	// order/done). Pure consumer: chart + feed render receipt fields only.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		getHunt,
		eventsUrl,
		approveAsk,
		declineAsk,
		revokeHunt
	} from '$lib/api.js';
	import PriceChart from '$lib/components/PriceChart.svelte';
	import ReceiptCard from '$lib/components/ReceiptCard.svelte';
	import OrderCard from '$lib/components/OrderCard.svelte';
	import AskModal from '$lib/components/AskModal.svelte';

	const huntId = page.params.id;
	const EVENT_TYPES = ['tick', 'receipt', 'ask', 'status', 'order', 'done'];

	let mandate = $state(null);
	let currentTick = $state(0);
	let feed = $state([]); // newest first: {key, kind, tick, payload}
	let points = $state([]); // {tick, y, landedStr, action} for the chart
	let pendingAsk = $state(null);
	let clockPaused = $state(false); // server-side pause (pending ask)
	let paused = $state(false); // client-side play/pause
	let status = $state('RUNNING');
	let finalStatus = $state(null); // set by the done event
	let busy = $state(false);
	let error = $state('');

	let es = null;
	let buffer = []; // envelopes held while client-side paused
	let seq = 0;

	function pushFeed(kind, tick, payload) {
		feed.unshift({ key: seq++, kind, tick, payload });
	}

	function apply(env) {
		const { type, tick, payload } = env;
		if (type === 'tick') {
			currentTick = tick;
		} else if (type === 'receipt') {
			pushFeed('receipt', tick, payload);
			const quote = payload.chosen?.quote ?? payload.considered?.[0]?.quote;
			if (quote) {
				// parseFloat ONLY for chart geometry; the string is kept for display
				points.push({
					tick,
					y: parseFloat(quote.landed_eur),
					landedStr: quote.landed_eur,
					action: payload.action
				});
			}
		} else if (type === 'ask') {
			pendingAsk = payload;
			clockPaused = true;
		} else if (type === 'status') {
			status = payload.status;
			if (payload.clock === 'paused') clockPaused = true;
			if (payload.clock === 'running') clockPaused = false;
			if (payload.status === 'REVOKED') {
				pendingAsk = null;
				clockPaused = false;
			}
			if (payload.ask_resolution || payload.status === 'REVOKED') {
				pushFeed('status', tick, payload);
			}
		} else if (type === 'order') {
			pushFeed('order', tick, payload);
		} else if (type === 'done') {
			finalStatus = payload.final_status;
			status = payload.final_status;
			es?.close();
			es = null;
			if (payload.final_status === 'PURCHASED') {
				// short beat so the BUY card is visible before navigating to ④
				setTimeout(() => goto(`/hunt/${huntId}/receipt`), 1500);
			}
		}
	}

	function handle(env) {
		if (paused && env.type !== 'done') {
			buffer.push(env);
		} else {
			if (paused) {
				flush();
			}
			apply(env);
		}
	}

	function flush() {
		const held = buffer;
		buffer = [];
		for (const env of held) apply(env);
	}

	function togglePause() {
		paused = !paused;
		if (!paused) flush();
	}

	async function resolveAsk(approve) {
		if (!pendingAsk || busy) return;
		busy = true;
		error = '';
		try {
			await (approve ? approveAsk : declineAsk)(pendingAsk.id);
			pendingAsk = null; // status event will flip the clock indicator
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}

	async function revoke() {
		if (!window.confirm('Revoke the mandate? The hunt stops this tick and will not buy.')) return;
		error = '';
		try {
			await revokeHunt(huntId);
		} catch (e) {
			error = e.message;
		}
	}

	onMount(() => {
		(async () => {
			try {
				const hunt = await getHunt(huntId);
				mandate = hunt.mandate;
				status = hunt.status;
				if (hunt.status === 'PURCHASED') {
					goto(`/hunt/${huntId}/receipt`);
					return;
				}
				if (hunt.status !== 'RUNNING' && hunt.status !== 'PENDING_ASK') {
					error = `Hunt is ${hunt.status} — start it from the confirm screen before monitoring.`;
					return;
				}
				es = new EventSource(eventsUrl(huntId));
				for (const t of EVENT_TYPES) {
					es.addEventListener(t, (e) => handle(JSON.parse(e.data)));
				}
				es.onerror = () => {
					if (!finalStatus) {
						error = 'Event stream interrupted — is the API still running?';
					}
					es?.close();
					es = null;
				};
			} catch (e) {
				error = e.message;
			}
		})();

		return () => {
			es?.close();
			es = null;
		};
	});
</script>

<svelte:head><title>SolidHunt — Monitor</title></svelte:head>

<div class="head-row">
	<h1>Watching the market</h1>
	<div class="controls">
		<span class="state small" role="status">
			{#if finalStatus}
				{finalStatus}
			{:else if clockPaused}
				clock paused — awaiting your decision
			{:else if paused}
				display paused
			{:else}
				<span class="pulse" aria-hidden="true"></span> hunting · tick {currentTick}
			{/if}
		</span>
		<button onclick={togglePause} disabled={!!finalStatus}>
			{paused ? 'Resume' : 'Pause'}
		</button>
		<button class="danger" onclick={revoke} disabled={!!finalStatus}>Revoke mandate</button>
	</div>
</div>

{#if error}
	<div class="banner error" role="alert">{error}</div>
{/if}

{#if finalStatus === 'REVOKED' || status === 'REVOKED'}
	<div class="banner terminal" role="status">
		Mandate revoked. The hunt is over — nothing will be bought.
	</div>
{:else if finalStatus === 'PURCHASED'}
	<div class="banner success" role="status">
		Purchase complete — opening your receipt…
		<a href="/hunt/{huntId}/receipt">View receipt</a>
	</div>
{/if}

<PriceChart {points} cap={mandate?.cap_landed_eur ?? null} {currentTick} />

<h2 class="feed-title">Event feed</h2>
<div class="feed" aria-live="polite">
	{#each feed as item (item.key)}
		{#if item.kind === 'receipt'}
			<ReceiptCard receipt={item.payload} />
		{:else if item.kind === 'order'}
			<OrderCard tick={item.tick} order={item.payload} />
		{:else if item.kind === 'status'}
			<div class="card status-card small">
				{#if item.payload.status === 'REVOKED'}
					<span class="badge badge-escalate">REVOKED</span> Mandate revoked at tick {item.tick}.
				{:else if item.payload.ask_resolution}
					<span class="badge badge-ask">ASK {item.payload.ask_resolution}</span>
					Clock resumed at tick {item.tick}.
				{/if}
			</div>
		{/if}
	{:else}
		<p class="muted">Waiting for the first receipt…</p>
	{/each}
</div>

{#if pendingAsk}
	<AskModal
		ask={pendingAsk}
		{busy}
		onapprove={() => resolveAsk(true)}
		ondecline={() => resolveAsk(false)}
	/>
{/if}

<style>
	.head-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
		margin-bottom: 16px;
	}

	.head-row h1 {
		margin: 0;
	}

	.controls {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.state {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--ink-muted);
		font-variant-numeric: tabular-nums;
	}

	.feed-title {
		margin-top: 24px;
	}

	.feed {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.status-card {
		color: var(--ink-muted);
		display: flex;
		align-items: center;
		gap: 8px;
	}
</style>
