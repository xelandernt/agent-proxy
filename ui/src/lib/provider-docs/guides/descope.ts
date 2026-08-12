import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "descope",
	name: "Descope",
	tagline:
		"Secure your MCP servers with Descope. Descope handles user login, MCP clients register directly with your project, and the gateway validates the tokens.",
	pattern: "remote-oauth",
	providerSteps: [
		{
			title: "Create a Descope account and project",
			body: "Sign up at descope.com for a Free Forever account. Each project has an ID in the format P2... that appears in its URLs.",
		},
		{
			title: "Create an MCP server application",
			body: "Go to the MCP Servers page of the Descope Console and create a server, or use a project-level inbound app — the gateway accepts either.",
		},
		{
			title: "Enable Dynamic Client Registration",
			body: "Enable Dynamic Client Registration (DCR) on the application. DCR is required for MCP clients to register automatically with your Descope project.",
			kind: "warning",
		},
		{
			title: "Copy the well-known URL",
			body: "Copy the OIDC discovery URL for your application. A resource-specific MCP server looks like https://api.descope.com/v1/apps/agentic/P.../M.../.well-known/openid-configuration; a project-level inbound app is https://api.descope.com/v1/apps/P.../.well-known/openid-configuration.",
		},
		{
			title: "Leave scopes to discovery",
			body: "If you omit required_scopes and scopes_supported in the gateway form, Descope discovers the supported scopes from the OpenID configuration and advertises them to MCP clients. Set both only when clients should request a broader set of scopes than the server requires.",
			kind: "tip",
		},
	],
	fields: [
		{ key: "required_scopes", shared: true },
		{ key: "scopes_supported", shared: true },
		{ key: "resource_name", shared: true },
		{ key: "resource_documentation", shared: true },
		{
			key: "config_url",
			text: "The OIDC discovery URL for your Descope project, e.g. https://api.descope.com/v1/apps/P.../.well-known/openid-configuration. Provide either this, or project_id together with descope_base_url.",
		},
		{
			key: "project_id",
			text: "Your Descope project ID, e.g. P2.... Provide it together with descope_base_url when you don't have a config_url.",
		},
		{
			key: "descope_base_url",
			text: "Your Descope region base URL, e.g. https://api.descope.com. Provide it together with project_id when you don't have a config_url.",
		},
	],
};
