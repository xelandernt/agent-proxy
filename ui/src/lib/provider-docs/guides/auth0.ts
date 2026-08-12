import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "auth0",
	name: "Auth0",
	tagline:
		"Secure your MCP servers with Auth0: the gateway proxies Auth0's OIDC flow with fixed application credentials and validates Auth0-issued tokens.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Open the Auth0 Applications list",
			body: "Go to Applications → Applications in your Auth0 dashboard and click + Create Application.",
		},
		{
			title: "Create your application",
			body: 'Choose a name users will recognize (e.g. "My MCP Server"), select Single Page Web Applications as the application type, and click Create.',
		},
		{
			title: "Set the allowed callback URL",
			body: "Open the Settings tab, scroll to Application URIs, and add your gateway's public URL plus /auth/callback (e.g. https://mcp.example.com/auth/callback) to Allowed Callback URLs. Click Save. The callback URL must match exactly — the default path is /auth/callback, but you can customize it with the form's Redirect Path field as long as you use the same path in Auth0.",
			kind: "warning",
		},
		{
			title: "Save your credentials",
			body: "In the Basic Information section you'll find the Client ID (a public identifier) and the Client Secret (a private value Auth0 shows once). Store both securely and never commit them to version control.",
			kind: "tip",
		},
		{
			title: "Select your API audience",
			body: "Go to Applications → APIs and find the API your application should access. The API Audience is a URL that uniquely identifies that API; the gateway validates the token's aud claim against it, so use the same value in the form's Audience field.",
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
		{
			key: "config_url",
			text: "Your Auth0 tenant's OIDC discovery URL: https://<tenant>.auth0.com/.well-known/openid-configuration, where <tenant> is your tenant's domain from the Auth0 dashboard. The gateway fetches the provider's discovery document from this URL.",
		},
		{ key: "client_id", shared: true },
		{ key: "client_secret", shared: true },
		{
			key: "audience",
			text: "The Auth0 API Audience — a URL that uniquely identifies the API your application targets, e.g. https://<tenant>.auth0.com/api/v2/. Find it under Applications → APIs; tokens Auth0 issues must carry this aud value.",
		},
		{ key: "timeout_seconds", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
