import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "static",
	name: "Static credentials",
	tagline:
		"Gateway-internal username/password for this server's clients — the gateway authenticates them itself, with no external identity provider.",
	pattern: "gateway-internal",
	providerSteps: [
		{
			title: "Choose a username and password",
			body: "The gateway itself authenticates clients against the username and password you configure. Pick something strong — the password is stored in the gateway's server config, so treat it like any other credential.",
		},
		{
			title: "Generate a strong jwt_secret",
			body: "When a client logs in, the gateway mints a short-lived JWT signed with jwt_secret. Generate a long random value, e.g. `openssl rand -hex 32`, and keep it secret — anyone holding it can forge tokens. Changing it invalidates all previously issued tokens.",
		},
		{
			title: "Decide how long tokens stay valid",
			body: "Set token_ttl_seconds to how long a minted token remains valid (default 3600). Shorter values force clients to re-authenticate more often but limit the blast radius of a leaked token.",
		},
		{
			title: "Hand the bearer token to your clients",
			body: "MCP clients cannot complete an OAuth flow against a static provider — there is no authorization server to redirect to. Clients must present the gateway-issued bearer token directly, exactly as the admin interface does to authenticate.",
			kind: "warning",
		},
	],
	fields: [
		{
			key: "username",
			text: 'Any username you choose. Clients must send it together with the password to authenticate. Defaults to "user".',
		},
		{
			key: "password",
			text: "The password clients authenticate with. Pick something strong — it is stored in the gateway config, so it is only as safe as that config.",
		},
		{
			key: "jwt_secret",
			text: "The secret used to sign and verify the gateway-issued tokens. Use a long random string, e.g. `openssl rand -hex 32`, and keep it secret — anyone holding it can forge tokens. Changing it invalidates existing tokens.",
		},
		{
			key: "token_ttl_seconds",
			text: "How long a minted token stays valid, in seconds. Default 3600. The token carries the server's own issuer and audience, so it can only be used against this gateway.",
		},
	],
};
