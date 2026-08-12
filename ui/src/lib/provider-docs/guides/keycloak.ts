import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "keycloak",
	name: "Keycloak",
	tagline:
		"Secure your MCP servers with Keycloak. The gateway validates Keycloak-issued JWTs directly against your realm — no OAuth proxy, no client secret.",
	pattern: "token-verification",
	providerSteps: [
		{
			title: "Create a realm",
			body: "Open your Keycloak Admin Console and create a realm, or use an existing one. The gateway verifies tokens against the realm URL you configure, so any realm you run works — it does not need to be set up in a specific way.",
		},
		{
			title: "Create a client",
			body: "Under Clients → Create client, choose OpenID Connect as the client type and pick the access type that matches how your users log in. Save the client ID — the gateway uses it as the default audience. Note that the gateway never runs the login flow itself: the client exists so your frontend or app can mint tokens for users.",
		},
		{
			title: "Assign scopes to the client",
			body: "On the client's Client scopes tab, keep the realm default scopes (openid, email, profile) or add the custom scopes you want to enforce. The gateway rejects tokens missing any scope you list in Required Scopes.",
		},
		{
			title: "Add an audience mapper",
			body: "If you want tokens to carry a specific aud claim, add an audience mapper to the client: Client scopes → the client's dedicated scope → Add mapper → Audience, and set the audience to your client ID or your gateway's public URL.",
			kind: "tip",
		},
		{
			title: "Set the audience",
			body: "Keycloak issues tokens with a default audience, and the gateway rejects tokens whose aud claim does not match. Set the form's Audience to your client ID (or your gateway's public URL if you mapped it) — or leave it empty to fall back to the client ID.",
			kind: "warning",
		},
		{
			title: "Copy the realm URL",
			body: "The gateway needs the realm URL itself, not the discovery document: e.g. http://keycloak.localhost:8080/realms/<realm-name>. It is shown on the realm's settings page, and the gateway uses it to validate the token's iss claim and fetch signing keys.",
			kind: "tip",
		},
		{
			title: "Test against the local dev Keycloak",
			body: "This repo runs a local Keycloak for development via Docker Compose. Start it, and a realm is ready at http://keycloak.localhost:8080/realms/agent-proxy with pre-created clients such as mcp-inspector and agent-proxy-admin-ui. Point Realm URL at it to try the setup end-to-end.",
		},
	],
	fields: [
		{
			key: "realm_url",
			text: "Your Keycloak realm URL, e.g. https://<host>/realms/<realm-name>. Use the realm URL itself, without a trailing /.well-known path — e.g. http://keycloak.localhost:8080/realms/agent-proxy for the local dev realm.",
		},
		{ key: "required_scopes", shared: true },
		{
			key: "audience",
			text: "The expected audience (aud claim) of the token — set it to your Keycloak client ID, or comma-separate multiple. If empty, falls back to client_id.",
		},
		{
			key: "client_id",
			text: "The Keycloak client whose tokens the gateway accepts; used as the audience when audience is empty.",
		},
	],
};
