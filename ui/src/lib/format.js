// Pure presentation helpers. Amounts are decimal STRINGS from the API and are
// rendered exactly as they arrive — never parseFloat'ed for display.

/** "76.40" -> "€76.40"; "-6.00" -> "−€6.00" (string manipulation only). */
export function eur(amount) {
	const s = String(amount);
	return s.startsWith('-') ? `−€${s.slice(1)}` : `€${s}`;
}

/** Probability string "0.12" -> "12%" (not money; formatting only). */
export function pct(p) {
	const n = Number(p);
	return Number.isFinite(n) ? `${Math.round(n * 100)}%` : String(p);
}

/** First 12 chars of a hash for display. */
export function shortHash(h) {
	return h ? `${h.slice(0, 12)}…` : '';
}

// Badge class/label derives ONLY from the action field — never from prices.
export const ACTION_BADGE = {
	BUY: { label: 'BUY', cls: 'badge-buy' },
	ALERT: { label: 'ALERT', cls: 'badge-alert' },
	ASK: { label: 'ASK', cls: 'badge-ask' },
	HOLD: { label: 'HOLD', cls: 'badge-hold' },
	ESCALATE_NONE_FOUND: { label: 'ESCALATE', cls: 'badge-escalate' }
};

export const ASK_KIND_LABEL = {
	GRAY_ROUTE: 'Geo route consent',
	OVER_CAP: 'Over-cap — one-time cap extension'
};

// Order-card style derives ONLY from the order state field.
export const ORDER_BADGE = {
	PLACED: { label: 'ORDER PLACED', cls: 'badge-info' },
	CONFIRMED: { label: 'ORDER CONFIRMED', cls: 'badge-buy' },
	CANCELLED_BY_MERCHANT: { label: 'CANCELLED BY MERCHANT', cls: 'badge-escalate' },
	REFUNDED: { label: 'REFUNDED', cls: 'badge-info' }
};

export const GEO_ARB_LABEL = {
	NEVER: 'Never use geo tricks',
	ASK: 'Ask before geo routes',
	ALLOW: 'Geo routes allowed'
};
