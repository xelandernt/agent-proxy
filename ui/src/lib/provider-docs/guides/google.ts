import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "google",
	name: "Google",
	tagline:
		"Secure your MCP servers with Google OAuth. The gateway bridges Google's OAuth 2.0 clients to MCP clients and validates Google-issued tokens.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Configure the OAuth consent screen",
			body: "Open the Google Cloud Console (console.cloud.google.com/apis/credentials), select your project, and go to APIs & Services → OAuth consent screen. Choose External for testing or Internal for G Suite organizations. For an External app in testing mode, add yourself as a test user.",
		},
		{
			title: "Create an OAuth 2.0 Client ID",
			body: "Go to APIs & Services → Credentials, click + CREATE CREDENTIALS → OAuth client ID, and set Application type to Web application. Give it a descriptive name, add your gateway's public URL under Authorized JavaScript origins, and add your gateway's public URL plus /auth/callback under Authorized redirect URIs.",
		},
		{
			title: "Match the redirect URI exactly",
			body: "The redirect URI registered here must match exactly what the gateway uses. The default path is /auth/callback; if you set a custom path via the redirect_path field, register the same path in Google. Local development may use http://localhost with any port; production must use HTTPS.",
			kind: "warning",
		},
		{
			title: "Save your credentials",
			body: "After creating the client you get a Client ID ending in .apps.googleusercontent.com and a Client Secret starting with GOCSPX-. Download the JSON credentials or copy both values securely.",
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
		{
			key: "client_secret",
			text: "Your OAuth client's secret from the Google Cloud Console, starting with GOCSPX-. Optional: Google always issues a secret, but you can leave this empty and set a jwt_signing_key instead if you prefer the gateway to sign its own tokens. Treat it like a password — never commit it to version control.",
		},
		{ key: "valid_scopes", shared: true },
		{ key: "timeout_seconds", shared: true },
		{ key: "extra_authorize_params", shared: true },
		{ key: "enable_cimd", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
