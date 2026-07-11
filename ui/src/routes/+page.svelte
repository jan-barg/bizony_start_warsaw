<script>
	// Screen ① — New Hunt. Textarea + mode toggle → POST /intake. While the
	// intake returns NEEDS_INFO, clarifying questions render chat-style and
	// each reply POSTs /intake/{id}/clarify until status is OK.
	import { goto } from '$app/navigation';
	import { postIntake, postClarify, postStructuredIntake } from '$lib/api.js';
	import { intakeByHunt, stash } from '$lib/stores.js';

	let text = $state('');
	let mode = $state('MONITOR');
	let chat = $state([]); // {role: 'user'|'agent', lines: string[]}
	let intakeId = $state(null);
	let reply = $state('');
	let busy = $state(false);
	let error = $state('');
	let structured = $state(false);
	let form = $state({ product_query: '', style_code: '', size_eu: '', cap_landed_eur: '' });
	let imageB64 = $state(null);
	let imageName = $state('');

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

	async function submit() {
		const trimmed = text.trim();
		if (!trimmed || busy) return;
		busy = true;
		error = '';
		// Immediate mode: append " now" (the intake parser reads mode from the
		// text) and pass mode explicitly too.
		const finalText =
			mode === 'IMMEDIATE' && !/\bnow\b/i.test(trimmed) ? `${trimmed} now` : trimmed;
		chat = [{ role: 'user', lines: [finalText] }];
		intakeId = null;
		try {
			onResult(await postIntake(finalText, mode, imageB64));
		} catch (e) {
			if (e.status === 503) {
				structured = true;
				error = 'The language model is offline. Use the deterministic form below.';
			} else {
				error = e.message;
			}
		} finally {
			busy = false;
		}
	}

	async function attachScreenshot(event) {
		const file = event.currentTarget.files?.[0];
		if (!file) {
			imageB64 = null;
			imageName = '';
			return;
		}
		const bytes = new Uint8Array(await file.arrayBuffer());
		let binary = '';
		for (const byte of bytes) binary += String.fromCharCode(byte);
		imageB64 = btoa(binary);
		imageName = file.name;
	}

	async function submitStructured() {
		if (!form.product_query.trim() || !form.size_eu || !form.cap_landed_eur || busy) return;
		busy = true;
		error = '';
		try {
			onResult(
				await postStructuredIntake({
					product_query: form.product_query.trim(),
					style_code: form.style_code.trim() || null,
					size_eu: String(form.size_eu),
					cap_landed_eur: String(form.cap_landed_eur),
					mode
				})
			);
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}

	async function sendReply() {
		const trimmed = reply.trim();
		if (!trimmed || !intakeId || busy) return;
		busy = true;
		error = '';
		chat.push({ role: 'user', lines: [trimmed] });
		reply = '';
		try {
			onResult(await postClarify(intakeId, trimmed));
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>SolidHunt — New hunt</title></svelte:head>

<h1>Start a hunt</h1>
<p class="muted">
	Tell SolidHunt what to find and your all-in price ceiling. It watches, verifies,
	and acts without breaking your mandate.
</p>

<div class="card soft intake">
	<label class="small muted" for="hunt-text">What are you hunting?</label>
	<textarea
		id="hunt-text"
		rows="4"
		bind:value={text}
		placeholder="Nike Dunk Low Panda, size 43, under €80 delivered…"
		onkeydown={(e) => {
			if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit();
		}}
	></textarea>

	<div class="controls">
		<fieldset class="mode">
			<legend class="small muted">Mode</legend>
			<label>
				<input type="radio" name="mode" value="MONITOR" bind:group={mode} />
				Monitor — watch and buy at the right moment
			</label>
			<label>
				<input type="radio" name="mode" value="IMMEDIATE" bind:group={mode} />
				Immediate — best qualifying deal right now
			</label>
		</fieldset>
		<button class="primary" onclick={submit} disabled={busy || !text.trim()}>
			{busy ? 'Working…' : 'Start the hunt'}
		</button>
	</div>
	<label class="screenshot small">
		Screenshot <span class="muted">(PNG, JPEG, or WebP; optional)</span>
		<input type="file" accept="image/png,image/jpeg,image/webp" onchange={attachScreenshot} />
		{#if imageName}<span class="muted">Attached: {imageName}</span>{/if}
	</label>
</div>

{#if error}
	<div class="banner error" role="alert">{error}</div>
{/if}

{#if structured}
	<div class="card soft structured-form">
		<h2>Enter hunt details</h2>
		<p class="small muted">These fields are validated by code. Product, size, and cap are never guessed.</p>
		<label>
			Brand, model, and colorway
			<input bind:value={form.product_query} placeholder="Nike Dunk Low Panda" />
		</label>
		<label>
			Style code <span class="muted">(optional)</span>
			<input bind:value={form.style_code} placeholder="DD1391-100" />
		</label>
		<div class="form-row">
			<label>
				EU size
				<input type="number" min="35" max="50" step="0.5" bind:value={form.size_eu} />
			</label>
			<label>
				Maximum landed EUR
				<input type="number" min="1" step="0.01" bind:value={form.cap_landed_eur} />
			</label>
		</div>
		<button class="primary" onclick={submitStructured} disabled={busy || !form.product_query.trim() || !form.size_eu || !form.cap_landed_eur}>
			{busy ? 'Validating…' : 'Compile mandate'}
		</button>
	</div>
{/if}

{#if chat.length}
	<div class="chat" aria-live="polite">
		{#each chat as msg, i (i)}
			<div class="bubble {msg.role}">
				{#each msg.lines as line (line)}
					<p class="chat-line">{line}</p>
				{/each}
			</div>
		{/each}
	</div>
{/if}

{#if intakeId}
	<div class="reply-row">
		<input
			type="text"
			bind:value={reply}
			placeholder="Your answer…"
			aria-label="Answer the clarifying question"
			onkeydown={(e) => {
				if (e.key === 'Enter') sendReply();
			}}
		/>
		<button onclick={sendReply} disabled={busy || !reply.trim()}>Reply</button>
	</div>
{/if}

<style>
	.intake {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin-top: 24px;
	}

	textarea {
		width: 100%;
		resize: vertical;
		font-size: 20px;
	}

	.controls {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}

	.mode {
		border: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.mode label {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 14px;
	}

	.screenshot {
		display: grid;
		gap: 5px;
	}

	.chat-line {
		margin: 0;
	}

	.chat-line + .chat-line {
		margin-top: 6px;
	}

	.reply-row {
		display: flex;
		gap: 8px;
		margin-top: 12px;
	}

	.reply-row input {
		flex: 1;
	}

	.structured-form {
		display: grid;
		gap: 14px;
		margin-top: 18px;
	}

	.structured-form h2,
	.structured-form p {
		margin: 0;
	}

	.structured-form label {
		display: grid;
		gap: 6px;
	}

	.form-row {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}
</style>
