import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "huggingface",
	name: "Hugging Face",
	tagline:
		"Secure your MCP servers with Hugging Face OAuth. The gateway bridges Hugging Face's OAuth apps to MCP clients, including public apps without a client secret.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Create a Hugging Face OAuth app",
			body: "Go to your Hugging Face application settings (huggingface.co/settings/applications/new) and create a new OAuth application. Choose a name users will recognize.",
		},
		{
			title: "Configure the redirect URL",
			body: "Set the redirect URL to your gateway's public URL plus /auth/callback (e.g. https://mcp.example.com/auth/callback). Use http://localhost:8000/auth/callback for local development and HTTPS for production.",
		},
		{
			title: "Match the redirect URL exactly",
			body: "The redirect URL registered here must match exactly what the gateway uses. The default path is /auth/callback; if you set a custom path via the redirect_path field, register the same path in Hugging Face.",
			kind: "warning",
		},
		{
			title: "Save your credentials",
			body: "After creating the app you get a Client ID and, for a confidential app, a Client Secret. Public apps have no secret — leave client_secret empty and set a jwt_signing_key instead so the gateway can sign its own tokens.",
		},
		{
			title: "Keep the secret out of version control",
			body: "Never commit the client secret to version control. Use environment variables or a secrets manager in production.",
			kind: "tip",
		},
		{
			title: "Choose the scopes you need",
			body: "The default scopes are openid and profile. Add scopes your tools actually need — e.g. email, inference-api, read-repos, gated-repos, write-repos — and list the same scopes in the required_scopes field. For organization resources, pass Hugging Face's orgIds authorization parameter via extra_authorize_params, using the organization ID from the organizations.sub field in the userinfo response.",
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
		{
			key: "client_secret",
			text: "Your OAuth app's secret. Only confidential apps have one — public apps have no secret and must leave this empty and set a jwt_signing_key instead. Treat it like a password — never commit it to version control.",
		},
		{ key: "valid_scopes", shared: true },
		{ key: "timeout_seconds", shared: true },
		{ key: "extra_authorize_params", shared: true },
		{ key: "extra_token_params", shared: true },
		{ key: "enable_cimd", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
