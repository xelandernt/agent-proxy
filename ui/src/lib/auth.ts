import * as oauth from "oauth4webapi";

import {
	authStatusApiAdminAuthStatusGet,
	authStatusApiUserAuthStatusGet,
	endSessionApiAdminSessionDelete,
	endSessionApiUserSessionDelete,
	establishSessionApiAdminSessionPost,
	establishSessionApiUserSessionPost,
	loginApiAdminLoginPost,
	meApiAdminMeGet,
	meApiUserMeGet,
} from "#/api/generated/fastAPI";

const PKCE_STATE_KEY = "admin-oauth-state";
const USER_PKCE_STATE_KEY = "user-oauth-state";

export type AdminAuthStatus =
	| "checking"
	| "error"
	| "authenticated"
	| "unauthenticated";

export type AdminOAuthInfo = {
	issuer: string;
	client_id: string;
	scopes?: string[];
};

export type AdminAuthInfo = {
	provider: string | null;
	oauth: AdminOAuthInfo | null;
};

export type UserAuthInfo = {
	provider: string;
	oauth: (AdminOAuthInfo & { scopes: string[] }) | null;
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

function userCallbackUrl(): string {
	return `${window.location.origin}/account/callback`;
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
	return beginOAuthLogin(
		oauthInfo,
		PKCE_STATE_KEY,
		adminCallbackUrl(),
		(server) => {
			const scopes = server.scopes_supported ?? [];
			return scopes.includes("openid") ? "openid" : (scopes[0] ?? "mcp");
		},
	);
}

export async function fetchUserAuthInfo(): Promise<UserAuthInfo | null> {
	try {
		const result = await authStatusApiUserAuthStatusGet();
		return result.status === 200 ? (result.data as UserAuthInfo) : null;
	} catch {
		return null;
	}
}

export async function checkUserAuth(): Promise<AdminAuthStatus> {
	try {
		const result = await meApiUserMeGet();
		if (result.status === 200) return "authenticated";
		return "unauthenticated";
	} catch {
		return "error";
	}
}

export async function establishUserSession(token: string): Promise<boolean> {
	try {
		const result = await establishSessionApiUserSessionPost({ token });
		return result.status === 200;
	} catch {
		return false;
	}
}

export async function endUserSession(): Promise<boolean> {
	try {
		const result = await endSessionApiUserSessionDelete();
		return result.status === 204;
	} catch {
		return false;
	}
}

export async function startUserOAuthLogin(): Promise<
	"redirected" | "unsupported"
> {
	const authInfo = await fetchUserAuthInfo();
	const oauthInfo = authInfo?.oauth;
	if (!oauthInfo) return "unsupported";
	return beginOAuthLogin(
		oauthInfo,
		USER_PKCE_STATE_KEY,
		userCallbackUrl(),
		() => oauthInfo.scopes.join(" "),
	);
}

export async function completeOAuthLogin(
	oauthInfo: AdminOAuthInfo,
	server: oauth.AuthorizationServer,
): Promise<void> {
	await completeLogin(
		oauthInfo,
		server,
		PKCE_STATE_KEY,
		adminCallbackUrl(),
		establishAdminSession,
	);
}

export async function completeUserOAuthLogin(
	oauthInfo: AdminOAuthInfo,
	server: oauth.AuthorizationServer,
): Promise<void> {
	await completeLogin(
		oauthInfo,
		server,
		USER_PKCE_STATE_KEY,
		userCallbackUrl(),
		establishUserSession,
	);
}

async function beginOAuthLogin(
	oauthInfo: AdminOAuthInfo,
	stateKey: string,
	callbackUrl: string,
	selectScope: (server: oauth.AuthorizationServer) => string,
): Promise<"redirected" | "unsupported"> {
	const server = await fetchAuthorizationServer(oauthInfo.issuer);
	if (!server?.authorization_endpoint || !server.token_endpoint) {
		return "unsupported";
	}
	const codeVerifier = oauth.generateRandomCodeVerifier();
	const codeChallenge = await oauth.calculatePKCECodeChallenge(codeVerifier);
	const state = oauth.generateRandomState();
	sessionStorage.setItem(stateKey, JSON.stringify({ codeVerifier, state }));
	const authorizationUrl = new URL(server.authorization_endpoint);
	authorizationUrl.searchParams.set("client_id", oauthInfo.client_id);
	authorizationUrl.searchParams.set("redirect_uri", callbackUrl);
	authorizationUrl.searchParams.set("response_type", "code");
	authorizationUrl.searchParams.set("scope", selectScope(server));
	authorizationUrl.searchParams.set("code_challenge", codeChallenge);
	authorizationUrl.searchParams.set("code_challenge_method", "S256");
	authorizationUrl.searchParams.set("state", state);
	window.location.assign(authorizationUrl.href);
	return "redirected";
}

async function completeLogin(
	oauthInfo: AdminOAuthInfo,
	server: oauth.AuthorizationServer,
	stateKey: string,
	callbackUrl: string,
	establishSession: (token: string) => Promise<boolean>,
): Promise<void> {
	const stored = sessionStorage.getItem(stateKey);
	sessionStorage.removeItem(stateKey);
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
		callbackUrl,
		codeVerifier,
		{ [oauth.allowInsecureRequests]: true },
	);
	const tokens = await oauth.processAuthorizationCodeResponse(
		server,
		client,
		response,
	);
	if (!(await establishSession(tokens.access_token))) {
		throw new Error("The gateway rejected the access token.");
	}
}
