// Thin wrapper around the SolidHunt API (spec §8). Every network call the UI
// makes goes through this module. The UI is a pure consumer of receipts and
// events — no decision logic lives client-side.
export const API = import.meta.env.VITE_API ?? 'http://localhost:8000';

async function req(method, path, body) {
	let res;
	try {
		res = await fetch(`${API}${path}`, {
			method,
			headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
			body: body !== undefined ? JSON.stringify(body) : undefined
		});
	} catch {
		throw new Error(`Cannot reach the SolidHunt API at ${API} — is uvicorn running?`);
	}
	if (!res.ok) {
		let detail = '';
		try {
			detail = (await res.json()).detail ?? '';
		} catch {
			/* non-JSON error body */
		}
		const err = new Error(detail || `${method} ${path} failed (${res.status})`);
		err.status = res.status;
		throw err;
	}
	return res.json();
}

// ---- intake (§7.1 loop) ----
export const postIntake = (text, mode) => req('POST', '/intake', { input: { text }, mode });
export const postClarify = (intakeId, text) => req('POST', `/intake/${intakeId}/clarify`, { text });

// ---- hunts ----
export const getHunt = (huntId) => req('GET', `/hunts/${huntId}`);
export const patchMandate = (huntId, fields) =>
	req('PATCH', `/hunts/${huntId}/mandate`, { mandate: fields });
export const confirmHunt = (huntId) => req('POST', `/hunts/${huntId}/confirm`);
export const runImmediate = (huntId) => req('POST', `/hunts/${huntId}/run_immediate`);
export const startHunt = (huntId) => req('POST', `/hunts/${huntId}/start`);
export const revokeHunt = (huntId) => req('POST', `/hunts/${huntId}/revoke`);
export const getReceipts = (huntId, fromTick = 0) =>
	req('GET', `/hunts/${huntId}/receipts?from_tick=${fromTick}`);

// ---- asks (single-use consent, §6.3) ----
export const approveAsk = (askId) => req('POST', `/asks/${askId}/approve`);
export const declineAsk = (askId) => req('POST', `/asks/${askId}/decline`);

// ---- SSE ----
export const eventsUrl = (huntId) => `${API}/hunts/${huntId}/events`;
