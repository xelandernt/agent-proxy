import { createFileRoute, Link } from "@tanstack/react-router";
import { PencilIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "#/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "#/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyTitle,
} from "#/components/ui/empty";
import { AdminApiError } from "#/lib/admin";
import {
	useAdminModelProviders,
	useDeleteModelProvider,
} from "#/lib/model-gateway-queries";

export const Route = createFileRoute("/admin/model-providers/")({
	component: ModelProvidersIndex,
});

function ModelProvidersIndex() {
	const query = useAdminModelProviders();
	const deleteMutation = useDeleteModelProvider();
	const [deleting, setDeleting] = useState<string | null>(null);
	const remove = async (name: string) => {
		if (!window.confirm(`Delete model provider "${name}"?`)) return;
		setDeleting(name);
		try {
			await deleteMutation.mutateAsync(name);
			toast.success(`Deleted ${name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Could not delete the provider.",
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
						Model providers
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						Reusable inference connections selected by models.
					</p>
				</div>
				<Link to="/admin/model-providers/new">
					<Button>
						<PlusIcon data-icon="inline-start" />
						New provider
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
					<EmptyHeader>
						<EmptyTitle>No model providers yet</EmptyTitle>
						<EmptyDescription>
							Create a provider before configuring a model.
						</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Link to="/admin/model-providers/new">
							<Button>
								<PlusIcon data-icon="inline-start" />
								Create provider
							</Button>
						</Link>
					</EmptyContent>
				</Empty>
			)}
			{query.isSuccess && query.data.length > 0 && (
				<div className="flex flex-col gap-4">
					{query.data.map((provider) => (
						<Card key={provider.name}>
							<CardHeader className="flex-row items-center justify-between">
								<CardTitle>{provider.name}</CardTitle>
								<span className="font-mono text-xs text-muted-foreground">
									{String(provider.config.provider ?? "unknown")}
								</span>
							</CardHeader>
							<CardContent className="flex items-center justify-between gap-4">
								<p className="text-xs text-muted-foreground">
									Credentials:{" "}
									{provider.credential_names.length
										? provider.credential_names.join(", ")
										: "default AWS chain"}
								</p>
								<div className="flex gap-2">
									<Link
										to="/admin/model-providers/$providerName/edit"
										params={{ providerName: provider.name }}
									>
										<Button variant="outline" size="sm">
											<PencilIcon data-icon="inline-start" />
											Edit
										</Button>
									</Link>
									<Button
										variant="outline"
										size="sm"
										className="text-destructive"
										disabled={deleting === provider.name}
										onClick={() => void remove(provider.name)}
									>
										<Trash2Icon data-icon="inline-start" />
										{deleting === provider.name ? "Deleting…" : "Delete"}
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
