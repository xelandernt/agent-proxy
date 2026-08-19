const AUTH_EXPIRED_EVENT = "gateway-auth-expired";

export type AuthAudience = "admin" | "user";

const expiring = new Set<AuthAudience>();

export function onAuthenticationExpired(
	audience: AuthAudience,
	listener: () => void,
): () => void {
	const handler = (event: Event) => {
		if ((event as CustomEvent<AuthAudience>).detail === audience) listener();
	};
	window.addEventListener(AUTH_EXPIRED_EVENT, handler);
	return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
}

export function expireAuthentication(audience: AuthAudience): void {
	if (expiring.has(audience)) return;
	expiring.add(audience);
	const loginPath = audience === "admin" ? "/admin" : "/account";
	sessionStorage.setItem(
		`${audience}-login-error`,
		"Your session expired. Sign in again.",
	);
	window.dispatchEvent(
		new CustomEvent<AuthAudience>(AUTH_EXPIRED_EVENT, { detail: audience }),
	);
	void fetch(`/api/${audience}/session`, { method: "DELETE" }).finally(() => {
		expiring.delete(audience);
		if (
			window.location.pathname !== loginPath &&
			window.location.pathname !== `${loginPath}/`
		) {
			window.location.assign(loginPath);
		}
	});
}
