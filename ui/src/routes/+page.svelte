<script>
	// Screen ① — New Hunt. One ChatGPT-style composer over a SoftAurora
	// background (UI-spec.MD). First send POSTs /intake; while the intake
	// returns NEEDS_INFO the same composer becomes the reply box and each send
	// POSTs /intake/{id}/clarify, chat-style, until status is OK.
	import { goto } from '$app/navigation';
	import { fly, slide } from 'svelte/transition';
	import { postIntake, postClarify } from '$lib/api.js';
	import { intakeByHunt, stash } from '$lib/stores.js';
	import SoftAurora from '$lib/components/SoftAurora.svelte';

	// brand: respect reduced motion — collapse every morph to an instant swap
	const reducedMotion =
		typeof window !== 'undefined' &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	const dur = (ms) => (reducedMotion ? 0 : ms);

	let text = $state('');
	let mode = $state('MONITOR');
	let chat = $state([]); // {role: 'user'|'agent', lines: string[]}
	let intakeId = $state(null);
	let busy = $state(false);
	let error = $state('');
	let ta = $state(null);

	const started = $derived(chat.length > 0);
	const modeHint = $derived(
		mode === 'MONITOR'
			? 'Watches the market and strikes at the right moment.'
			: 'Buys the best qualifying deal right now.'
	);

	const examples = [
		'Nike Dunk Low Panda, size 43, under €80 delivered',
		'Omega Seamaster on a €2,400 budget, within 30 days',
		'AirPods Pro under €200 — buy now'
	];

	function onResult(res) {
		if (res.status === 'NEEDS_INFO') {
			intakeId = res.intake_id;
			chat.push({ role: 'agent', lines: res.questions });
			return;
		}
		// OK → hunt created; stash payload for the confirm screen, then navigate.
		stash(intakeByHunt, res.hunt_id, res);
		goto(`/hunt/${res.hunt_id}/confirm`);
	}

	function autogrow() {
		if (!ta) return;
		ta.style.height = 'auto';
		ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
	}

	async function send() {
		const trimmed = text.trim();
		if (!trimmed || busy) return;
		busy = true;
		error = '';
		text = '';
		autogrow();
		try {
			if (intakeId) {
				chat.push({ role: 'user', lines: [trimmed] });
				onResult(await postClarify(intakeId, trimmed));
			} else {
				// Immediate mode: append " now" (the intake parser reads mode from
				// the text) and pass mode explicitly too.
				const finalText =
					mode === 'IMMEDIATE' && !/\bnow\b/i.test(trimmed) ? `${trimmed} now` : trimmed;
				chat = [{ role: 'user', lines: [finalText] }];
				onResult(await postIntake(finalText, mode));
			}
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}

	function onKeydown(e) {
		if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
			e.preventDefault();
			send();
		}
	}

	function useExample(example) {
		text = example;
		autogrow();
		ta?.focus();
	}
</script>

<svelte:head><title>SolidHunt — New hunt</title></svelte:head>

<div class="aurora" aria-hidden="true">
	<SoftAurora
		speed={0.5}
		scale={1.4}
		brightness={1.35}
		color1="#43f27e"
		color2="#a7f9c5"
		bandHeight={0.68}
		bandSpread={1.1}
		layerOffset={2.5}
		mouseInfluence={0.2}
	/>
</div>

<section class="home" class:started>
	<header class="hero">
		<h1>What are we hunting?</h1>
		{#if !started}
			<p class="muted sub" transition:slide={{ duration: dur(320) }}>
				Name the product and your all-in price ceiling. SolidHunt watches, verifies,
				and buys — never breaking your mandate.
			</p>
		{/if}
	</header>

	{#if chat.length}
		<div class="chat" aria-live="polite">
			{#each chat as msg, i (i)}
				<div class="bubble {msg.role}" in:fly={{ y: 14, duration: dur(280) }}>
					{#each msg.lines as line (line)}
						<p class="chat-line">{line}</p>
					{/each}
				</div>
			{/each}
		</div>
	{/if}

	{#if error}
		<div class="banner error" role="alert">{error}</div>
	{/if}

	<div class="composer" class:busy>
		<textarea
			bind:this={ta}
			bind:value={text}
			rows="1"
			placeholder={started
				? 'Your answer…'
				: 'Nike Dunk Low Panda, size 43, under €80 delivered…'}
			aria-label={started ? 'Answer the clarifying question' : 'What are you hunting?'}
			oninput={autogrow}
			onkeydown={onKeydown}
		></textarea>

		<div class="composer-row">
			{#if !started}
				<div
					class="mode-toggle"
					role="group"
					aria-label="Hunt mode"
					transition:slide={{ axis: 'x', duration: dur(280) }}
				>
					<span
						class="slider"
						aria-hidden="true"
						style:transform="translateX({mode === 'MONITOR' ? '0%' : '100%'})"
					></span>
					<button
						type="button"
						class:active={mode === 'MONITOR'}
						aria-pressed={mode === 'MONITOR'}
						onclick={() => (mode = 'MONITOR')}
					>
						Monitor
					</button>
					<button
						type="button"
						class:active={mode === 'IMMEDIATE'}
						aria-pressed={mode === 'IMMEDIATE'}
						onclick={() => (mode = 'IMMEDIATE')}
					>
						Buy now
					</button>
				</div>
			{/if}
			<span class="muted small hint">
				{started ? 'SolidHunt needs a little more to hunt safely.' : modeHint}
			</span>

			<button
				type="button"
				class="send"
				onclick={send}
				disabled={busy || !text.trim()}
				aria-label={started ? 'Send answer' : 'Start the hunt'}
			>
				{#if busy}
					<span class="pulse" aria-hidden="true"></span>
				{:else}
					<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
						<path
							d="M8 13.5V3.6M3.8 7.4 8 3.2l4.2 4.2"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
						/>
					</svg>
				{/if}
			</button>
		</div>
	</div>

	{#if !started}
		<div class="examples" transition:slide={{ duration: dur(300) }}>
			{#each examples as example (example)}
				<button type="button" class="chip" onclick={() => useExample(example)}>
					{example}
				</button>
			{/each}
		</div>
	{/if}
</section>

<style>
	.aurora {
		position: fixed;
		inset: 0;
		z-index: -1;
		pointer-events: none;
	}

	.home {
		min-height: calc(100dvh - 200px);
		max-width: 720px;
		margin: 0 auto;
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 20px;
	}

	/* .started never re-anchors the layout — the page stays centered and every
	   height change (sub/chips collapsing, bubbles arriving) is animated, so
	   the whole view morphs instead of snapping */
	.hero {
		text-align: center;
	}

	.hero h1 {
		font-size: clamp(36px, 6vw, 56px);
		line-height: 1;
		margin: 0 0 12px;
		letter-spacing: -0.02em;
		transition:
			font-size 0.35s ease,
			margin 0.35s ease;
	}

	.started .hero h1 {
		font-size: 28px;
		margin-bottom: 0;
	}

	.sub {
		max-width: 480px;
		margin: 0 auto;
		font-size: 17px;
	}

	/* ---- composer (ChatGPT-inspired; radius intentionally softer than the
	   8px card token — this is the screen's single dominant surface) ---- */
	.composer {
		background: var(--paper);
		border: 1px solid var(--border);
		border-radius: 16px;
		padding: 12px 12px 10px;
		box-shadow: 0 10px 36px rgb(8 8 8 / 9%);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.composer:focus-within {
		box-shadow:
			0 10px 36px rgb(8 8 8 / 9%),
			var(--focus-ring);
	}

	.composer textarea {
		border: none;
		background: transparent;
		resize: none;
		font-size: 17px;
		line-height: 1.5;
		padding: 6px 8px;
		width: 100%;
		max-height: 200px;
	}

	.composer textarea:focus-visible {
		outline: none;
		box-shadow: none;
	}

	.composer-row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.mode-toggle {
		position: relative;
		display: grid;
		grid-template-columns: 1fr 1fr; /* equal cells so the slider maps 0%/100% */
		border: 1px solid var(--border);
		border-radius: var(--radius-control);
		overflow: hidden;
		flex-shrink: 0;
	}

	.mode-toggle .slider {
		position: absolute;
		top: 0;
		left: 0;
		width: 50%;
		height: 100%;
		background: var(--brand-solid);
		transition: transform 0.25s cubic-bezier(0.3, 0.9, 0.4, 1);
	}

	.mode-toggle button {
		position: relative; /* above the slider */
		border: none;
		border-radius: 0;
		background: transparent;
		color: var(--ink-muted);
		font-size: 14px;
		font-weight: 600;
		padding: 6px 14px;
		white-space: nowrap;
		transition: color 0.25s ease;
	}

	.mode-toggle button.active {
		color: var(--ink); /* black on Solid Green, per brand */
	}

	.hint {
		flex: 1;
		min-width: 0;
	}

	.send {
		width: 38px;
		height: 38px;
		flex-shrink: 0;
		margin-left: auto;
		border-radius: 50%;
		border: none;
		background: var(--brand-solid);
		color: var(--ink);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
	}

	.send:hover:not(:disabled) {
		background: #35d96c;
	}

	/* ---- example chips ---- */
	.examples {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 8px;
	}

	.chip {
		font-size: 14px;
		color: var(--ink-muted);
		background: rgb(255 255 255 / 70%);
		padding: 6px 14px;
		border-radius: 999px;
	}

	.chip:hover {
		color: var(--ink);
	}

	.chat-line {
		margin: 0;
	}

	.chat-line + .chat-line {
		margin-top: 6px;
	}

	@media (max-width: 560px) {
		.hint {
			display: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.hero h1,
		.mode-toggle .slider,
		.mode-toggle button {
			transition: none;
		}
	}
</style>
