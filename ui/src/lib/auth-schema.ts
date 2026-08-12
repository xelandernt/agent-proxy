export type JsonSchema = {
	$ref?: string;
	type?: string;
	const?: unknown;
	title?: string;
	format?: string;
	writeOnly?: boolean;
	default?: unknown;
	enum?: unknown[];
	anyOf?: JsonSchema[];
	oneOf?: JsonSchema[];
	items?: JsonSchema;
	properties?: Record<string, JsonSchema>;
	required?: string[];
	additionalProperties?: boolean | JsonSchema;
};

export type AuthProviderSchema = {
	$defs?: Record<string, JsonSchema>;
	discriminator?: { propertyName?: string; mapping?: Record<string, string> };
};

export type InputSpec =
	| { kind: "text" | "secret" | "url" | "number" | "boolean" | "list" }
	| { kind: "string-or-list" }
	| { kind: "choice"; choices: unknown[] }
	| { kind: "object" | "map" };

export function resolveNode(
	node: JsonSchema,
	schema: AuthProviderSchema,
): JsonSchema {
	if (node.$ref && schema.$defs) {
		const name = node.$ref.split("/").pop();
		if (name && schema.$defs[name]) return schema.$defs[name];
	}
	return node;
}

function variants(node: JsonSchema, schema: AuthProviderSchema): JsonSchema[] {
	const resolved = resolveNode(node, schema);
	const union = resolved.anyOf ?? resolved.oneOf;
	if (!union) return [resolved];
	return union
		.map((candidate) => resolveNode(candidate, schema))
		.filter((candidate) => candidate.type !== "null");
}

export function effectiveNode(
	node: JsonSchema,
	schema: AuthProviderSchema,
): JsonSchema {
	const resolved = resolveNode(node, schema);
	if (!(resolved.anyOf ?? resolved.oneOf)) return resolved;
	const candidates = variants(node, schema);
	return candidates.length === 1
		? effectiveNode(candidates[0], schema)
		: resolved;
}

function isSecret(node: JsonSchema): boolean {
	return node.writeOnly === true || node.format === "password";
}

export function inputSpec(
	node: JsonSchema,
	schema: AuthProviderSchema,
): InputSpec {
	const candidates = variants(node, schema);
	if (candidates.length > 1) {
		const types = new Set(candidates.map((candidate) => candidate.type));
		if (types.size === 2 && types.has("string") && types.has("array")) {
			return { kind: "string-or-list" };
		}
		const choices = candidates.flatMap((candidate) => {
			if (candidate.enum) return candidate.enum;
			if (candidate.type === "boolean") return [true, false];
			return [];
		});
		if (choices.length > 0) return { kind: "choice", choices };
	}

	const resolved = candidates[0] ?? effectiveNode(node, schema);
	if (resolved.enum) return { kind: "choice", choices: resolved.enum };
	if (resolved.type === "boolean") return { kind: "boolean" };
	if (resolved.type === "number" || resolved.type === "integer") {
		return { kind: "number" };
	}
	if (resolved.type === "array") return { kind: "list" };
	if (resolved.type === "object") {
		return resolved.additionalProperties ? { kind: "map" } : { kind: "object" };
	}
	if (isSecret(resolved)) return { kind: "secret" };
	if (resolved.format === "uri") return { kind: "url" };
	return { kind: "text" };
}

export function initialValue(
	node: JsonSchema,
	schema: AuthProviderSchema,
	current?: unknown,
): unknown {
	if (current !== undefined && current !== null) return current;
	if (node.default !== undefined) return node.default;
	const resolved = effectiveNode(node, schema);
	return resolved.default ?? null;
}

export function parseTextValue(kind: InputSpec["kind"], raw: string): unknown {
	if (kind === "number") {
		if (raw === "") return null;
		const parsed = Number(raw);
		return Number.isNaN(parsed) ? raw : parsed;
	}
	if (kind === "list" || kind === "string-or-list") {
		const items = raw
			.split(",")
			.map((item) => item.trim())
			.filter(Boolean);
		if (items.length === 0) return null;
		return kind === "string-or-list" && items.length === 1 ? items[0] : items;
	}
	return raw === "" ? null : raw;
}

export function formatStringMap(value: unknown): string {
	if (!value || typeof value !== "object" || Array.isArray(value)) return "";
	return Object.entries(value)
		.map(([key, item]) => `${key}=${String(item)}`)
		.join("\n");
}

export function parseStringMap(raw: string): Record<string, string> | null {
	const entries = raw
		.split("\n")
		.map((line) => line.trim())
		.filter(Boolean)
		.map((line) => {
			const separator = line.indexOf("=");
			return separator < 1
				? [line, ""]
				: [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
		});
	return entries.length > 0 ? Object.fromEntries(entries) : null;
}
