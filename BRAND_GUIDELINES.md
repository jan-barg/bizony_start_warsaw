# SolidHunt Brand Guidelines

## Brand foundation

**Name:** SolidHunt

**Primary one-liner:** The deal hunter never sleeps.

**Product promise:** Set the product and the price ceiling. SolidHunt watches, verifies, and acts without breaking the user's mandate.

The brand should feel patient, precise, transparent, and safe. The hunting metaphor communicates persistence and timing, never aggression.

## Logo

Use the supplied artwork rather than recreating or typesetting the wordmark.

| Asset | Use |
|---|---|
| `assets/brand/solidhunt-logo.svg` | Preferred for the web, product UI, and scalable layouts |
| `assets/brand/solidhunt-logo-transparent.png` | Raster use on light or photographic backgrounds |
| `assets/brand/solidhunt-logo.png` | Slides, documents, and tools that require a white background |

The four focus corners represent a hunt locking onto the right deal. The centered diamond represents the decision point: a deal proceeds only when it satisfies the mandate.

### Clear space and sizing

- Keep clear space around the logo equal to at least half the height of the green symbol.
- Use the full horizontal logo at a minimum width of 140 px on screen.
- Do not use the symbol below 32 px. At smaller sizes, use the wordmark or a text label instead.
- Preserve the original aspect ratio.

### Do not

- Recolor, rotate, stretch, outline, or add effects to the logo.
- Place the logo over a busy image without a clean backing surface.
- Separate the symbol and wordmark unless an icon-only asset is created and approved.
- Typeset `solidhunt` as a substitute for the supplied wordmark.

## Color system

### Core palette

| Token | Value | Purpose |
|---|---|---|
| Solid Green | `#43F27E` | Brand fields, key highlights, active hunt moments |
| Ink | `#080808` | Primary text, logo geometry, high-emphasis controls |
| Paper | `#FFFFFF` | Main background |
| Soft Surface | `#F4F6F3` | Secondary surfaces and grouped content |
| Border | `#D8DDD9` | Dividers and control borders |
| Muted Ink | `#59615B` | Supporting copy and metadata |

Use black text and icons on Solid Green. Do not use white text on the brand green.

### Functional colors

Functional colors communicate decisions and must always be paired with a label or icon.

| Token | Value | Meaning |
|---|---|---|
| Buy | `#137A3D` | Verified purchase or completed strike |
| Hold | `#A76100` | Waiting, monitoring, or user attention |
| Reject | `#C52A22` | Unsafe, invalid, or blocked offer |
| Information | `#2859C5` | Neutral explanation or route detail |

Solid Green is the brand color; it should not be the only way the interface communicates a successful purchase.

## Typography

Use **Inter** for the frontend. If it is unavailable, use `Arial`, `Helvetica`, then `sans-serif`.

- Display and page titles: 700 weight, tight line height.
- Section headings: 600 weight.
- Body copy: 400 weight.
- Prices, caps, and receipt totals: 600-700 weight with tabular numbers.
- Avoid all-caps paragraphs. Reserve uppercase for short state labels such as `BUY`, `HOLD`, and `REJECT`.

Suggested web scale:

| Role | Size / line-height |
|---|---|
| Display | `56px / 1.0` |
| H1 | `40px / 1.1` |
| H2 | `28px / 1.2` |
| H3 | `20px / 1.3` |
| Body | `16px / 1.5` |
| Small | `14px / 1.4` |

## Layout and interface style

- Use a light-first interface with generous white space and strong black typography.
- Build on a 4 px spacing unit. Prefer `8, 12, 16, 24, 32, 48, 64` px increments.
- Use 8 px corner radii for cards and controls. Avoid excessive pills and heavily rounded dashboards.
- Use one dominant action per screen.
- Keep the user's product, landed-cost cap, and current hunt state visible.
- Present cost arithmetic as a clear receipt, not as fine print.
- Price charts should show the user's cap as a persistent labeled line.
- Use motion to communicate scanning or a price strike, not as decoration. Respect reduced-motion settings.

## Frontend tokens

Use these variables as the initial implementation contract:

```css
:root {
  --brand-solid: #43f27e;
  --ink: #080808;
  --ink-muted: #59615b;
  --paper: #ffffff;
  --surface-soft: #f4f6f3;
  --border: #d8ddd9;

  --state-buy: #137a3d;
  --state-hold: #a76100;
  --state-reject: #c52a22;
  --state-info: #2859c5;

  --font-sans: Inter, Arial, Helvetica, sans-serif;
  --radius-control: 8px;
  --radius-card: 8px;
  --focus-ring: 0 0 0 3px rgb(67 242 126 / 45%);
}
```

## Voice and writing

SolidHunt speaks with confidence grounded in evidence. Copy should be short, direct, and specific about what happened.

Prefer:

- `Hunting 24 verified offers`
- `Held: landed cost is €4.20 above your cap`
- `Deal found at €76.40 delivered`
- `Ask before buying through this route`

Avoid:

- Vague claims such as `AI-powered shopping magic`
- Aggressive hunting language aimed at people or sellers
- Claims that a purchase is safe without showing the reason
- Hiding shipping, taxes, risk, or mandate conditions

Use the hunting metaphor sparingly. The interface should explain decisions in plain shopping language.

## Accessibility

- Maintain WCAG AA contrast for all text and interactive elements.
- Never rely on green, amber, or red alone; add text and icons.
- Provide visible keyboard focus using the green focus ring.
- Give the logo the accessible name `SolidHunt`; treat decorative repetitions as hidden from assistive technology.
- Respect `prefers-reduced-motion` for timeline playback and scan animations.
- Use tabular numerals and explicit currency labels for prices.

## Brand consistency checklist

Before shipping a frontend screen, confirm:

1. The product is named `SolidHunt`, with the capital `S` and `H` in prose.
2. The official SVG is used for the logo.
3. Solid Green is `#43F27E`.
4. The price cap and landed cost are easy to find.
5. Every automated decision includes a plain-language reason.
6. Status is understandable without color.
7. Keyboard focus and reduced motion are supported.
