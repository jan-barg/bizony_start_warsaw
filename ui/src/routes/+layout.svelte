<script>
	import '../app.css';
	import { onNavigate } from '$app/navigation';

	let { children } = $props();

	// Morph between screens with the View Transitions API (SvelteKit's
	// documented pattern). Elements sharing a view-transition-name across
	// pages (composer → mandate card, page titles, the aurora) animate from
	// one into the other; everything else cross-fades. No-ops on browsers
	// without support and under prefers-reduced-motion.
	onNavigate((navigation) => {
		if (!document.startViewTransition) return;
		if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});
</script>

<header class="site-header">
	<a href="/" aria-label="SolidHunt home" class="logo-link">
		<img src="/brand/solidhunt-logo.svg" alt="SolidHunt" class="logo" />
	</a>
	<span class="tagline muted small">The deal hunter never sleeps.</span>
</header>

<main class="page">
	{@render children()}
</main>

<style>
	.site-header {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 16px 24px;
		border-bottom: 1px solid var(--border);
	}

	.logo {
		display: block;
		width: 160px; /* full horizontal logo, above the 140px minimum */
		height: auto;
	}

	.logo-link {
		display: inline-flex;
		border-radius: var(--radius-control);
	}

	@media (max-width: 480px) {
		.tagline {
			display: none;
		}
	}
</style>
