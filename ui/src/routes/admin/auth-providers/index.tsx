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
	useAdminAuthProviders,
	useDeleteAuthProvider,
} from "#/lib/admin-queries";

export const Route = createFileRoute("/admin/auth-providers/")({
	component: AuthProvidersIndex,
});

function AuthProvidersIndex() {
	const query = useAdminAuthProviders();
	const deleteMutation = useDeleteAuthProvider();
	const [deleting, setDeleting] = useState<string | null>(null);

	const remove = async (name: string) => {
		if (!window.confirm(`Delete provider "${name}"?`)) return;
		setDeleting(name);
		try {
			await deleteMutation.mutateAsync(name);
			toast.success(`Deleted ${name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Failed to delete provider.",
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
						Authentication providers
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						Reusable definitions shared by live MCP servers.
					</p>
				</div>
				<Link to="/admin/auth-providers/new" search={{ provider: undefined }}>
					<Button>
						<PlusIcon className="size-4" />
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
						<EmptyTitle>No providers yet</EmptyTitle>
						<EmptyDescription>
							Create one before linking authenticated servers.
						</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Link
							to="/admin/auth-providers/new"
							search={{ provider: undefined }}
						>
							<Button>
								<PlusIcon className="size-4" />
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
									{String(provider.auth.provider ?? "unknown")}
								</span>
							</CardHeader>
							<CardContent className="flex justify-end gap-2">
								<Link
									to="/admin/auth-providers/$providerName/edit"
									params={{ providerName: provider.name }}
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
									disabled={deleting === provider.name}
									onClick={() => remove(provider.name)}
								>
									<Trash2Icon className="size-3.5" />
									{deleting === provider.name ? "Deleting…" : "Delete"}
								</Button>
							</CardContent>
						</Card>
					))}
				</div>
			)}
		</div>
	);
}
