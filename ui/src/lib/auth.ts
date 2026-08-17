import * as oauth from "oauth4webapi";

import {
	authStatusApiAdminAuthStatusGet,
	endSessionApiAdminSessionDelete,
	establishSessionApiAdminSessionPost,
	loginApiAdminLoginPost,
	meApiAdminMeGet,
} from "#/api/generated/fastAPI";

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

/**
 * Adopt a bearer token into the gateway's HttpOnly session cookie. The token
 * is never persisted in browser storage.
 */
export async function establishAdminSession(token: string): Promise<boolean> {
	try {
		const result = await establishSessionApiAdminSessionPost({ token });
		return result.status === 200;
	} catch {
		return false;
	}
}

/** Clear the gateway's HttpOnly session cookie. */
export async function endAdminSession(): Promise<boolean> {
	try {
		const result = await endSessionApiAdminSessionDelete();
		return result.status === 204;
	} catch {
		return false;
	}
}

export async function fetchAdminAuthInfo(): Promise<AdminAuthInfo | null> {
	try {
		const result = await authStatusApiAdminAuthStatusGet();
		if (result.status !== 200) return null;
		const payload = result.data as AdminAuthInfo;
		return payload;
	} catch {
		return null;
	}
}

export async function checkAdminAuth(): Promise<AdminAuthStatus> {
	try {
		const result = await meApiAdminMeGet();
		if (result.status === 200) return "authenticated";
		if (result.status === 503) return "unconfigured";
		return "unauthenticated";
	} catch {
		return "error";
	}
}

export async function loginWithPassword(
	username: string,
	password: string,
): Promise<boolean> {
	try {
		const result = await loginApiAdminLoginPost({ username, password });
		return result.status === 200;
	} catch {
		return false;
	}
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
	let parsed: unknown;
	try {
		parsed = JSON.parse(stored);
	} catch {
		throw new Error("Stored login flow is corrupted.");
	}
	if (
		typeof parsed !== "object" ||
		parsed === null ||
		typeof (parsed as { codeVerifier?: unknown }).codeVerifier !== "string" ||
		typeof (parsed as { state?: unknown }).state !== "string"
	) {
		throw new Error("Stored login flow is corrupted.");
	}
	const { codeVerifier, state } = parsed as {
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
	if (!(await establishAdminSession(tokens.access_token))) {
		throw new Error("The gateway rejected the access token.");
	}
}
