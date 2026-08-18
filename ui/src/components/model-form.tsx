import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeftIcon, BoxIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import type {
	JsonValue,
	ModelDeploymentCreate,
	ModelDeploymentUpdate,
	ModelDeploymentView,
} from "#/api/generated/fastAPI";
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
} from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import { Textarea } from "#/components/ui/textarea";
import { AdminApiError } from "#/lib/admin";
import { useCreateModel, useUpdateModel } from "#/lib/model-gateway-queries";

function parseObject(value: string, label: string): Record<string, JsonValue> {
	if (!value.trim()) return {};
	const parsed: unknown = JSON.parse(value);
	if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
		throw new Error(`${label} must be a JSON object.`);
	}
	return parsed as Record<string, JsonValue>;
}

function parseSecrets(value: string): Record<string, string> {
	const parsed = parseObject(value, "Secrets");
	for (const [name, secret] of Object.entries(parsed)) {
		if (typeof secret !== "string") {
			throw new Error(`Secret "${name}" must be a string.`);
		}
	}
	return parsed as Record<string, string>;
}

export function ModelForm({ model }: { model?: ModelDeploymentView }) {
	const navigate = useNavigate();
	const createMutation = useCreateModel();
	const updateMutation = useUpdateModel();
	const [name, setName] = useState(model?.name ?? "");
	const [description, setDescription] = useState(model?.description ?? "");
	const [upstreamModel, setUpstreamModel] = useState(
		model?.upstream_model ?? "",
	);
	const [apiBase, setApiBase] = useState(model?.api_base ?? "");
	const [settings, setSettings] = useState(() =>
		JSON.stringify(model?.settings ?? {}, null, 2),
	);
	const [secrets, setSecrets] = useState("");
	const [removeSecrets, setRemoveSecrets] = useState("");
	const [error, setError] = useState<string | null>(null);
	const submitting = useRef(false);
	const busy = createMutation.isPending || updateMutation.isPending;

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		if (submitting.current) return;
		submitting.current = true;
		setError(null);
		try {
			const parsedSettings = parseObject(settings, "Settings");
			const parsedSecrets = parseSecrets(secrets);
			if (model) {
				const payload: ModelDeploymentUpdate = {
					description,
					upstream_model: upstreamModel,
					api_base: apiBase.trim() || null,
					settings: parsedSettings,
					set_secrets: parsedSecrets,
					remove_secrets: removeSecrets
						.split(",")
						.map((value) => value.trim())
						.filter(Boolean),
				};
				await updateMutation.mutateAsync({ name: model.name, payload });
				toast.success(`Updated ${model.name}`);
			} else {
				const payload: ModelDeploymentCreate = {
					name: name.trim(),
					description,
					upstream_model: upstreamModel.trim(),
					api_base: apiBase.trim() || null,
					settings: parsedSettings,
					secrets: parsedSecrets,
				};
				await createMutation.mutateAsync(payload);
				toast.success(`Created ${payload.name}`);
			}
			await navigate({ to: "/admin/models" });
		} catch (caught) {
			setError(
				caught instanceof AdminApiError || caught instanceof Error
					? caught.message
					: "Could not save the model.",
			);
		} finally {
			submitting.current = false;
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-8">
			<Link to="/admin/models">
				<Button variant="ghost" size="sm">
					<ArrowLeftIcon className="size-4" />
					Back to models
				</Button>
			</Link>
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<BoxIcon className="size-4" />
						{model ? `Edit ${model.name}` : "New model"}
					</CardTitle>
					<CardDescription>
						The public name is exposed through OpenAI-compatible endpoints. The
						upstream model and credentials stay on the gateway.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form onSubmit={submit}>
						<FieldGroup>
							<Field>
								<FieldLabel htmlFor="model-name">Public model name</FieldLabel>
								<Input
									id="model-name"
									value={name}
									onChange={(event) => setName(event.target.value)}
									placeholder="support-agent"
									disabled={Boolean(model)}
									required
								/>
								<FieldDescription>
									Lowercase letters, numbers, and hyphens.
								</FieldDescription>
							</Field>
							<Field>
								<FieldLabel htmlFor="model-description">Description</FieldLabel>
								<Input
									id="model-description"
									value={description}
									onChange={(event) => setDescription(event.target.value)}
								/>
							</Field>
							<Field>
								<FieldLabel htmlFor="upstream-model">LiteLLM model</FieldLabel>
								<Input
									id="upstream-model"
									value={upstreamModel}
									onChange={(event) => setUpstreamModel(event.target.value)}
									placeholder="anthropic/claude-sonnet-4-5"
									required
								/>
								<FieldDescription>
									Use LiteLLM's provider/model syntax.
								</FieldDescription>
							</Field>
							<Field>
								<FieldLabel htmlFor="api-base">Provider endpoint</FieldLabel>
								<Input
									id="api-base"
									type="url"
									value={apiBase}
									onChange={(event) => setApiBase(event.target.value)}
									placeholder="https://example.openai.azure.com"
								/>
								<FieldDescription>
									Optional for providers with a standard endpoint.
								</FieldDescription>
							</Field>
							<Field>
								<FieldLabel htmlFor="model-settings">
									Provider settings
								</FieldLabel>
								<Textarea
									id="model-settings"
									className="min-h-32 font-mono text-xs"
									value={settings}
									onChange={(event) => setSettings(event.target.value)}
								/>
								<FieldDescription>
									JSON object of non-secret LiteLLM arguments.
								</FieldDescription>
							</Field>
							<Field>
								<FieldLabel htmlFor="model-secrets">
									{model ? "Set or replace secrets" : "Provider secrets"}
								</FieldLabel>
								<Textarea
									id="model-secrets"
									className="min-h-24 font-mono text-xs"
									value={secrets}
									onChange={(event) => setSecrets(event.target.value)}
									placeholder={'{\n  "api_key": "..."\n}'}
								/>
								<FieldDescription>
									JSON string values. Stored encrypted and never returned by the
									API.
								</FieldDescription>
							</Field>
							{model && model.secret_names.length > 0 && (
								<Field>
									<FieldLabel htmlFor="remove-secrets">
										Remove secrets
									</FieldLabel>
									<Input
										id="remove-secrets"
										value={removeSecrets}
										onChange={(event) => setRemoveSecrets(event.target.value)}
										placeholder={model.secret_names.join(", ")}
									/>
									<FieldDescription>
										Comma-separated names. Stored:{" "}
										{model.secret_names.join(", ")}.
									</FieldDescription>
								</Field>
							)}
							{error && <p className="text-sm text-destructive">{error}</p>}
							<div className="flex justify-end gap-2">
								<Link to="/admin/models">
									<Button type="button" variant="outline">
										Cancel
									</Button>
								</Link>
								<Button
									type="submit"
									disabled={busy || !name.trim() || !upstreamModel.trim()}
								>
									{busy ? "Saving…" : "Save model"}
								</Button>
							</div>
						</FieldGroup>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
