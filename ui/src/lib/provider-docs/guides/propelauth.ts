import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "propelauth",
	name: "PropelAuth",
	tagline:
		"Secure your MCP servers with PropelAuth. PropelAuth handles user login and consent, MCP clients register directly, and the gateway validates tokens via introspection.",
	pattern: "remote-oauth",
	providerSteps: [
		{
			title: "Create a PropelAuth account",
			body: "Sign up at propelauth.com. Your tenant's auth URL is shown in the Backend Integration section of the dashboard.",
		},
		{
			title: "Enable MCP authentication",
			body: "Navigate to the MCP section in your PropelAuth dashboard, click Enable MCP, and choose which environments to enable it for (Test, Staging, Prod).",
		},
		{
			title: "Configure allowed MCP clients",
			body: "Under MCP → Allowed MCP Clients, add redirect URIs for each MCP client you want to allow. PropelAuth provides templates for popular clients like Claude, Cursor, and ChatGPT.",
		},
		{
			title: "Configure scopes",
			body: "Under MCP → Scopes, define the permissions available to MCP clients, e.g. read:user_data. The gateway can require these scopes in the tokens it validates.",
		},
		{
			title: "Choose how users create OAuth clients",
			body: "Under MCP → Settings → How Do Users Create OAuth Clients?, enable Dynamic Client Registration so clients self-register automatically via the DCR protocol. You can also let users register manually via hosted pages, or manage client creation yourself.",
			kind: "tip",
		},
		{
			title: "Generate introspection credentials",
			body: "Go to MCP → Request Validation and click Create Credentials. Note the Client ID and Client Secret — the gateway uses them to call PropelAuth's token-introspection endpoint.",
		},
		{
			title: "Note your auth URL",
			body: "Find your Auth URL in the Backend Integration section of the dashboard (e.g. https://auth.yourdomain.com). You'll enter it in the gateway form.",
		},
	],
	fields: [
		{ key: "required_scopes", shared: true },
		{ key: "scopes_supported", shared: true },
		{ key: "resource_name", shared: true },
		{ key: "resource_documentation", shared: true },
		{
			key: "auth_url",
			text: "Your PropelAuth tenant auth URL, e.g. https://<tenant>.propelauth.com. The gateway uses it to discover PropelAuth's OAuth endpoints.",
		},
		{
			key: "introspection_client_id",
			text: "The client ID for PropelAuth token introspection, generated under MCP → Request Validation in the dashboard.",
		},
		{
			key: "introspection_client_secret",
			text: "The corresponding client secret — keep it secure. It is shown once when you create the introspection credentials.",
		},
		{
			key: "resource",
			text: "The resource the gateway's tokens are issued for, e.g. your gateway's public URL. Tokens intended for a different resource are rejected. Optional; leave empty to accept any resource.",
		},
		{
			key: "token_introspection",
			shared: true,
		},
		{
			key: "timeout_seconds",
			shared: true,
		},
		{
			key: "cache_ttl_seconds",
			shared: true,
		},
		{
			key: "max_cache_size",
			shared: true,
		},
	],
};
