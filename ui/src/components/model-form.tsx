import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeftIcon, BoxIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import type {
	ModelDeploymentCreate,
	ModelDeploymentUpdate,
	ModelDeploymentView,
	ModelPricing,
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
	FieldError,
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
import { AdminApiError } from "#/lib/admin";
import {
	useAdminModelProviders,
	useCreateModel,
	useUpdateModel,
} from "#/lib/model-gateway-queries";
import { customPricingFromInputs } from "#/lib/model-pricing";

export function ModelForm({ model }: { model?: ModelDeploymentView }) {
	const navigate = useNavigate();
	const providers = useAdminModelProviders();
	const createMutation = useCreateModel();
	const updateMutation = useUpdateModel();
	const [name, setName] = useState(model?.name ?? "");
	const [provider, setProvider] = useState(model?.provider ?? "");
	const [modelId, setModelId] = useState(model?.model_id ?? "");
	const customPricing = model?.pricing?.is_custom ? model.pricing : undefined;
	const [inputPrice, setInputPrice] = useState(
		customPricing?.input_usd_per_million_tokens ?? "",
	);
	const [cachedInputPrice, setCachedInputPrice] = useState(
		customPricing?.cached_input_usd_per_million_tokens ?? "",
	);
	const [outputPrice, setOutputPrice] = useState(
		customPricing?.output_usd_per_million_tokens ?? "",
	);
	const [pricingError, setPricingError] = useState<string | null>(null);
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
		let pricing: ModelPricing | null;
		try {
			pricing = customPricingFromInputs({
				input: inputPrice,
				cachedInput: cachedInputPrice,
				output: outputPrice,
			});
			setPricingError(null);
		} catch (caught) {
			setPricingError(
				caught instanceof Error ? caught.message : "Invalid custom pricing.",
			);
			return;
		}
		submitting.current = true;
		setError(null);
		try {
			if (model) {
				const payload: ModelDeploymentUpdate = {
					provider,
					model_id: modelId.trim(),
					pricing,
				};
				await updateMutation.mutateAsync({ name: model.name, payload });
				toast.success(`Updated ${model.name}`);
			} else {
				const payload: ModelDeploymentCreate = {
					name: name.trim(),
					provider,
					model_id: modelId.trim(),
					pricing,
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
						provider, with optional custom token pricing.
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
							<FieldSet>
								<FieldLegend>Custom pricing</FieldLegend>
								<FieldDescription>
									USD per one million tokens. Enter all three prices, or leave
									all three blank to use automatic pricing when available.
								</FieldDescription>
								<FieldGroup className="gap-4 md:grid md:grid-cols-3">
									<Field data-invalid={Boolean(pricingError)}>
										<FieldLabel htmlFor="model-input-price">Input</FieldLabel>
										<Input
											id="model-input-price"
											type="number"
											min="0"
											step="any"
											value={inputPrice}
											onChange={(event) => setInputPrice(event.target.value)}
											placeholder="2.50"
											aria-invalid={Boolean(pricingError)}
										/>
									</Field>
									<Field data-invalid={Boolean(pricingError)}>
										<FieldLabel htmlFor="model-cached-input-price">
											Cached input
										</FieldLabel>
										<Input
											id="model-cached-input-price"
											type="number"
											min="0"
											step="any"
											value={cachedInputPrice}
											onChange={(event) =>
												setCachedInputPrice(event.target.value)
											}
											placeholder="0.25"
											aria-invalid={Boolean(pricingError)}
										/>
									</Field>
									<Field data-invalid={Boolean(pricingError)}>
										<FieldLabel htmlFor="model-output-price">Output</FieldLabel>
										<Input
											id="model-output-price"
											type="number"
											min="0"
											step="any"
											value={outputPrice}
											onChange={(event) => setOutputPrice(event.target.value)}
											placeholder="10.00"
											aria-invalid={Boolean(pricingError)}
										/>
									</Field>
								</FieldGroup>
								{pricingError && <FieldError>{pricingError}</FieldError>}
							</FieldSet>
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
