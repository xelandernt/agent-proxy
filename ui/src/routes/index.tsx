import { createFileRoute, Link } from "@tanstack/react-router";
import { ServerCogIcon, ServerIcon } from "lucide-react";
import { useSyncExternalStore } from "react";
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
				<Link to="/admin">
					<Button variant="ghost">
						<ServerCogIcon className="size-3.5" />
						Manage
					</Button>
				</Link>
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
							Add a server through the{" "}
							<Link
								to="/admin"
								className="underline underline-offset-4 hover:text-foreground"
							>
								admin interface
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
						/>
					))}
				</div>
			)}
		</div>
	);
}
