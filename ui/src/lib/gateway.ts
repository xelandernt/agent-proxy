export const GATEWAY_URL =
	import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8008";

const GATEWAY_PATH_PREFIXES = ["/api/", "/.well-known/"];

/**
 * Orval generates calls against relative gateway paths. Patch fetch once at
 * startup so those requests hit the configured gateway origin. Browser-only;
 * server rendering must not reach out to the gateway.
 */
export function patchGatewayFetch(): void {
	if (typeof window === "undefined") return;
	const original = globalThis.fetch;
	if (original === undefined) return;
	globalThis.fetch = (input, init) => {
		if (
			typeof input === "string" &&
			GATEWAY_PATH_PREFIXES.some((prefix) => input.startsWith(prefix))
		) {
			return original(`${GATEWAY_URL}${input}`, init);
		}
		return original(input, init);
	};
}

/** Authorization header for the admin API, when a token is stored. */
export function adminHeaders(): RequestInit["headers"] | undefined {
	const token = localStorage.getItem("admin-token");
	return token ? { Authorization: `Bearer ${token}` } : undefined;
}
