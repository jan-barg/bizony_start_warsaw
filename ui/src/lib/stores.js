// Cross-screen hand-off state. SPA-only (ssr=false), so module state is safe.
// Screens fall back to refetching from the API when a store is empty (refresh).
import { writable } from 'svelte/store';

/** hunt_id -> intake OK payload ({brief, mandate, mandate_diff, ...}) */
export const intakeByHunt = writable({});

/** hunt_id -> POST /hunts/{id}/run_immediate response */
export const immediateByHunt = writable({});

export function stash(store, huntId, payload) {
	store.update((m) => ({ ...m, [huntId]: payload }));
}
