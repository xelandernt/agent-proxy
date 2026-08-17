import type { ProviderGuide } from "../types";

export const guide: ProviderGuide = {
	id: "none",
	name: "No authentication",
	tagline:
		"Leave the server unlinked from an authentication provider when the upstream owns authentication.",
	pattern: "no-auth",
	providerSteps: [
		{
			title: "Point the gateway at your authenticated upstream",
			body: "Leave Gateway authentication set to No gateway authentication when your upstream MCP server already requires credentials. The gateway performs no token verification of its own: any request reaches the upstream, and whatever the upstream rejects is relayed back unchanged.",
		},
		{
			title: "Relay the client's token",
			body: "With the Forward client credentials toggle enabled, the Authorization header your MCP client sends to the gateway is passed straight through to the upstream. This is the setting for an authenticated upstream: clients keep using the token they already have for your server.",
			kind: "tip",
		},
		{
			title: "Keep the firewall on unless you need relaying",
			body: "Forward client credentials defaults to off, so a request's Authorization header is stripped before it leaves the gateway. Leave it off when the upstream needs no token — it prevents a leaked front-end token from reaching a backend that ignores it.",
		},
		{
			title: "Understand the trust boundary",
			body: "With no provider link the gateway adds no identity boundary: anyone who can reach the gateway URL can call the server, and the gateway cannot tell authenticated from unauthenticated traffic. Only use this mode when your upstream's own authentication protects the tools.",
			kind: "warning",
		},
	],
	fields: [],
};
