import { type AuthAudience, expireAuthentication } from "./auth-session.ts";

export function authAudienceForUrl(
	url: string,
	pathname = window.location.pathname,
): AuthAudience {
	if (url.startsWith("/api/admin")) return "admin";
	if (url.startsWith("/api/user")) return "user";
	return pathname.startsWith("/admin") ? "admin" : "user";
}

export function isAuthenticationProbe(url: string): boolean {
	const pathname = new URL(url, "http://localhost").pathname;
	return pathname === "/api/admin/me" || pathname === "/api/user/me";
}

export async function apiFetch<T>(
	url: string,
	options?: RequestInit,
): Promise<T> {
	const response = await fetch(url, options);
	if (response.status === 401 && !isAuthenticationProbe(url)) {
		expireAuthentication(authAudienceForUrl(url));
	}
	const body = [204, 205, 304].includes(response.status)
		? null
		: await response.text();
	return {
		data: body ? JSON.parse(body) : {},
		status: response.status,
		headers: response.headers,
	} as T;
}
