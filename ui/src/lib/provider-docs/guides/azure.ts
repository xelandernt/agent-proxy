import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "azure",
	name: "Azure (Microsoft Entra ID)",
	tagline:
		"Secure your MCP servers with Azure (Microsoft Entra ID). The gateway bridges Entra's traditional OAuth to MCP clients and validates Entra JWTs against your app registration.",
	pattern: "oauth-proxy",
	providerSteps: [
		{
			title: "Create an app registration",
			body: "Sign in to the Azure Portal and go to Microsoft Entra ID → App registrations → New registration. Give the app a recognizable name and pick the supported account types (single tenant, multitenant, or multitenant plus personal accounts).",
		},
		{
			title: "Register the redirect URI",
			body: "Set Platform to Web and enter your gateway's public URL plus /auth/callback, e.g. https://mcp.example.com/auth/callback. The URI must match exactly — the gateway uses the same default path unless you change its redirect_path. Local development may use http://localhost; production must use HTTPS.",
			kind: "warning",
		},
		{
			title: "Expose an API and define scopes",
			body: "Under Expose an API, click Set next to Application ID URI — keep the default api://<client-id> or set a custom value following Entra's identifier URI restrictions. Then add the scopes your server requires (e.g. read, write), with an admin consent display name and the consent audience (admins only, or admins and users).",
		},
		{
			title: "Enable access token v2",
			body: "Open Manifest in the app registration sidebar, set requestedAccessTokenVersion to 2, and save. Access token v2 is required for the integration to work — with v1 tokens authentication fails.",
			kind: "warning",
		},
		{
			title: "Create a client secret",
			body: "Go to Certificates & secrets → New client secret, add a description and expiration, then click Add. Copy the secret value immediately — it is shown only once. Alternatively, configure a client certificate and skip the secret; the gateway accepts either a client secret or a JWT signing key.",
		},
		{
			title: "Note your credentials",
			body: "From the Overview page, note the Application (client) ID and the Directory (tenant) ID — both UUIDs. Use your specific tenant ID: Azure no longer supports the 'common' value for new applications. Store the credentials securely and never commit them to version control.",
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
		{ key: "client_id", shared: true },
		{
			key: "client_secret",
			text: "Your app's client secret from Certificates & secrets, or leave empty if you set a JWT signing key. At least one of client_secret or jwt_signing_key is required — the signing key also signs the tokens the gateway issues to clients.",
		},
		{
			key: "tenant_id",
			text: "Your Microsoft Entra tenant ID — the Directory (tenant) ID GUID from the Overview page of your app registration. Use your specific tenant ID; Azure no longer supports 'common' for new applications.",
		},
		{
			key: "required_scopes",
			text: "Scopes the access token must carry, e.g. api://<app-id>/<scope>. Enter the unprefixed scope names from Expose an API (e.g. read, write) — the gateway prefixes them with your identifier_uri automatically. At least one scope is required; Entra rejects authorization requests without a scope parameter.",
		},
		{
			key: "identifier_uri",
			text: "Your application's Application ID URI from Expose an API, e.g. api://<app-id>. Required scopes are prefixed with this value before being sent to Entra. Leave empty to use the default api://<client_id>.",
		},
		{
			key: "additional_authorize_scopes",
			text: "Extra scopes sent on the authorize request as-is, for external resources such as Microsoft Graph (e.g. User.Read). They are not validated on the returned token — Entra issues separate tokens per resource.",
		},
		{
			key: "base_authority",
			text: "The Entra authority host, defaulting to login.microsoftonline.com. Change it to login.microsoftonline.us for Azure Government.",
		},
		{
			key: "token_issuer",
			text: "The expected iss claim on issued tokens. Only set it when it differs from the standard authority URL, e.g. for sovereign clouds or Azure AD B2C tenants.",
		},
		{ key: "enable_cimd", shared: true },
		{ key: "redirect_path", shared: true },
	],
};
