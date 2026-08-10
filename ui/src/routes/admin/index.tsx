import { createFileRoute, Link } from "@tanstack/react-router";
import { PencilIcon, PlusIcon, ServerIcon, Trash2Icon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
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
import {
	AdminApiError,
	type AdminServer,
	deleteAdminServer,
	listAdminServers,
} from "#/lib/admin";
import { getAdminToken } from "#/lib/auth";

export const Route = createFileRoute("/admin/")({ component: AdminIndex });

type LoadState =
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; servers: AdminServer[] };

function providerName(server: AdminServer): string {
	const auth = server.auth;
	return typeof auth.provider === "string" ? auth.provider : "unknown";
}

function AdminIndex() {
	const [state, setState] = useState<LoadState>({ status: "loading" });
	const [deleting, setDeleting] = useState<string | null>(null);

	const load = useCallback(() => {
		const token = getAdminToken();
		if (!token) {
			setState({ status: "error", message: "Not authenticated." });
			return;
		}
		setState({ status: "loading" });
		listAdminServers(token)
			.then((servers) => setState({ status: "ready", servers }))
			.catch((error: unknown) => {
				setState({
					status: "error",
					message: error instanceof Error ? error.message : String(error),
				});
			});
	}, []);

	useEffect(() => {
		load();
	}, [load]);

	const remove = async (server: AdminServer) => {
		const token = getAdminToken();
		if (!token) return;
		if (!window.confirm(`Delete server "${server.name}"?`)) return;
		setDeleting(server.name);
		try {
			await deleteAdminServer(token, server.name);
			toast.success(`Deleted ${server.name}`);
			load();
		} catch (error) {
			setDeleting(null);
			if (error instanceof AdminApiError) {
				toast.error(error.message);
			} else {
				toast.error("Failed to delete server.");
			}
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-8">
			<header className="flex items-start justify-between gap-4">
				<div className="flex flex-col gap-3">
					<p className="font-mono text-xs font-medium uppercase tracking-[0.2em] text-kicker">
						Agent Gateway
					</p>
					<h1 className="bg-gradient-to-b from-foreground to-foreground/55 bg-clip-text font-serif text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
						Manage servers
					</h1>
					<p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
						Servers are applied to the running gateway immediately — no restart
						required.
					</p>
				</div>
				<Link to="/admin/new">
					<Button>
						<PlusIcon className="size-4" />
						New server
					</Button>
				</Link>
			</header>

			{state.status === "loading" && <ServerListSkeleton />}
			{state.status === "error" && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Could not load servers</EmptyTitle>
						<EmptyDescription>{state.message}</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Button variant="outline" onClick={load}>
							Retry
						</Button>
					</EmptyContent>
				</Empty>
			)}
			{state.status === "ready" && state.servers.length === 0 && (
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
			{state.status === "ready" && state.servers.length > 0 && (
				<div className="flex flex-col gap-4">
					{state.servers.map((server) => (
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
									onClick={() => remove(server)}
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
