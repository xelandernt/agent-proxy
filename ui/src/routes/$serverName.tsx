import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeftIcon, PencilIcon, ServerIcon } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { HarnessPanel } from "#/components/harness-panel";
import { ServerPageSkeleton } from "#/components/server-page-skeleton";
import { ServerUrlRow } from "#/components/server-url-row";
import { Badge } from "#/components/ui/badge";
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
import { UsagePanel } from "#/components/usage-panel";
import { AdminApiError } from "#/lib/admin";
import { useDeleteServer } from "#/lib/admin-queries";
import { checkAdminAuth } from "#/lib/auth";
import {
	HARNESSES,
	selectedHarnessId,
	setSelectedHarnessId,
	subscribeHarnessSelection,
} from "#/lib/harnesses";
import { useMcpServers } from "#/lib/queries";

export const Route = createFileRoute("/$serverName")({ component: ServerPage });

function ServerPage() {
	const { serverName } = Route.useParams();
	const [isAdmin, setIsAdmin] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const harnessId = useSyncExternalStore(
		subscribeHarnessSelection,
		selectedHarnessId,
		() => HARNESSES[0].id,
	);
	const serversQuery = useMcpServers();
	const deleteMutation = useDeleteServer();
	const server = serversQuery.data?.servers.find(
		(candidate) => candidate.name === serverName,
	);

	useEffect(() => {
		let active = true;
		checkAdminAuth().then((status) => {
			if (active) setIsAdmin(status === "authenticated");
		});
		return () => {
			active = false;
		};
	}, []);

	const remove = async () => {
		if (!window.confirm(`Delete server "${serverName}"?`)) return;
		setDeleting(true);
		try {
			await deleteMutation.mutateAsync(serverName);
			toast.success(`Deleted ${serverName}`);
			window.location.assign("/");
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Failed to delete server.",
			);
		} finally {
			setDeleting(false);
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-8">
			<Link
				to="/"
				className="inline-flex w-fit items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
			>
				<ArrowLeftIcon className="size-3" />
				All servers
			</Link>

			{serversQuery.isLoading && <ServerPageSkeleton />}
			{serversQuery.isError && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Server not found</EmptyTitle>
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
			{serversQuery.isSuccess && !server && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Server not found</EmptyTitle>
						<EmptyDescription>
							Unknown MCP server "{serverName}".
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			)}
			{serversQuery.isSuccess && server && (
				<>
					<header className="flex flex-col gap-3">
						<div className="flex items-start justify-between gap-4">
							<div className="flex items-center gap-3">
								<h1 className="font-serif text-4xl font-bold tracking-tight">
									{server.name}
								</h1>
								{server.auth === "oauth2" && (
									<Badge
										variant="outline"
										className="gap-1.5 px-2.5 py-1 text-xs font-medium text-muted-foreground"
									>
										<span className="size-1.5 rounded-full bg-lagoon" />
										OAuth
									</Badge>
								)}
							</div>
							{isAdmin && (
								<div className="flex items-center gap-2">
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
										className="text-destructive"
										disabled={deleting}
										onClick={() => void remove()}
									>
										Delete
									</Button>
								</div>
							)}
						</div>
						<p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
							{server.description || "No description provided."}
						</p>
						<ServerUrlRow url={server.url} />
					</header>
					<UsagePanel serverName={server.name} />
					<Card>
						<CardHeader>
							<CardTitle className="font-sans text-base font-semibold">
								Connect
							</CardTitle>
						</CardHeader>
						<CardContent>
							<HarnessPanel
								server={server}
								harnessId={harnessId}
								onHarnessIdChange={setSelectedHarnessId}
							/>
						</CardContent>
					</Card>
				</>
			)}
		</div>
	);
}
