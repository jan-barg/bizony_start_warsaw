<script>
	// Screen ① — New Hunt. Textarea + mode toggle → POST /intake. While the
	// intake returns NEEDS_INFO, clarifying questions render chat-style and
	// each reply POSTs /intake/{id}/clarify until status is OK.
	import { goto } from '$app/navigation';
	import { postIntake, postClarify } from '$lib/api.js';
	import { intakeByHunt, stash } from '$lib/stores.js';

	let text = $state('');
	let mode = $state('MONITOR');
	let chat = $state([]); // {role: 'user'|'agent', lines: string[]}
	let intakeId = $state(null);
	let reply = $state('');
	let busy = $state(false);
	let error = $state('');

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
			onResult(await postIntake(finalText, mode));
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
</div>

{#if error}
	<div class="banner error" role="alert">{error}</div>
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
</style>
