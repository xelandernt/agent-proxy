export type ProviderPattern =
	| "oauth-proxy"
	| "remote-oauth"
	| "token-verification"
	| "gateway-internal";

export type StepKind = "step" | "tip" | "warning" | "info";

export type ProviderStep = {
	title: string;
	body: string;
	kind?: StepKind;
};

export type FieldEntry =
	| { key: string; shared: true }
	| { key: string; text: string };

export type ProviderGuide = {
	id: string;
	name: string;
	tagline: string;
	pattern: ProviderPattern;
	providerSteps: ProviderStep[];
	fields: FieldEntry[];
};

export const PATTERN_LABELS: Record<ProviderPattern, string> = {
	"oauth-proxy": "OAuth proxy",
	"remote-oauth": "Remote OAuth",
	"token-verification": "Token verification",
	"gateway-internal": "Gateway-internal",
};

export const PATTERN_ORDER: ProviderPattern[] = [
	"oauth-proxy",
	"remote-oauth",
	"token-verification",
	"gateway-internal",
];
