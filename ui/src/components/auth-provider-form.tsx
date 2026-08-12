import { Link } from "@tanstack/react-router";
import { CircleHelpIcon, ExternalLinkIcon } from "lucide-react";
import { useState } from "react";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "#/components/ui/select";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "#/components/ui/tooltip";
import {
	getFieldTooltip,
	hasProviderGuide,
} from "#/lib/provider-docs/registry";

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

function effectiveNode(
	node: JsonSchema,
	schema: AuthProviderSchema,
): JsonSchema {
	const resolved = resolveNode(node, schema);
	const union = resolved.anyOf ?? resolved.oneOf;
	if (union) {
		const nonNull = union.find(
			(candidate) => resolveNode(candidate, schema).type !== "null",
		);
		if (nonNull) return effectiveNode(nonNull, schema);
	}
	return resolved;
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
	label,
	value,
	onChange,
}: {
	kind: ReturnType<typeof inputKind>;
	label?: string;
	value: Value;
	onChange: (value: Value) => void;
}) {
	if (kind === "boolean") {
		return (
			<input
				type="checkbox"
				checked={value === true}
				onChange={(event) => onChange(event.target.checked)}
				aria-label={label}
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

function FieldLabel({ label, help }: { label: string; help?: string }) {
	if (!help) {
		return (
			<span className="font-mono text-xs text-muted-foreground">{label}</span>
		);
	}
	return (
		<span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
			{label}
			<Tooltip>
				<TooltipTrigger asChild>
					<button
						type="button"
						aria-label={`Help for ${label}`}
						className="rounded-sm text-muted-foreground/60 outline-none focus-visible:ring-2 focus-visible:ring-ring hover:text-muted-foreground"
					>
						<CircleHelpIcon className="size-3.5" />
					</button>
				</TooltipTrigger>
				<TooltipContent side="right">{help}</TooltipContent>
			</Tooltip>
		</span>
	);
}

function FieldGroup({
	label,
	error,
	help,
	children,
}: {
	label: string;
	error?: string;
	help?: string;
	children: React.ReactNode;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<FieldLabel label={label} help={help} />
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
	providerId,
}: {
	schema: AuthProviderSchema;
	node: JsonSchema;
	value: Record<string, unknown>;
	onChange: (value: Record<string, unknown>) => void;
	fieldErrors: Map<string, string>;
	path: string;
	providerId: string;
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
								<legend className="px-1">
									<FieldLabel
										label={property.title ?? name}
										help={getFieldTooltip(providerId, name)}
									/>
								</legend>
								<ProviderFields
									schema={schema}
									node={objectNode}
									value={(ownedValue as Record<string, unknown>) ?? {}}
									onChange={(nested) => onChange({ ...value, [name]: nested })}
									fieldErrors={fieldErrors}
									path={propertyPath}
									providerId={providerId}
								/>
							</fieldset>
						);
					}

					return (
						<FieldGroup
							key={name}
							label={`${property.title ?? name}${required.has(name) ? " *" : ""}`}
							error={error}
							help={getFieldTooltip(providerId, name)}
						>
							<FieldInput
								kind={kind}
								label={property.title ?? name}
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
		<TooltipProvider delayDuration={250}>
			<div className="flex flex-col gap-4">
				<FieldGroup
					label="Provider *"
					error={errorMap.get("auth.provider")}
					help="Which identity provider issues the tokens your MCP clients will present. Each provider needs its own console setup — the setup guide linked below walks through it."
				>
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
					{provider && hasProviderGuide(provider) && (
						<Link
							to="/docs/$provider"
							params={{ provider }}
							className="inline-flex w-fit items-center gap-1 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
						>
							View setup guide
							<ExternalLinkIcon className="size-3" />
						</Link>
					)}
				</FieldGroup>
				{providerNode && (
					<ProviderFields
						schema={schema}
						node={providerNode}
						value={value}
						onChange={onChange}
						fieldErrors={errorMap}
						path="auth"
						providerId={provider ?? ""}
					/>
				)}
			</div>
		</TooltipProvider>
	);
}
