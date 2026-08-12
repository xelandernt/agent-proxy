import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "oci",
	name: "OCI IAM",
	tagline:
		"Secure your MCP servers with OCI IAM OAuth. The gateway bridges your identity domain's confidential applications to MCP clients and validates domain-issued tokens.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Enable client access for the JWKS endpoint",
			body: "Log in to the OCI console (cloud.oracle.com) and go to Identity & Security → Domains. Select the domain you use for MCP authentication, open the Settings tab, click Edit Domain Settings, and enable Configure client access. The gateway needs this to fetch the domain's JWKS and validate tokens.",
		},
		{
			title: "Add a Confidential Application",
			body: "On the domain's details page, select Integrated applications, click Add application, and choose Confidential Application, then Launch workflow. Enter a name and description for the app.",
		},
		{
			title: "Configure the OAuth client",
			body: "Open the app's OAuth configuration tab and click Edit OAuth configuration. Select Configure this application as a client now, choose the Authorization code grant type, and set the redirect URL to your gateway's public URL plus /auth/callback (e.g. https://mcp.example.com/auth/callback).",
		},
		{
			title: "Activate the application and save credentials",
			body: "Submit the configuration, then make sure to Activate the client application. Note down the client ID and client secret — you'll need both in the form. No special PKCE configuration is required.",
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
		{
			key: "config_url",
			text: "The OIDC discovery URL for your OCI IAM identity domain, e.g. https://<domain-guid>.identity.oraclecloud.com/.well-known/openid-configuration. The gateway uses it to discover the domain's token, userinfo, and JWKS endpoints.",
		},
		{ key: "client_id", shared: true },
		{ key: "client_secret", shared: true },
		{
			key: "audience",
			text: "The audience for tokens issued by your identity domain — usually the domain's base URL, e.g. https://<domain-guid>.identity.oraclecloud.com. The gateway validates the token's aud claim against it.",
		},
		{ key: "timeout_seconds", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
