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
	type AuthProviderSchema,
	effectiveNode,
	formatStringMap,
	type InputSpec,
	initialValue,
	inputSpec,
	type JsonSchema,
	parseStringMap,
	parseTextValue,
	resolveNode,
} from "#/lib/auth-schema";
import {
	getFieldTooltip,
	hasProviderGuide,
} from "#/lib/provider-docs/registry";

export type { AuthProviderSchema } from "#/lib/auth-schema";

export const SECRET_MASK = "**********";

type Value = unknown;

function isMaskedSecret(value: Value): boolean {
	return typeof value === "string" && value === SECRET_MASK;
}

function StringMapInput({
	label,
	value,
	onChange,
}: {
	label?: string;
	value: Value;
	onChange: (value: Value) => void;
}) {
	const [raw, setRaw] = useState(() => formatStringMap(value));
	return (
		<textarea
			value={raw}
			onChange={(event) => {
				setRaw(event.target.value);
				onChange(parseStringMap(event.target.value));
			}}
			aria-label={label}
			placeholder="key=value"
			rows={3}
			className="w-full rounded-md border bg-transparent px-3 py-2 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
		/>
	);
}

function FieldInput({
	spec,
	label,
	value,
	onChange,
}: {
	spec: Exclude<InputSpec, { kind: "object" }>;
	label?: string;
	value: Value;
	onChange: (value: Value) => void;
}) {
	if (spec.kind === "boolean") {
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
	if (spec.kind === "choice") {
		const selected = spec.choices.some((choice) => Object.is(choice, value))
			? JSON.stringify(value)
			: "";
		return (
			<select
				value={selected}
				onChange={(event) =>
					onChange(event.target.value ? JSON.parse(event.target.value) : null)
				}
				aria-label={label}
				className="h-9 w-full rounded-md border bg-background px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
			>
				<option value="">Select a value</option>
				{spec.choices.map((choice) => (
					<option key={JSON.stringify(choice)} value={JSON.stringify(choice)}>
						{String(choice)}
					</option>
				))}
			</select>
		);
	}
	if (spec.kind === "map") {
		return <StringMapInput label={label} value={value} onChange={onChange} />;
	}
	const masked = isMaskedSecret(value);
	const raw =
		spec.kind === "list" || spec.kind === "string-or-list"
			? Array.isArray(value)
				? value.join(", ")
				: typeof value === "string"
					? value
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
				spec.kind === "secret"
					? "password"
					: spec.kind === "url"
						? "url"
						: spec.kind === "number"
							? "number"
							: "text"
			}
			value={raw}
			onChange={(event) =>
				onChange(parseTextValue(spec.kind, event.target.value))
			}
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
					const spec = inputSpec(property, schema);
					const propertyPath = path ? `${path}.${name}` : name;
					const current = value[name];
					const ownedValue = initialValue(property, schema, current);
					const error = errorFor(name, propertyPath);

					if (spec.kind === "object") {
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
							key={`${providerId}:${name}`}
							label={`${property.title ?? name}${required.has(name) ? " *" : ""}`}
							error={error}
							help={getFieldTooltip(providerId, name)}
						>
							<FieldInput
								spec={spec}
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
