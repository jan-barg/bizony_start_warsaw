<script>
	// Hand-rolled SVG price chart (no chart lib). One y-axis (landed EUR),
	// x = tick. Series: best landed per receipt tick (2px line), running
	// observed-min (dashed), horizontal cap line (labeled), and event markers
	// whose shape+color derive ONLY from the receipt action field:
	// BUY solid dot · ALERT ring · ASK diamond · HOLD no marker.
	import { eur } from '$lib/format.js';

	let { points = [], cap = null, currentTick = 0 } = $props();

	const W = 760;
	const H = 280;
	const M = { top: 18, right: 16, bottom: 30, left: 60 };
	const IW = W - M.left - M.right;
	const IH = H - M.top - M.bottom;

	let hover = $state(null); // nearest point under the cursor

	const capN = $derived(cap != null ? parseFloat(cap) : null);

	const layout = $derived.by(() => {
		const xMax = Math.max(currentTick, points.length ? points[points.length - 1].tick : 0, 10);
		// Stable frame: with a cap the y-axis is ALWAYS 0 → 2×cap, so the line
		// never rescales under the viewer's eyes and the cap sits mid-chart.
		let yMin = 0;
		let yMax;
		if (capN != null) {
			yMax = capN * 2;
		} else {
			const ys = points.length ? points.map((p) => p.y) : [100];
			yMax = Math.max(...ys) * 1.15 || 100;
		}
		const x = (t) => M.left + (t / xMax) * IW;
		const y = (v) => M.top + (1 - (Math.min(v, yMax) - yMin) / (yMax - yMin)) * IH;

		// running observed-min series (dashed)
		let min = Infinity;
		const mins = points.map((p) => {
			min = Math.min(min, p.y);
			return { tick: p.tick, y: min };
		});

		const path = (pts) =>
			pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.tick).toFixed(1)},${y(p.y).toFixed(1)}`).join(' ');

		// recessive gridlines: 4 y steps, x every 10 ticks
		const ySteps = [0, 1, 2, 3, 4].map((i) => yMin + ((yMax - yMin) * i) / 4);
		const xStep = xMax > 60 ? 20 : 10;
		const xTicks = [];
		for (let t = 0; t <= xMax; t += xStep) xTicks.push(t);

		return { xMax, yMin, yMax, x, y, mins, path, ySteps, xTicks };
	});

	function onMove(evt) {
		if (!points.length) return;
		const rect = evt.currentTarget.getBoundingClientRect();
		const px = ((evt.clientX - rect.left) / rect.width) * W;
		let best = null;
		let bestD = Infinity;
		for (const p of points) {
			const d = Math.abs(layout.x(p.tick) - px);
			if (d < bestD) {
				bestD = d;
				best = p;
			}
		}
		hover = best;
	}
</script>

<figure class="chart card">
	<figcaption>
		<h3>Best all-in price, day by day</h3>
	</figcaption>

	<svg
		viewBox="0 0 {W} {H}"
		role="img"
		aria-label="Best landed cost in euros per tick, with the mandate cap line"
		onmousemove={onMove}
		onmouseleave={() => (hover = null)}
	>
		<!-- recessive grid + y axis labels -->
		{#each layout.ySteps as v (v)}
			<line
				x1={M.left}
				x2={W - M.right}
				y1={layout.y(v)}
				y2={layout.y(v)}
				class="grid"
			/>
			<text x={M.left - 8} y={layout.y(v) + 4} class="axis" text-anchor="end">
				€{Math.round(v)}
			</text>
		{/each}
		{#each layout.xTicks as t (t)}
			<text x={layout.x(t)} y={H - 8} class="axis" text-anchor="middle">{t}</text>
		{/each}

		<!-- cap line: persistent, labeled (brand requirement) -->
		{#if capN != null}
			<line
				x1={M.left}
				x2={W - M.right}
				y1={layout.y(capN)}
				y2={layout.y(capN)}
				class="cap-line"
			/>
			<text x={W - M.right} y={layout.y(capN) - 6} class="cap-label" text-anchor="end">
				your ceiling {eur(cap)}
			</text>
		{/if}

		<!-- running observed-min, dashed -->
		{#if layout.mins.length > 1}
			<path d={layout.path(layout.mins)} class="min-line" />
		{/if}

		<!-- best-landed series -->
		{#if points.length > 1}
			<path d={layout.path(points)} class="series" />
		{/if}

		<!-- event markers (2px surface ring separates them from the line) -->
		{#each points as p (p.tick)}
			{#if p.action === 'BUY'}
				<circle cx={layout.x(p.tick)} cy={layout.y(p.y)} r="5.5" class="ring-bg" />
				<circle cx={layout.x(p.tick)} cy={layout.y(p.y)} r="4.5" class="m-buy" />
			{:else if p.action === 'ALERT'}
				<circle cx={layout.x(p.tick)} cy={layout.y(p.y)} r="5" class="m-alert" />
			{:else if p.action === 'ASK'}
				<rect
					x={layout.x(p.tick) - 4.5}
					y={layout.y(p.y) - 4.5}
					width="9"
					height="9"
					class="m-ask"
					transform="rotate(45 {layout.x(p.tick)} {layout.y(p.y)})"
				/>
			{/if}
		{/each}

		<!-- crosshair + tooltip -->
		{#if hover}
			<line
				x1={layout.x(hover.tick)}
				x2={layout.x(hover.tick)}
				y1={M.top}
				y2={H - M.bottom}
				class="crosshair"
			/>
			<circle cx={layout.x(hover.tick)} cy={layout.y(hover.y)} r="6.5" class="hover-halo" />
			{@const tx = Math.min(layout.x(hover.tick) + 10, W - 165)}
			{@const ty = Math.max(layout.y(hover.y) - 44, M.top)}
			<g class="tooltip" transform="translate({tx},{ty})">
				<rect width="155" height="38" rx="6" />
				<text x="10" y="16">day {hover.tick} · {hover.action}</text>
				<text x="10" y="31" class="tt-val">{eur(hover.landedStr)} all-in</text>
			</g>
		{/if}
	</svg>

	<!-- legend: identity is never color-alone -->
	<div class="legend small">
		<span><svg width="18" height="10"><line x1="0" y1="5" x2="18" y2="5" class="series" /></svg> best all-in price</span>
		<span><svg width="18" height="10"><line x1="0" y1="5" x2="18" y2="5" class="min-line" /></svg> lowest seen</span>
		<span><svg width="18" height="10"><line x1="0" y1="5" x2="18" y2="5" class="cap-line" /></svg> your ceiling</span>
		<span><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" class="m-buy" /></svg> BUY</span>
		<span><svg width="12" height="12"><circle cx="6" cy="6" r="4" class="m-alert" /></svg> ALERT</span>
		<span><svg width="14" height="14"><rect x="3" y="3" width="8" height="8" class="m-ask" transform="rotate(45 7 7)" /></svg> ASK</span>
	</div>
</figure>

<style>
	.chart {
		padding: 16px;
	}

	figcaption h3 {
		margin: 0 0 8px;
	}

	svg {
		width: 100%;
		height: auto;
		display: block;
	}

	.grid {
		stroke: var(--border);
		stroke-width: 1;
	}

	.axis {
		font-size: 11px;
		fill: var(--ink-muted);
		font-variant-numeric: tabular-nums;
	}

	.series {
		fill: none;
		stroke: var(--ink);
		stroke-width: 2;
		stroke-linejoin: round;
	}

	.min-line {
		fill: none;
		stroke: var(--state-info);
		stroke-width: 1.5;
		stroke-dasharray: 5 4;
	}

	.cap-line {
		stroke: var(--state-reject);
		stroke-width: 1.5;
		stroke-dasharray: 2 3;
	}

	.cap-label {
		font-size: 12px;
		font-weight: 600;
		fill: var(--state-reject);
	}

	.ring-bg {
		fill: var(--paper); /* 2px surface ring under the BUY dot */
	}

	.m-buy {
		fill: var(--state-buy);
	}

	.m-alert {
		fill: var(--paper);
		stroke: var(--state-hold);
		stroke-width: 2;
	}

	.m-ask {
		fill: var(--state-ask);
		stroke: var(--paper);
		stroke-width: 1;
	}

	.crosshair {
		stroke: var(--ink-muted);
		stroke-width: 1;
		stroke-dasharray: 3 3;
	}

	.hover-halo {
		fill: none;
		stroke: var(--ink);
		stroke-width: 1;
	}

	.tooltip rect {
		fill: var(--ink);
		opacity: 0.92;
	}

	.tooltip text {
		fill: var(--paper);
		font-size: 11px;
	}

	.tooltip .tt-val {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 16px;
		margin-top: 8px;
		color: var(--ink-muted);
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
</style>
