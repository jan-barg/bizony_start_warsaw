import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// SPA mode: every route falls back to index.html; ssr is disabled in
		// src/routes/+layout.js. The UI is a pure consumer of the SolidHunt API.
		adapter: adapter({ fallback: 'index.html' })
	}
};

export default config;
