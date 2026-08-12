import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "discord",
	name: "Discord",
	tagline:
		"Secure your MCP servers with Discord OAuth: the gateway bridges Discord's traditional OAuth to MCP clients using fixed application credentials.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Create a Discord application",
			body: 'Go to the Discord Developer Portal (https://discord.com/developers/applications), click New Application, and give it a name users will recognize (e.g. "My MCP Server").',
		},
		{
			title: "Configure the OAuth2 redirect",
			body: "In the left sidebar, click OAuth2. In the Redirects section, click Add Redirect and enter your callback URL: your gateway's public URL plus /auth/callback (e.g. https://mcp.example.com/auth/callback). The redirect URL must match exactly — the default path is /auth/callback, but you can customize it with the form's Redirect Path field as long as you use the same path in Discord. Discord allows http://localhost URLs for development; production must use HTTPS.",
			kind: "warning",
		},
		{
			title: "Save your credentials",
			body: "On the same OAuth2 page you'll find the Client ID (a numeric string) and the Client Secret (click Reset Secret to generate one). Store both securely and never commit them to version control.",
			kind: "tip",
		},
		{
			title: "Pick the scopes your server needs",
			body: "Discord issues scopes for different user data: identify (username, avatar — the default), email (the user's email address), guilds (the user's list of servers), and guilds.join (add the user to a server). Request the ones you need through the form's Required Scopes field; identify is used if you leave it empty.",
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
		{ key: "enable_cimd", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
