<script>
	// The brand aurora as a full-viewport backdrop. One component so every
	// screen that uses it renders the IDENTICAL aurora — that is what makes
	// view transitions between screens read as one continuous surface.
	import SoftAurora from '$lib/components/SoftAurora.svelte';
</script>

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

<style>
	.aurora {
		position: fixed;
		inset: 0;
		z-index: -1;
		pointer-events: none;
		view-transition-name: sh-aurora; /* pair across pages: no crossfade flash */
	}
</style>
