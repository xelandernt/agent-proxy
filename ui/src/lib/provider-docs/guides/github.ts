import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "github",
	name: "GitHub",
	tagline:
		"Secure your MCP servers with GitHub OAuth. The gateway bridges GitHub's traditional OAuth Apps to MCP clients, since GitHub does not support Dynamic Client Registration.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Create a GitHub OAuth App",
			body: "Go to Settings → Developer settings → OAuth Apps (github.com/settings/developers) and click New OAuth App.",
		},
		{
			title: "Configure the OAuth App",
			body: "Fill in an Application name users will recognize, a Homepage URL, and the Authorization callback URL: your gateway's public URL plus /auth/callback (e.g. https://mcp.example.com/auth/callback).",
		},
		{
			title: "Match the callback URL exactly",
			body: "The callback URL registered here must match exactly what the gateway uses. The default path is /auth/callback; if you set a custom path via the redirect_path field, register the same path in GitHub. Local development may use http://localhost; production must use HTTPS.",
			kind: "warning",
		},
		{
			title: "Save your credentials",
			body: "After creating the app you get a Client ID (a public identifier like Ov23liAbcDefGhiJkLmN). Click Generate a new client secret and save the value securely — GitHub shows it only once.",
		},
		{
			title: "Keep the secret out of version control",
			body: "Never commit the client secret to version control. Use environment variables or a secrets manager in production.",
			kind: "tip",
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
		{ key: "timeout_seconds", shared: true },
		{ key: "cache_ttl_seconds", shared: true },
		{ key: "max_cache_size", shared: true },
		{ key: "enable_cimd", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
