import { createFileRoute, Link } from "@tanstack/react-router";
import { BoxIcon, PencilIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ModelPricingSummary } from "#/components/model-pricing-summary";
import { Button } from "#/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "#/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { AdminApiError } from "#/lib/admin";
import { useAdminModels, useDeleteModel } from "#/lib/model-gateway-queries";

export const Route = createFileRoute("/admin/models/")({
	component: ModelsIndex,
});

function ModelsIndex() {
	const query = useAdminModels();
	const deleteMutation = useDeleteModel();
	const [deleting, setDeleting] = useState<string | null>(null);

	const remove = async (name: string) => {
		if (!window.confirm(`Delete model "${name}"?`)) return;
		setDeleting(name);
		try {
			await deleteMutation.mutateAsync(name);
			toast.success(`Deleted ${name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Could not delete the model.",
			);
		} finally {
			setDeleting(null);
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-8">
			<header className="flex items-center justify-between gap-4">
				<div>
					<h1 className="font-serif text-4xl font-bold tracking-tight">
						Models
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						OpenAI-compatible aliases backed by LiteLLM providers.
					</p>
				</div>
				<Link to="/admin/models/new">
					<Button>
						<PlusIcon className="size-4" />
						New model
					</Button>
				</Link>
			</header>
			{query.isLoading && (
				<p className="text-sm text-muted-foreground">Loading…</p>
			)}
			{query.isError && (
				<p className="text-sm text-destructive">
					{query.error instanceof Error
						? query.error.message
						: String(query.error)}
				</p>
			)}
			{query.isSuccess && query.data.length === 0 && (
				<Empty>
					<EmptyMedia variant="icon">
						<BoxIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>No models configured</EmptyTitle>
						<EmptyDescription>
							Create a provider first, then connect a public model name to it.
						</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Link to="/admin/models/new">
							<Button>
								<PlusIcon className="size-4" />
								Create model
							</Button>
						</Link>
					</EmptyContent>
				</Empty>
			)}
			{query.isSuccess && query.data.length > 0 && (
				<div className="grid gap-4 md:grid-cols-2">
					{query.data.map((model) => (
						<Card key={model.name}>
							<CardHeader>
								<CardTitle className="font-mono text-base">
									{model.name}
								</CardTitle>
							</CardHeader>
							<CardContent className="flex flex-col gap-4">
								<div className="flex flex-col gap-1 text-xs text-muted-foreground">
									<p>
										<span className="font-medium text-foreground">
											Provider:
										</span>{" "}
										<code>{model.provider}</code>
									</p>
									<p>
										<span className="font-medium text-foreground">
											Model ID:
										</span>{" "}
										<code>{model.model_id}</code>
									</p>
								</div>
								<ModelPricingSummary pricing={model.pricing} />
								<div className="flex justify-end gap-2">
									<Link
										to="/admin/models/$modelName/edit"
										params={{ modelName: model.name }}
									>
										<Button variant="outline" size="sm">
											<PencilIcon className="size-3.5" />
											Edit
										</Button>
									</Link>
									<Button
										variant="outline"
										size="sm"
										className="text-destructive"
										disabled={deleting === model.name}
										onClick={() => void remove(model.name)}
									>
										<Trash2Icon className="size-3.5" />
										{deleting === model.name ? "Deleting…" : "Delete"}
									</Button>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			)}
		</div>
	);
}
