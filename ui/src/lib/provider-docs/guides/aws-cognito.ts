import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "aws-cognito",
	name: "AWS Cognito",
	tagline:
		"Secure your MCP servers with AWS Cognito user pools. The gateway bridges Cognito's traditional OAuth to MCP clients and validates Cognito JWTs.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Create a user pool and app client",
			body: "Open the AWS Cognito console in the region where you want the user pool, select User pools, and click Create user pool.",
		},
		{
			title: "Choose Traditional web application",
			body: "For Application type select Traditional web application. This is the correct choice for server-side authentication: it enables client secrets, the authorization-code grant, and the security settings a confidential client needs. Do not pick SPA, Mobile app, or Machine-to-machine.",
			kind: "tip",
		},
		{
			title: "Configure the sign-in and callback options",
			body: "Pick the sign-in identifiers (email, username, or phone), select any required attributes, and add the callback URL: your gateway's public URL plus /auth/callback (e.g. https://mcp.example.com/auth/callback).",
		},
		{
			title: "Review and create the user pool",
			body: "After creation, save the User pool ID (format: eu-central-1_XXXXXXXXX), the Client ID, and the Client Secret. The client ID and secret are under Applications → App clients → your app → App client information.",
		},
		{
			title: "Check the OAuth settings on the app client",
			body: "Under Login pages, verify Allowed callback URLs contains your gateway URL + /auth/callback, OAuth 2.0 grant types includes Authorization code grant, and OpenID Connect scopes covers what you need (openid, email, profile). Local development may use http://localhost; production must use HTTPS.",
			kind: "tip",
		},
		{
			title: "Create a resource server",
			body: "Cognito requires a resource server entry or token exchange fails with invalid_grant. Go to Branding → Domain, click Create resource server, and set the Resource server identifier to the MCP endpoint URL exactly as the gateway exposes it — e.g. https://mcp.example.com/<server-name>/mcp. The identifier must match the URL clients connect to.",
			kind: "warning",
		},
		{
			title: "Save your credentials",
			body: "You now have everything the gateway needs: user pool ID, client ID, client secret, and the AWS region. Store them securely — never commit them to version control.",
		},
	],
	fields: [
		{
			key: "resource_base_url",
			shared: true,
		},
		{ key: "issuer_url", shared: true },
		{
			key: "allowed_client_redirect_uris",
			shared: true,
		},
		{ key: "jwt_signing_key", shared: true },
		{
			key: "require_authorization_consent",
			shared: true,
		},
		{ key: "consent_csp_policy", shared: true },
		{ key: "forward_resource", shared: true },
		{
			key: "fallback_refresh_token_expiry_seconds",
			shared: true,
		},
		{
			key: "fastmcp_access_token_expiry_seconds",
			shared: true,
		},
		{
			key: "token_expiry_threshold_seconds",
			shared: true,
		},
		{ key: "required_scopes", shared: true },
		{
			key: "user_pool_id",
			text: "Your Cognito user pool ID, shown at the top of the pool's details page in the Cognito console. Format: <region>_<random id>, e.g. eu-central-1_XXXXXXXXX.",
		},
		{ key: "client_id", shared: true },
		{ key: "client_secret", shared: true },
		{
			key: "timeout_seconds",
			shared: true,
		},
		{
			key: "aws_region",
			text: "The AWS region your user pool lives in, e.g. eu-central-1. It is part of the user pool ID, but the gateway needs it separately to reach Cognito's token and user-info endpoints.",
		},
		{ key: "redirect_path", shared: true },
	],
};
