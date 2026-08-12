import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "jwt",
	name: "JWT (self-signed tokens)",
	tagline:
		"Validate bearer tokens issued by your own authorization system — the gateway verifies pre-issued JWTs and serves no OAuth flows.",
	pattern: "token-verification",
	providerSteps: [
		{
			title: "Choose how clients obtain tokens",
			body: "Your authorization system mints and signs JWTs that MCP clients present as bearer tokens. The gateway never runs an OAuth flow — it only verifies tokens that were issued beforehand, so make sure your clients have a way to obtain them.",
		},
		{
			title: "Expose the signing key's public key",
			body: "The gateway needs the public side of your signing key to verify signatures. Either paste the PEM-formatted public key into public_key, or publish your JSON Web Key Set at a URL and put that URL in jwks_uri. One of the two is required.",
		},
		{
			title: "Decide the expected claims",
			body: "Set issuer to the exact iss value your tokens carry and audience to the expected aud value; tokens that do not match are rejected. Optionally pin the signing algorithm and require specific scopes.",
		},
		{
			title: "Restrict the JWKS host when using jwks_uri",
			body: "The gateway fetches jwks_uri at runtime, so a misconfigured or compromised URI could point it at an internal host. Enable ssrf_safe to allow fetches only to known, allow-listed hosts. Only leave it off when you fully control the host serving the key set.",
			kind: "warning",
		},
		{
			title: "Test with a real token",
			body: "Mint a token with your signing key and try it against the server. If verification fails, check that the key format, algorithm, issuer, and audience all match what your authorization system actually emits.",
			kind: "tip",
		},
	],
	fields: [
		{
			key: "public_key",
			text: "The PEM-formatted public key of your signing key, e.g. -----BEGIN PUBLIC KEY----- ... -----END PUBLIC KEY-----. Paste it exactly as exported; the gateway needs it to verify token signatures.",
		},
		{
			key: "jwks_uri",
			text: "A URL serving your JSON Web Key Set (JWKS) — the public keys the gateway uses to verify token signatures. One of public_key or jwks_uri is required.",
		},
		{
			key: "issuer",
			text: "The expected iss claim of accepted tokens. A single value or a comma-separated list. Tokens from any other issuer are rejected. Optional; leave empty to accept any issuer.",
		},
		{
			key: "audience",
			text: "The expected aud claim of accepted tokens. A single value or a comma-separated list. Tokens for any other audience are rejected. Optional; leave empty to accept any audience.",
		},
		{
			key: "algorithm",
			text: "The JWT signing algorithm your tokens use, e.g. RS256, ES256. Leave empty to accept any algorithm the key supports.",
		},
		{ key: "required_scopes", shared: true },
		{
			key: "ssrf_safe",
			text: "Whether the gateway should only fetch jwks_uri from allow-listed hosts to protect against SSRF. The gateway fetches the URI at runtime; enable this unless you fully control the host.",
		},
	],
};
