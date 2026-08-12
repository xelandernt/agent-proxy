/**
 * Shared field guidance, keyed by the JSON-schema property key used in the
 * auth provider form. A field that appears in multiple providers must have
 * its text here, once, so tooltips and docs stay identical everywhere.
 *
 * Provider-specific fields keep their text in the provider's guide data file
 * (`guides/<provider>.tsx`) instead.
 */

export const FIELD_TOOLTIPS: Record<string, string> = {
	client_id:
		"Your application's client ID from the provider console. It is a public identifier shown next to your app's credentials.",
	client_secret:
		"Your application's client secret from the provider console. Treat it like a password — most providers show it only once. It must match the app's OAuth configuration (client type, grant types, callback URLs).",
	config_url:
		"URL of the provider's OIDC discovery document (.well-known/openid-configuration). Find the exact URL in your provider's console or docs.",
	audience:
		"The audience (aud claim) your provider should include in issued tokens — usually an API identifier or resource URL you define in the provider console. The gateway validates the token's aud claim against it.",
	required_scopes:
		"OAuth scopes the client must be granted in the access token. Space- or comma-separated. The provider must support every scope you list; leave empty to accept any scope the provider issues. Common values: openid, email, profile.",
	scopes_supported:
		"Scopes the provider advertises as supported. The client only requests scopes the provider supports. Comma-separated; leave empty to let the client request what it needs.",
	resource_name:
		"A human-readable name for the protected resource (your MCP server) shown to users on the provider's consent screen. Optional.",
	resource_documentation:
		"A URL pointing to documentation about your MCP server, shown on the provider's consent screen. Optional.",
	resource_base_url:
		"The URL of the protected resource your tokens are issued for — usually the gateway's public base URL, e.g. https://mcp.example.com. Optional; leave empty to use the gateway's own base URL.",
	issuer_url:
		"The issuer (iss claim) your provider's tokens must carry. Tokens from any other issuer are rejected. Usually the provider's well-known issuer URL, e.g. https://<tenant>.auth0.com/. Optional; leave empty to trust the issuer discovered automatically.",
	allowed_client_redirect_uris:
		"Additional callback URLs, beyond the default redirect path, that MCP clients may use when completing the OAuth flow. Each entry must be registered as an allowed callback in the provider console. Comma-separated; usually left empty.",
	jwt_signing_key:
		"A secret key the gateway uses to sign tokens it issues (refresh tokens, client-facing tokens). Use a long random string and keep it secret. Set a fixed value so tokens survive gateway restarts.",
	require_authorization_consent:
		"Whether users must approve the consent screen on first login. true = always require consent, false = skip it when the provider allows, remember = remember each user's choice, external = the provider renders its own consent UI.",
	consent_csp_policy:
		"Content-Security-Policy header sent with the gateway-hosted consent screen. Optional; only needed if that page embeds third-party resources.",
	forward_resource:
		"Whether the resource URL is sent to the provider's authorize endpoint. Leave enabled unless your provider rejects the resource parameter.",
	fallback_refresh_token_expiry_seconds:
		"Lifetime in seconds for a refresh token when the provider does not return an explicit expiry. Optional.",
	fastmcp_access_token_expiry_seconds:
		"Lifetime in seconds for the access token the gateway issues to MCP clients. Optional; defaults to the provider's token lifetime.",
	token_expiry_threshold_seconds:
		"How many seconds before expiry the gateway refreshes a token preemptively. 0 = refresh only after it expires.",
	timeout_seconds:
		"Timeout in seconds for outbound requests to the provider (discovery, token exchange). Increase it on slow networks.",
	redirect_path:
		"The path on the gateway where the provider redirects users after login (e.g. /auth/callback). Must match exactly the callback URL registered in the provider console: gateway URL + this path.",
	enable_cimd:
		"Whether the gateway publishes a Client ID Metadata Document for MCP clients. Leave enabled — CIMD lets clients verify the gateway's identity during the OAuth handshake.",
	valid_scopes:
		"Comma-separated scopes accepted from the provider's authorization response. Tokens carrying any other scope are rejected. Optional; leave empty to accept any scope.",
	extra_authorize_params:
		"Extra query parameters appended to the provider's authorize URL, comma-separated key=value pairs, e.g. prompt=consent,access_type=offline. Optional.",
	extra_token_params:
		"Extra query parameters appended to the provider's token exchange request, comma-separated key=value pairs. Optional.",
	cache_ttl_seconds:
		"How long, in seconds, verified results are cached. Lower it if you rotate signing keys or revoke tokens frequently.",
	max_cache_size:
		"Maximum number of entries kept in the verification cache. Only relevant at very high request volumes.",
	token_introspection:
		"Optional overrides for how the provider's token-introspection endpoint is called (timeout, caching).",
};
