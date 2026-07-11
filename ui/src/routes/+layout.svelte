<script>
	import '../app.css';

	let { children } = $props();
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
