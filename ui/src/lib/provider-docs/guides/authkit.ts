import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "authkit",
	name: "AuthKit",
	tagline:
		"Secure your MCP servers with AuthKit by WorkOS. MCP clients register directly with your AuthKit tenant and the gateway validates the tokens they receive.",
	pattern: "remote-oauth",
	providerSteps: [
		{
			title: "Create a WorkOS account and project",
			body: "Sign up at workos.com and create a new project. The project holds your AuthKit configuration and tenant.",
		},
		{
			title: "Set up an AuthKit instance",
			body: "Create an AuthKit instance within the project and configure your sign-in methods and user management. This is where your tenant lives.",
		},
		{
			title: "Enable MCP authentication",
			body: "In the WorkOS Dashboard, go to Connect → Configuration → MCP Auth and enable Dynamic Client Registration (DCR) so MCP clients can register themselves. Alternatively enable Client ID Metadata Document (CIMD) if your clients support it.",
			kind: "tip",
		},
		{
			title: "Add your gateway as a resource indicator",
			body: "Under MCP resource indicators, add your gateway's public URL plus /mcp (e.g. https://mcp.example.com/<server-name>/mcp) as a valid resource indicator. It must match exactly the resource URL the gateway advertises in its protected resource metadata. Without it, AuthKit falls back to a default environment-scoped audience and token validation fails with a 401.",
			kind: "warning",
		},
		{
			title: "Note your AuthKit domain",
			body: "Find your AuthKit Domain on the configuration page. It looks like https://<your-project-12345>.authkit.app — you'll enter it in the gateway form.",
		},
	],
	fields: [
		{ key: "required_scopes", shared: true },
		{ key: "scopes_supported", shared: true },
		{ key: "resource_name", shared: true },
		{ key: "resource_documentation", shared: true },
		{
			key: "authkit_domain",
			text: "Your AuthKit domain, e.g. https://<tenant>.authkit.app. The gateway uses it to discover AuthKit's OAuth endpoints and JWKS.",
		},
		{ key: "resource_base_url", shared: true },
	],
};
