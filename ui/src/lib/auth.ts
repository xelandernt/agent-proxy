import * as oauth from "oauth4webapi";

import { GATEWAY_URL } from "#/lib/gateway";

export const TOKEN_KEY = "admin-token";
const PKCE_STATE_KEY = "admin-oauth-state";

export type AdminAuthStatus =
	| "checking"
	| "error"
	| "authenticated"
	| "unauthenticated"
	| "unconfigured";

export type AdminOAuthInfo = {
	issuer: string;
	client_id: string;
};

export type AdminAuthInfo = {
	provider: string | null;
	oauth: AdminOAuthInfo | null;
};

export function getAdminToken(): string | null {
	return localStorage.getItem(TOKEN_KEY);
}

export function setAdminToken(token: string): void {
	localStorage.setItem(TOKEN_KEY, token);
}

export function clearAdminToken(): void {
	localStorage.removeItem(TOKEN_KEY);
}

export async function fetchAdminAuthInfo(): Promise<AdminAuthInfo | null> {
	try {
		const response = await fetch(`${GATEWAY_URL}/api/admin/auth-status`);
		if (!response.ok) return null;
		return (await response.json()) as AdminAuthInfo;
	} catch {
		return null;
	}
}

export async function checkAdminAuth(token: string): Promise<AdminAuthStatus> {
	let response: Response;
	try {
		response = await fetch(`${GATEWAY_URL}/api/admin/me`, {
			headers: { Authorization: `Bearer ${token}` },
		});
	} catch {
		return "error";
	}
	if (response.status === 200) return "authenticated";
	if (response.status === 503) return "unconfigured";
	return "unauthenticated";
}

export async function loginWithPassword(
	username: string,
	password: string,
): Promise<boolean> {
	let response: Response;
	try {
		response = await fetch(`${GATEWAY_URL}/api/admin/login`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ username, password }),
		});
	} catch {
		return false;
	}
	if (!response.ok) return false;
	const payload = (await response.json()) as { token?: string };
	if (!payload.token) return false;
	setAdminToken(payload.token);
	return true;
}

function adminCallbackUrl(): string {
	return `${window.location.origin}/admin/callback`;
}

export async function fetchAuthorizationServer(
	issuer: string,
): Promise<oauth.AuthorizationServer | null> {
	try {
		const issuerUrl = new URL(issuer);
		const response = await oauth.discoveryRequest(issuerUrl, {
			algorithm: "oauth2",
			[oauth.allowInsecureRequests]: true,
		});
		return await oauth.processDiscoveryResponse(issuerUrl, response);
	} catch {
		return null;
	}
}

export async function startOAuthLogin(): Promise<"redirected" | "unsupported"> {
	const authInfo = await fetchAdminAuthInfo();
	const oauthInfo = authInfo?.oauth;
	if (!oauthInfo) return "unsupported";
	const server = await fetchAuthorizationServer(oauthInfo.issuer);
	if (!server?.authorization_endpoint || !server.token_endpoint) {
		return "unsupported";
	}

	const codeVerifier = oauth.generateRandomCodeVerifier();
	const codeChallenge = await oauth.calculatePKCECodeChallenge(codeVerifier);
	const state = oauth.generateRandomState();
	sessionStorage.setItem(
		PKCE_STATE_KEY,
		JSON.stringify({ codeVerifier, state }),
	);

	const scopes = server.scopes_supported ?? [];
	const scope = scopes.includes("openid") ? "openid" : (scopes[0] ?? "mcp");

	const authorizationUrl = new URL(server.authorization_endpoint);
	authorizationUrl.searchParams.set("client_id", oauthInfo.client_id);
	authorizationUrl.searchParams.set("redirect_uri", adminCallbackUrl());
	authorizationUrl.searchParams.set("response_type", "code");
	authorizationUrl.searchParams.set("scope", scope);
	authorizationUrl.searchParams.set("code_challenge", codeChallenge);
	authorizationUrl.searchParams.set("code_challenge_method", "S256");
	authorizationUrl.searchParams.set("state", state);

	window.location.assign(authorizationUrl.href);
	return "redirected";
}

export async function completeOAuthLogin(
	oauthInfo: AdminOAuthInfo,
	server: oauth.AuthorizationServer,
): Promise<void> {
	const stored = sessionStorage.getItem(PKCE_STATE_KEY);
	sessionStorage.removeItem(PKCE_STATE_KEY);
	if (!stored) throw new Error("No pending login flow found.");
	const { codeVerifier, state } = JSON.parse(stored) as {
		codeVerifier: string;
		state: string;
	};

	const client: oauth.Client = {
		client_id: oauthInfo.client_id,
		token_endpoint_auth_method: "none",
	};
	const params = oauth.validateAuthResponse(
		server,
		client,
		new URL(window.location.href),
		state,
	);
	const response = await oauth.authorizationCodeGrantRequest(
		server,
		client,
		oauth.None(),
		params,
		adminCallbackUrl(),
		codeVerifier,
		{ [oauth.allowInsecureRequests]: true },
	);
	const tokens = await oauth.processAuthorizationCodeResponse(
		server,
		client,
		response,
	);
	setAdminToken(tokens.access_token);
}
