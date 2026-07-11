"""Judge-facing world answer-key renderer (§4.7)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..core.config import Constants
from ..core.models import World, canonical_json


def render_dossier(world: World, cfg: Constants) -> str:
    config_hash = hashlib.sha256(repr(cfg).encode()).hexdigest()[:16]
    lines = [
        f"# SolidHunt world dossier — seed {world.seed}",
        "",
        "> Eval-only answer key. This document must never enter an engine or LLM code path.",
        "",
        "## Configuration and market summary",
        "",
        f"- Seed: `{world.seed}`",
        f"- Configuration hash: `{config_hash}`",
        f"- Horizon: {world.horizon} ticks",
        f"- Products: {len(world.products)}",
        f"- Vendors: {len(world.vendors)}",
        f"- Middlemen: {len(world.middlemen)}",
        f"- Listings: {len(world.listings)}",
        f"- Planted traps: {len(world.traps)}",
        "",
        "## Market narrative",
        "",
    ]
    for pair in sorted({row.pair for row in world.fx}):
        rows = sorted((row for row in world.fx if row.pair == pair), key=lambda row: row.tick)
        drift = ((rows[-1].rate / rows[0].rate) - 1) * 100
        lines.append(f"- {pair}: {rows[0].rate} → {rows[-1].rate} ({drift:+.2f}%).")
    sale_rows = sum(1 for row in world.price_events if row.on_sale)
    lines.extend([
        f"- The generated market contains {sale_rows} listing-days marked `on_sale` by the stored predicate.",
        "- Vendor discount anchors are descriptive only; the engine's own observation history is authoritative.",
        "",
        "## Planted traps",
        "",
    ])
    for index, trap in enumerate(world.traps, start=1):
        lines.extend([
            f"### {index}. `{trap.trap_type}`",
            "",
            f"- Listing: `{trap.listing_id or 'n/a'}`",
            f"- Vendor: `{trap.vendor_id or 'n/a'}`",
            f"- Active ticks: `{trap.ticks if trap.ticks is not None else 'n/a'}`",
            f"- Why it is a trap: {trap.explanation}",
            f"- Correct behavior: {trap.correct_behavior}",
            "",
        ])
    lines.extend(["## Oracle answers", ""])
    for key, answer in sorted(world.oracle.items()):
        lines.append(f"### `{key}`")
        lines.append("")
        for policy, best in (("ALLOW", answer.allow), ("NEVER", answer.never)):
            if best is None:
                lines.append(f"- {policy}: no legitimate under-cap buy exists.")
            else:
                route = best.route_kind + (f" via {best.middleman_id}" if best.middleman_id else "")
                lines.append(
                    f"- {policy}: tick {best.tick}, `{best.listing_id}`, {route}, landed €{best.landed_eur}."
                )
        lines.append("")
    lines.extend([
        "## Canonical world fingerprint",
        "",
        f"`sha256:{hashlib.sha256(canonical_json(world).encode()).hexdigest()}`",
        "",
    ])
    return "\n".join(lines)


def write_dossier(world: World, cfg: Constants, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dossier(world, cfg), encoding="utf-8")
