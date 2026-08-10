import { useState } from "react";

import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "#/components/ui/select";

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
};

export type AuthProviderSchema = {
	$defs?: Record<string, JsonSchema>;
	discriminator?: { propertyName?: string; mapping?: Record<string, string> };
};

export const SECRET_MASK = "**********";

type Value = unknown;

function resolveNode(node: JsonSchema, schema: AuthProviderSchema): JsonSchema {
	if (node.$ref && schema.$defs) {
		const name = node.$ref.split("/").pop();
		if (name && schema.$defs[name]) return schema.$defs[name];
	}
	return node;
}

function branchNode(node: JsonSchema): JsonSchema {
	const union = node.anyOf ?? node.oneOf;
	if (!union) return node;
	const nonNull = union.find((candidate) => candidate.type !== "null");
	return nonNull ?? node;
}

function effectiveNode(
	node: JsonSchema,
	schema: AuthProviderSchema,
): JsonSchema {
	return branchNode(resolveNode(node, schema));
}

function isSecret(node: JsonSchema): boolean {
	return node.writeOnly === true || node.format === "password";
}

function inputKind(
	node: JsonSchema,
	schema: AuthProviderSchema,
): "text" | "secret" | "url" | "number" | "boolean" | "list" | "object" {
	const resolved = effectiveNode(node, schema);
	if (resolved.type === "boolean") return "boolean";
	if (resolved.type === "number" || resolved.type === "integer")
		return "number";
	if (resolved.type === "array") return "list";
	if (resolved.type === "object") return "object";
	if (isSecret(resolved)) return "secret";
	if (resolved.format === "uri") return "url";
	return "text";
}

function initialValue(
	node: JsonSchema,
	schema: AuthProviderSchema,
	current?: Value,
): Value {
	const resolved = effectiveNode(node, schema);
	if (current !== undefined && current !== null) return current;
	if (resolved.default !== undefined) return resolved.default;
	return null;
}

function isMaskedSecret(value: Value): boolean {
	return typeof value === "string" && value === SECRET_MASK;
}

function parseValue(kind: ReturnType<typeof inputKind>, raw: string): Value {
	if (kind === "number") {
		if (raw === "") return null;
		const parsed = Number(raw);
		return Number.isNaN(parsed) ? raw : parsed;
	}
	if (kind === "list") {
		const items = raw
			.split(",")
			.map((item) => item.trim())
			.filter(Boolean);
		return items.length > 0 ? items : null;
	}
	return raw === "" ? null : raw;
}

function FieldInput({
	kind,
	value,
	onChange,
}: {
	kind: ReturnType<typeof inputKind>;
	value: Value;
	onChange: (value: Value) => void;
}) {
	if (kind === "boolean") {
		return (
			<input
				type="checkbox"
				checked={value === true}
				onChange={(event) => onChange(event.target.checked)}
				className="size-4 rounded border-border accent-[var(--color-primary)]"
			/>
		);
	}
	const masked = isMaskedSecret(value);
	const raw =
		kind === "list"
			? Array.isArray(value)
				? value.join(", ")
				: ""
			: masked
				? ""
				: typeof value === "number"
					? String(value)
					: typeof value === "string"
						? value
						: "";
	return (
		<input
			type={
				kind === "secret"
					? "password"
					: kind === "url"
						? "url"
						: kind === "number"
							? "number"
							: "text"
			}
			value={raw}
			onChange={(event) => onChange(parseValue(kind, event.target.value))}
			placeholder={masked ? "unchanged — re-enter to change" : ""}
			className="h-9 w-full rounded-md border bg-transparent px-3 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
		/>
	);
}

function FieldGroup({
	label,
	error,
	children,
}: {
	label: string;
	error?: string;
	children: React.ReactNode;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<span className="font-mono text-xs text-muted-foreground">{label}</span>
			{children}
			{error && <span className="text-xs text-destructive">{error}</span>}
		</div>
	);
}

function ProviderFields({
	schema,
	node,
	value,
	onChange,
	fieldErrors,
	path,
}: {
	schema: AuthProviderSchema;
	node: JsonSchema;
	value: Record<string, unknown>;
	onChange: (value: Record<string, unknown>) => void;
	fieldErrors: Map<string, string>;
	path: string;
}) {
	const resolved = resolveNode(node, schema);
	const properties = resolved.properties ?? {};
	const required = new Set(resolved.required ?? []);

	const errorFor = (name: string, propertyPath: string): string | undefined => {
		const exact = fieldErrors.get(propertyPath);
		if (exact) return exact;
		for (const [entry, message] of fieldErrors) {
			if (entry.startsWith(`${path}.`) && entry.endsWith(`.${name}`)) {
				return message;
			}
		}
		return undefined;
	};

	return (
		<div className="flex flex-col gap-4">
			{Object.entries(properties)
				.filter(([, property]) => property.const === undefined)
				.map(([name, property]) => {
					const kind = inputKind(property, schema);
					const propertyPath = path ? `${path}.${name}` : name;
					const current = value[name];
					const ownedValue = initialValue(property, schema, current);
					const error = errorFor(name, propertyPath);

					if (kind === "object") {
						const objectNode = effectiveNode(property, schema);
						return (
							<fieldset
								key={name}
								className="flex flex-col gap-3 rounded-md border p-4"
							>
								<legend className="px-1 font-mono text-xs text-foreground">
									{property.title ?? name}
								</legend>
								<ProviderFields
									schema={schema}
									node={objectNode}
									value={(ownedValue as Record<string, unknown>) ?? {}}
									onChange={(nested) => onChange({ ...value, [name]: nested })}
									fieldErrors={fieldErrors}
									path={propertyPath}
								/>
							</fieldset>
						);
					}

					return (
						<FieldGroup
							key={name}
							label={`${property.title ?? name}${required.has(name) ? " *" : ""}`}
							error={error}
						>
							<FieldInput
								kind={kind}
								value={ownedValue}
								onChange={(next) => onChange({ ...value, [name]: next })}
							/>
						</FieldGroup>
					);
				})}
		</div>
	);
}

export function AuthProviderForm({
	schema,
	value,
	onChange,
	fieldErrors = [],
}: {
	schema: AuthProviderSchema;
	value: Record<string, unknown>;
	onChange: (value: Record<string, unknown>) => void;
	fieldErrors?: Array<{ field: string; message: string }>;
}) {
	const mapping = schema.discriminator?.mapping ?? {};
	const providers = Object.keys(mapping).sort();
	const selected =
		typeof value.provider === "string" ? value.provider : undefined;
	const [displayProvider, setDisplayProvider] = useState<string | undefined>(
		selected,
	);
	const provider = selected ?? displayProvider;

	const selectProvider = (name: string) => {
		setDisplayProvider(name);
		onChange({ provider: name });
	};

	const errorMap = new Map(
		fieldErrors.map((entry) => [entry.field, entry.message]),
	);
	const ref = provider ? mapping[provider] : undefined;
	const providerNode = ref ? { $ref: ref } : undefined;

	return (
		<div className="flex flex-col gap-4">
			<FieldGroup label="Provider *" error={errorMap.get("auth.provider")}>
				<Select value={provider ?? ""} onValueChange={selectProvider}>
					<SelectTrigger className="w-full">
						<SelectValue placeholder="Select provider" />
					</SelectTrigger>
					<SelectContent>
						{providers.map((name) => (
							<SelectItem key={name} value={name}>
								<span className="font-mono">{name}</span>
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</FieldGroup>
			{providerNode && (
				<ProviderFields
					schema={schema}
					node={providerNode}
					value={value}
					onChange={onChange}
					fieldErrors={errorMap}
					path="auth"
				/>
			)}
		</div>
	);
}
