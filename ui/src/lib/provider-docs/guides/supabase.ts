import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "supabase",
	name: "Supabase",
	tagline:
		"Secure your MCP servers with Supabase Auth. MCP clients register directly with Supabase, and the gateway validates the JWTs Supabase issues.",
	pattern: "remote-oauth",
	providerSteps: [
		{
			title: "Create a Supabase project",
			body: "Create a project on supabase.com or use a self-hosted Supabase Auth instance. You will need the Project URL, found under Project Settings.",
		},
		{
			title: "Enable the OAuth Server",
			body: "In the Supabase dashboard, go to Authentication → OAuth Server. Enable the OAuth Server, set the Site URL to where your consent UI is hosted, set the Authorization Path (e.g. /oauth/callback), and enable Allow Dynamic OAuth Apps so MCP clients can self-register.",
		},
		{
			title: "Host a consent UI",
			body: "Supabase delegates the consent screen to your application: after the user authenticates, Supabase redirects to your callback URL and your application must call Supabase's approveAuthorization() or denyAuthorization() APIs to complete the flow. Without this page the OAuth flow cannot finish.",
			kind: "warning",
		},
		{
			title: "Copy the Project URL",
			body: "Go to Project Settings and copy the Project URL (e.g. https://abc123.supabase.co). This is the only credential the gateway needs.",
		},
		{
			title: "Note the JWT signing algorithm",
			body: "Check which JWT signing algorithm your project uses. The gateway defaults to ES256; set RS256 if your project is configured for RSA signing.",
			kind: "tip",
		},
	],
	fields: [
		{ key: "required_scopes", shared: true },
		{ key: "scopes_supported", shared: true },
		{ key: "resource_name", shared: true },
		{ key: "resource_documentation", shared: true },
		{
			key: "project_url",
			text: "Your Supabase project URL, e.g. https://<project-ref>.supabase.co. Found in the Supabase dashboard under Project Settings.",
		},
		{
			key: "auth_route",
			text: "The auth path, default /auth/v1. Only change it if your Supabase instance serves auth on a different path.",
		},
		{
			key: "algorithm",
			text: "The JWT signing algorithm Supabase uses for your project, RS256 or ES256 — must match the project's settings.",
		},
	],
};
