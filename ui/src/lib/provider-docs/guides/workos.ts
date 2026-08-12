import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "workos",
	name: "WorkOS",
	tagline:
		"Secure your MCP servers with WorkOS Connect. The gateway bridges WorkOS's OAuth to MCP clients using a WorkOS OAuth application and its AuthKit domain.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Create an OAuth application",
			body: "Sign in to the WorkOS dashboard and go to Applications → Create Application, select OAuth Application, and name your application.",
		},
		{
			title: "Get your credentials",
			body: "In the application's settings, copy the Client ID (it starts with client_), click Generate Client Secret and save it securely, and copy the AuthKit Domain, e.g. https://<tenant>.authkit.app.",
		},
		{
			title: "Register the redirect URI",
			body: "Under Redirect URIs, add your gateway's public URL plus /auth/callback, e.g. https://mcp.example.com/auth/callback. The callback must match exactly — the gateway uses the same default path unless you change its redirect_path. Local development may use http://localhost; production must use HTTPS.",
			kind: "warning",
		},
		{
			title: "Choose your scopes",
			body: "Request the scopes your server needs — openid, profile, and email cover the standard identity claims and are the common set for WorkOS. Scopes must be enabled for the application in your AuthKit configuration.",
			kind: "tip",
		},
		{
			title: "Save your credentials",
			body: "You now have everything the gateway needs: the client ID, client secret, and AuthKit domain. Store the client secret securely — never commit it to version control.",
		},
	],
	fields: [
		{ key: "resource_base_url", shared: true },
		{ key: "issuer_url", shared: true },
		{ key: "allowed_client_redirect_uris", shared: true },
		{ key: "jwt_signing_key", shared: true },
		{ key: "require_authorization_consent", shared: true },
		{ key: "consent_csp_policy", shared: true },
		{ key: "forward_resource", shared: true },
		{ key: "fallback_refresh_token_expiry_seconds", shared: true },
		{ key: "fastmcp_access_token_expiry_seconds", shared: true },
		{ key: "token_expiry_threshold_seconds", shared: true },
		{ key: "required_scopes", shared: true },
		{ key: "client_id", shared: true },
		{ key: "client_secret", shared: true },
		{
			key: "authkit_domain",
			text: "Your WorkOS AuthKit domain, shown in your OAuth application's settings, e.g. https://<tenant>.authkit.app. The gateway uses it to discover the authorization and token endpoints.",
		},
		{ key: "valid_scopes", shared: true },
		{ key: "timeout_seconds", shared: true },
		{ key: "extra_authorize_params", shared: true },
		{ key: "enable_cimd", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
