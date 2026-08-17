import { createFileRoute, Link } from "@tanstack/react-router";
import { PlusIcon, ServerIcon } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { ServerCard } from "#/components/server-card";
import { ServerGridSkeleton } from "#/components/server-grid-skeleton";
import { Button } from "#/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { AdminApiError } from "#/lib/admin";
import { useDeleteServer } from "#/lib/admin-queries";
import { checkAdminAuth } from "#/lib/auth";
import {
	HARNESSES,
	selectedHarnessId,
	setSelectedHarnessId,
	subscribeHarnessSelection,
} from "#/lib/harnesses";
import { useMcpServers, useUsageSeriesAll } from "#/lib/queries";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
	const harnessId = useSyncExternalStore(
		subscribeHarnessSelection,
		selectedHarnessId,
		() => HARNESSES[0].id,
	);
	const serversQuery = useMcpServers();
	const seriesQuery = useUsageSeriesAll();
	const deleteMutation = useDeleteServer();
	const [isAdmin, setIsAdmin] = useState(false);
	const [deleting, setDeleting] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		checkAdminAuth().then((status) => {
			if (active) setIsAdmin(status === "authenticated");
		});
		return () => {
			active = false;
		};
	}, []);

	const remove = async (name: string) => {
		if (!window.confirm(`Delete server "${name}"?`)) return;
		setDeleting(name);
		try {
			await deleteMutation.mutateAsync(name);
			toast.success(`Deleted ${name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Failed to delete server.",
			);
		} finally {
			setDeleting(null);
		}
	};

	const byServer = new Map(
		(seriesQuery.data?.servers ?? []).map((entry) => [
			entry.name,
			entry.points,
		]),
	);

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-10 p-8">
			<header className="flex items-start justify-between gap-4">
				<div className="flex flex-col gap-3">
					<h1 className="bg-gradient-to-b from-foreground to-foreground/55 bg-clip-text font-serif text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
						MCP Servers
					</h1>
				</div>
				{isAdmin && (
					<Link to="/admin/new">
						<Button>
							<PlusIcon className="size-4" />
							New server
						</Button>
					</Link>
				)}
			</header>

			{serversQuery.isLoading && <ServerGridSkeleton />}
			{serversQuery.isError && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Could not load MCP servers</EmptyTitle>
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
			{serversQuery.isSuccess && serversQuery.data.servers.length === 0 && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>No MCP servers configured</EmptyTitle>
						<EmptyDescription>
							Add a server after{" "}
							<Link
								to="/admin"
								className="underline underline-offset-4 hover:text-foreground"
							>
								signing in
							</Link>
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			)}
			{serversQuery.isSuccess && serversQuery.data.servers.length > 0 && (
				<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
					{serversQuery.data.servers.map((server) => (
						<ServerCard
							key={server.name}
							server={server}
							harnessId={harnessId}
							onHarnessIdChange={setSelectedHarnessId}
							sparkline={byServer.get(server.name)}
							management={
								isAdmin
									? {
											deleting: deleting === server.name,
											onDelete: () => void remove(server.name),
										}
									: undefined
							}
						/>
					))}
				</div>
			)}
		</div>
	);
}
