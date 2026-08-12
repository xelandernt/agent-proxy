import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "scalekit",
	name: "Scalekit",
	tagline:
		"Secure your MCP servers with Scalekit. MCP clients register directly with Scalekit via dynamic client registration, and the gateway validates the tokens Scalekit issues.",
	pattern: "remote-oauth",
	providerSteps: [
		{
			title: "Create a Scalekit account",
			body: "Sign up at app.scalekit.com and open Dashboard → Settings. Copy your Environment URL (e.g. https://<env>.scalekit.com) — you will enter it in the proxy form.",
		},
		{
			title: "Register the MCP server",
			body: "In the Scalekit dashboard, open the MCP Servers section and click Create new server. Enter a name, a resource identifier, and the desired MCP client authentication settings, then save. After saving, copy the Resource ID (e.g. res_92015146095).",
		},
		{
			title: "Have your gateway's public URL ready",
			body: "Scalekit redirects users back to the gateway after authentication, so you need the gateway's public URL. For local development http://localhost works.",
		},
		{
			title: "No credentials go on the gateway",
			body: "Scalekit supports OAuth 2.1 with dynamic client registration: MCP clients self-register with Scalekit using PKCE, so the gateway holds no client credentials. It only needs the environment URL and the resource ID to validate the tokens Scalekit issues.",
			kind: "tip",
		},
	],
	fields: [
		{ key: "required_scopes", shared: true },
		{ key: "scopes_supported", shared: true },
		{ key: "resource_name", shared: true },
		{ key: "resource_documentation", shared: true },
		{
			key: "environment_url",
			text: "Your Scalekit environment URL, e.g. https://<env>.scalekit.com. Found in the Scalekit dashboard under Dashboard → Settings.",
		},
		{
			key: "resource_id",
			text: "Your Scalekit resource ID, e.g. res_92015146095. Shown when you save the MCP server in the Scalekit dashboard's MCP Servers section.",
		},
	],
};
