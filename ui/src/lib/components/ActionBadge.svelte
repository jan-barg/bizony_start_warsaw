<script>
	import { ACTION_BADGE } from '$lib/format.js';

	let { action } = $props();
	const badge = $derived(ACTION_BADGE[action] ?? { label: action, cls: 'badge-hold' });
</script>

<span class="badge {badge.cls}">{badge.label}</span>
