import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeftIcon, CloudIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import type {
	ModelProviderCreateConfig,
	ModelProviderView,
} from "#/api/generated/fastAPI";
import { SecretInput } from "#/components/secret-input";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import {
	Field,
	FieldDescription,
	FieldGroup,
	FieldLabel,
	FieldLegend,
	FieldSet,
} from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "#/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "#/components/ui/toggle-group";
import { AdminApiError } from "#/lib/admin";
import {
	useCreateModelProvider,
	useUpdateModelProvider,
} from "#/lib/model-gateway-queries";

type ProviderType = ModelProviderCreateConfig["provider"];
type BedrockAuthType = "default" | "api_key" | "access_keys";

const PROVIDER_LABELS: Record<ProviderType, string> = {
	openai: "OpenAI",
	anthropic: "Anthropic",
	azure_openai: "Azure OpenAI",
	bedrock: "AWS Bedrock",
	openai_compatible: "OpenAI-compatible",
};

function stringValue(config: Record<string, unknown>, key: string): string {
	return typeof config[key] === "string" ? config[key] : "";
}

export function ModelProviderForm({
	provider: initial,
}: {
	provider?: ModelProviderView;
}) {
	const navigate = useNavigate();
	const createMutation = useCreateModelProvider();
	const updateMutation = useUpdateModelProvider();
	const initialConfig = (initial?.config ?? {}) as Record<string, unknown>;
	const initialType = stringValue(initialConfig, "provider") as ProviderType;
	const initialCredentials =
		typeof initialConfig.credentials === "object" && initialConfig.credentials
			? (initialConfig.credentials as Record<string, unknown>)
			: {};
	const [name, setName] = useState(initial?.name ?? "");
	const [providerType, setProviderType] = useState<ProviderType>(
		initialType || "openai",
	);
	const [apiKey, setApiKey] = useState("");
	const [organization, setOrganization] = useState(
		stringValue(initialConfig, "organization"),
	);
	const [project, setProject] = useState(stringValue(initialConfig, "project"));
	const [endpoint, setEndpoint] = useState(
		stringValue(initialConfig, "endpoint") ||
			stringValue(initialConfig, "base_url"),
	);
	const [apiVersion, setApiVersion] = useState(
		stringValue(initialConfig, "api_version"),
	);
	const [region, setRegion] = useState(stringValue(initialConfig, "region"));
	const [bedrockAuth, setBedrockAuth] = useState<BedrockAuthType>(
		(stringValue(initialCredentials, "type") as BedrockAuthType) || "default",
	);
	const [accessKeyId, setAccessKeyId] = useState("");
	const [secretAccessKey, setSecretAccessKey] = useState("");
	const [sessionToken, setSessionToken] = useState("");
	const [error, setError] = useState<string | null>(null);
	const submitting = useRef(false);
	const busy = createMutation.isPending || updateMutation.isPending;

	const hasStored = (credential: string) =>
		providerType === initialType &&
		Boolean(initial?.credential_names.includes(credential));
	const secretRequired = (credential: string) => !hasStored(credential);

	const config = (): ModelProviderCreateConfig => {
		if (providerType === "openai") {
			return {
				provider: "openai",
				api_key: apiKey || undefined,
				organization: organization.trim() || undefined,
				project: project.trim() || undefined,
			};
		}
		if (providerType === "anthropic") {
			return { provider: "anthropic", api_key: apiKey || undefined };
		}
		if (providerType === "azure_openai") {
			return {
				provider: "azure_openai",
				api_key: apiKey || undefined,
				endpoint: endpoint.trim(),
				api_version: apiVersion.trim(),
			};
		}
		if (providerType === "openai_compatible") {
			return {
				provider: "openai_compatible",
				api_key: apiKey || undefined,
				base_url: endpoint.trim(),
			};
		}
		if (bedrockAuth === "default") {
			return {
				provider: "bedrock",
				region: region.trim(),
				credentials: { type: "default" },
			};
		}
		if (bedrockAuth === "api_key") {
			return {
				provider: "bedrock",
				region: region.trim(),
				credentials: { type: "api_key", api_key: apiKey || undefined },
			};
		}
		return {
			provider: "bedrock",
			region: region.trim(),
			credentials: {
				type: "access_keys",
				access_key_id: accessKeyId || undefined,
				secret_access_key: secretAccessKey || undefined,
				session_token: sessionToken || undefined,
			},
		};
	};

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		if (submitting.current) return;
		submitting.current = true;
		setError(null);
		try {
			if (initial) {
				await updateMutation.mutateAsync({
					name: initial.name,
					payload: { config: config() },
				});
				toast.success(`Updated ${initial.name}`);
			} else {
				await createMutation.mutateAsync({
					name: name.trim(),
					config: config(),
				});
				toast.success(`Created ${name.trim()}`);
			}
			await navigate({ to: "/admin/model-providers" });
		} catch (caught) {
			setError(
				caught instanceof AdminApiError || caught instanceof Error
					? caught.message
					: "Could not save the provider.",
			);
		} finally {
			submitting.current = false;
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-8">
			<Link to="/admin/model-providers">
				<Button variant="ghost" size="sm">
					<ArrowLeftIcon data-icon="inline-start" />
					Back to providers
				</Button>
			</Link>
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<CloudIcon />
						{initial ? `Edit ${initial.name}` : "New model provider"}
					</CardTitle>
					<CardDescription>
						Configure one reusable inference connection. Credentials are
						encrypted and never returned by the API.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form onSubmit={submit}>
						<FieldGroup>
							<Field>
								<FieldLabel htmlFor="provider-name">Provider name</FieldLabel>
								<Input
									id="provider-name"
									value={name}
									onChange={(event) => setName(event.target.value)}
									placeholder="production-openai"
									disabled={Boolean(initial)}
									required
								/>
								<FieldDescription>
									A recognizable connection name shown in the model form.
								</FieldDescription>
							</Field>
							<Field>
								<FieldLabel htmlFor="provider-type">Provider type</FieldLabel>
								<Select
									value={providerType}
									onValueChange={(value) =>
										setProviderType(value as ProviderType)
									}
								>
									<SelectTrigger id="provider-type">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectGroup>
											{Object.entries(PROVIDER_LABELS).map(([value, label]) => (
												<SelectItem key={value} value={value}>
													{label}
												</SelectItem>
											))}
										</SelectGroup>
									</SelectContent>
								</Select>
							</Field>

							{providerType === "openai" && (
								<>
									<SecretField
										id="provider-api-key"
										label="API key"
										value={apiKey}
										setValue={setApiKey}
										required={secretRequired("api_key")}
										stored={hasStored("api_key")}
									/>
									<Field>
										<FieldLabel htmlFor="provider-organization">
											Organization
										</FieldLabel>
										<Input
											id="provider-organization"
											value={organization}
											onChange={(event) => setOrganization(event.target.value)}
										/>
										<FieldDescription>
											Optional OpenAI organization ID.
										</FieldDescription>
									</Field>
									<Field>
										<FieldLabel htmlFor="provider-project">Project</FieldLabel>
										<Input
											id="provider-project"
											value={project}
											onChange={(event) => setProject(event.target.value)}
										/>
										<FieldDescription>
											Optional OpenAI project ID.
										</FieldDescription>
									</Field>
								</>
							)}
							{providerType === "anthropic" && (
								<SecretField
									id="provider-api-key"
									label="API key"
									value={apiKey}
									setValue={setApiKey}
									required={secretRequired("api_key")}
									stored={hasStored("api_key")}
								/>
							)}
							{providerType === "azure_openai" && (
								<>
									<Field>
										<FieldLabel htmlFor="provider-endpoint">
											Azure endpoint
										</FieldLabel>
										<Input
											id="provider-endpoint"
											type="url"
											value={endpoint}
											onChange={(event) => setEndpoint(event.target.value)}
											placeholder="https://example.openai.azure.com"
											required
										/>
									</Field>
									<Field>
										<FieldLabel htmlFor="provider-api-version">
											API version
										</FieldLabel>
										<Input
											id="provider-api-version"
											value={apiVersion}
											onChange={(event) => setApiVersion(event.target.value)}
											placeholder="2026-06-01"
											required
										/>
									</Field>
									<SecretField
										id="provider-api-key"
										label="API key"
										value={apiKey}
										setValue={setApiKey}
										required={secretRequired("api_key")}
										stored={hasStored("api_key")}
									/>
								</>
							)}
							{providerType === "openai_compatible" && (
								<>
									<Field>
										<FieldLabel htmlFor="provider-base-url">
											Base URL
										</FieldLabel>
										<Input
											id="provider-base-url"
											type="url"
											value={endpoint}
											onChange={(event) => setEndpoint(event.target.value)}
											placeholder="https://api.example.com/v1"
											required
										/>
									</Field>
									<SecretField
										id="provider-api-key"
										label="API key"
										value={apiKey}
										setValue={setApiKey}
										required={secretRequired("api_key")}
										stored={hasStored("api_key")}
									/>
								</>
							)}
							{providerType === "bedrock" && (
								<>
									<Field>
										<FieldLabel htmlFor="provider-region">
											AWS region
										</FieldLabel>
										<Input
											id="provider-region"
											value={region}
											onChange={(event) => setRegion(event.target.value)}
											placeholder="eu-central-1"
											required
										/>
									</Field>
									<FieldSet>
										<FieldLegend>Authentication</FieldLegend>
										<ToggleGroup
											type="single"
											value={bedrockAuth}
											onValueChange={(value) =>
												value && setBedrockAuth(value as BedrockAuthType)
											}
											variant="outline"
										>
											<ToggleGroupItem value="default">
												IAM role
											</ToggleGroupItem>
											<ToggleGroupItem value="api_key">API key</ToggleGroupItem>
											<ToggleGroupItem value="access_keys">
												Access keys
											</ToggleGroupItem>
										</ToggleGroup>
										<FieldDescription>
											IAM role uses the gateway process's default AWS credential
											chain and stores no credentials.
										</FieldDescription>
									</FieldSet>
									{bedrockAuth === "api_key" && (
										<SecretField
											id="provider-api-key"
											label="Bedrock API key"
											value={apiKey}
											setValue={setApiKey}
											required={secretRequired("api_key")}
											stored={hasStored("api_key")}
										/>
									)}
									{bedrockAuth === "access_keys" && (
										<>
											<SecretField
												id="provider-access-key"
												label="Access key ID"
												value={accessKeyId}
												setValue={setAccessKeyId}
												required={secretRequired("access_key_id")}
												stored={hasStored("access_key_id")}
											/>
											<SecretField
												id="provider-secret-key"
												label="Secret access key"
												value={secretAccessKey}
												setValue={setSecretAccessKey}
												required={secretRequired("secret_access_key")}
												stored={hasStored("secret_access_key")}
											/>
											<SecretField
												id="provider-session-token"
												label="Session token"
												value={sessionToken}
												setValue={setSessionToken}
												required={false}
												stored={hasStored("session_token")}
											/>
										</>
									)}
								</>
							)}
							{error && <p className="text-sm text-destructive">{error}</p>}
							<div className="flex justify-end gap-2">
								<Link to="/admin/model-providers">
									<Button type="button" variant="outline">
										Cancel
									</Button>
								</Link>
								<Button type="submit" disabled={busy || !name.trim()}>
									{busy ? "Saving…" : "Save provider"}
								</Button>
							</div>
						</FieldGroup>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}

function SecretField({
	id,
	label,
	value,
	setValue,
	required,
	stored,
}: {
	id: string;
	label: string;
	value: string;
	setValue: (value: string) => void;
	required: boolean;
	stored: boolean;
}) {
	return (
		<Field>
			<FieldLabel htmlFor={id}>{label}</FieldLabel>
			<SecretInput
				id={id}
				label={label}
				value={value}
				onChange={setValue}
				required={required}
				stored={stored}
			/>
			<FieldDescription>
				{stored
					? "A value is stored. Leave blank to keep it."
					: "Required and stored encrypted."}
			</FieldDescription>
		</Field>
	);
}
