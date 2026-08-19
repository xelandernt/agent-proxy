import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeftIcon, BoxIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import type {
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
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "#/components/ui/select";
import { AdminApiError } from "#/lib/admin";
import {
	useAdminModelProviders,
	useCreateModel,
	useUpdateModel,
} from "#/lib/model-gateway-queries";

export function ModelForm({ model }: { model?: ModelDeploymentView }) {
	const navigate = useNavigate();
	const providers = useAdminModelProviders();
	const createMutation = useCreateModel();
	const updateMutation = useUpdateModel();
	const [name, setName] = useState(model?.name ?? "");
	const [provider, setProvider] = useState(model?.provider ?? "");
	const [modelId, setModelId] = useState(model?.model_id ?? "");
	const [error, setError] = useState<string | null>(null);
	const submitting = useRef(false);
	const busy = createMutation.isPending || updateMutation.isPending;

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		if (submitting.current) return;
		if (!provider) {
			setError("Select a provider.");
			return;
		}
		submitting.current = true;
		setError(null);
		try {
			if (model) {
				const payload: ModelDeploymentUpdate = {
					provider,
					model_id: modelId.trim(),
				};
				await updateMutation.mutateAsync({ name: model.name, payload });
				toast.success(`Updated ${model.name}`);
			} else {
				const payload: ModelDeploymentCreate = {
					name: name.trim(),
					provider,
					model_id: modelId.trim(),
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
					<ArrowLeftIcon data-icon="inline-start" />
					Back to models
				</Button>
			</Link>
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<BoxIcon />
						{model ? `Edit ${model.name}` : "New model"}
					</CardTitle>
					<CardDescription>
						Create a public model name backed by a configured inference
						provider.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form onSubmit={submit}>
						<FieldGroup>
							<Field>
								<FieldLabel htmlFor="model-name">Model name</FieldLabel>
								<Input
									id="model-name"
									value={name}
									onChange={(event) => setName(event.target.value)}
									placeholder="support-agent"
									disabled={Boolean(model)}
									required
								/>
								<FieldDescription>
									The name clients send to the OpenAI-compatible API.
								</FieldDescription>
							</Field>
							<Field data-invalid={Boolean(error && !provider)}>
								<FieldLabel htmlFor="model-provider">Provider</FieldLabel>
								<Select value={provider} onValueChange={setProvider}>
									<SelectTrigger
										id="model-provider"
										aria-invalid={Boolean(error && !provider)}
									>
										<SelectValue placeholder="Select a provider" />
									</SelectTrigger>
									<SelectContent>
										<SelectGroup>
											{providers.data?.map((entry) => (
												<SelectItem key={entry.name} value={entry.name}>
													{entry.name}
												</SelectItem>
											))}
										</SelectGroup>
									</SelectContent>
								</Select>
								<FieldDescription>
									{providers.data?.length === 0 ? (
										<>
											No model providers exist. Create one under{" "}
											<Link to="/admin/model-providers/new">
												Models → Providers
											</Link>
											.
										</>
									) : (
										"Credentials and endpoint settings are managed on the provider."
									)}
								</FieldDescription>
							</Field>
							<Field>
								<FieldLabel htmlFor="model-id">Provider model ID</FieldLabel>
								<Input
									id="model-id"
									value={modelId}
									onChange={(event) => setModelId(event.target.value)}
									placeholder="gpt-5"
									required
								/>
								<FieldDescription>
									Enter only the provider-side ID; the gateway applies the
									LiteLLM provider prefix.
								</FieldDescription>
							</Field>
							{error && <p className="text-sm text-destructive">{error}</p>}
							<div className="flex justify-end gap-2">
								<Link to="/admin/models">
									<Button type="button" variant="outline">
										Cancel
									</Button>
								</Link>
								<Button
									type="submit"
									disabled={
										busy || !name.trim() || !modelId.trim() || !provider
									}
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
