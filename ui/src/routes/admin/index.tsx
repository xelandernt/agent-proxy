import { createFileRoute, Link } from "@tanstack/react-router";
import {
	ArrowLeftIcon,
	BookOpenIcon,
	PencilIcon,
	PlusIcon,
	ServerIcon,
	Trash2Icon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "#/components/ui/badge";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardFooter,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Skeleton } from "#/components/ui/skeleton";
import { AdminApiError } from "#/lib/admin";
import { useAdminServers, useDeleteServer } from "#/lib/admin-queries";

export const Route = createFileRoute("/admin/")({ component: AdminIndex });

function providerName(server: { auth: unknown }): string {
	const auth = server.auth as { provider?: unknown } | null;
	return typeof auth?.provider === "string" ? auth.provider : "unknown";
}

function AdminIndex() {
	const [deleting, setDeleting] = useState<string | null>(null);
	const serversQuery = useAdminServers();
	const deleteMutation = useDeleteServer();

	const remove = async (name: string) => {
		if (!window.confirm(`Delete server "${name}"?`)) return;
		setDeleting(name);
		try {
			await deleteMutation.mutateAsync(name);
			toast.success(`Deleted ${name}`);
		} catch (error) {
			if (error instanceof AdminApiError) {
				toast.error(error.message);
			} else {
				toast.error("Failed to delete server.");
			}
		} finally {
			setDeleting(null);
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-8">
			<div className="flex items-center justify-between">
				<Link
					to="/"
					className="inline-flex w-fit items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					<ArrowLeftIcon className="size-3" />
					All servers
				</Link>
				<Link
					to="/docs"
					className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					<BookOpenIcon className="size-3.5" />
					Provider guides
				</Link>
			</div>
			<header className="flex items-start justify-between gap-4">
				<div className="flex flex-col gap-3">
					<h1 className="bg-gradient-to-b from-foreground to-foreground/55 bg-clip-text font-serif text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
						Manage servers
					</h1>
				</div>
				<Link to="/admin/new">
					<Button>
						<PlusIcon className="size-4" />
						New server
					</Button>
				</Link>
			</header>

			{serversQuery.isLoading && <ServerListSkeleton />}
			{serversQuery.isError && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Could not load servers</EmptyTitle>
						<EmptyDescription>
							{serversQuery.error instanceof Error
								? serversQuery.error.message
								: String(serversQuery.error)}
						</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Button variant="outline" onClick={() => serversQuery.refetch()}>
							Retry
						</Button>
					</EmptyContent>
				</Empty>
			)}
			{serversQuery.isSuccess && serversQuery.data.length === 0 && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>No servers yet</EmptyTitle>
						<EmptyDescription>
							Create your first server to expose an MCP endpoint.
						</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Link to="/admin/new">
							<Button>
								<PlusIcon className="size-4" />
								New server
							</Button>
						</Link>
					</EmptyContent>
				</Empty>
			)}
			{serversQuery.isSuccess && serversQuery.data.length > 0 && (
				<div className="flex flex-col gap-4">
					{serversQuery.data.map((server) => (
						<Card key={server.name}>
							<CardHeader className="flex-row items-center justify-between">
								<CardTitle className="truncate font-sans text-base font-semibold">
									{server.name}
								</CardTitle>
								<Badge variant="outline" className="font-mono text-xs">
									{providerName(server)}
								</Badge>
							</CardHeader>
							<CardContent className="flex flex-col gap-2">
								{server.description && (
									<p className="text-sm text-muted-foreground">
										{server.description}
									</p>
								)}
								<p className="truncate font-mono text-xs text-muted-foreground">
									{server.upstream_url}
								</p>
							</CardContent>
							<CardFooter className="justify-end gap-2">
								<Link to="/$serverName" params={{ serverName: server.name }}>
									<Button variant="ghost" size="sm">
										View
									</Button>
								</Link>
								<Link
									to="/admin/$serverName/edit"
									params={{ serverName: server.name }}
								>
									<Button variant="outline" size="sm">
										<PencilIcon className="size-3.5" />
										Edit
									</Button>
								</Link>
								<Button
									variant="outline"
									size="sm"
									disabled={deleting === server.name}
									onClick={() => remove(server.name)}
									className="text-destructive"
								>
									<Trash2Icon className="size-3.5" />
									{deleting === server.name ? "Deleting…" : "Delete"}
								</Button>
							</CardFooter>
						</Card>
					))}
				</div>
			)}
		</div>
	);
}

function ServerListSkeleton() {
	return (
		<div className="flex flex-col gap-4">
			{[0, 1, 2].map((index) => (
				<Card key={index} className="flex flex-col gap-4 p-6">
					<Skeleton className="h-5 w-1/3" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-2/3" />
					<Skeleton className="h-8 w-32" />
				</Card>
			))}
		</div>
	);
}
