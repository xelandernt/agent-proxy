import { createFileRoute, Link } from "@tanstack/react-router";
import { ServerIcon } from "lucide-react";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { HarnessPanel } from "#/components/harness-panel";
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
import { CopyButton, useCopy } from "#/lib/copy";
import {
	HARNESSES,
	selectedHarnessId,
	setSelectedHarnessId,
	subscribeHarnessSelection,
} from "#/lib/harnesses";
import { fetchMcpServers, type McpServerListing } from "#/lib/mcp";
import { cn } from "#/lib/utils";

export const Route = createFileRoute("/")({ component: Home });

type LoadState =
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; servers: McpServerListing[] };

function Home() {
	const [state, setState] = useState<LoadState>({ status: "loading" });
	const harnessId = useSyncExternalStore(
		subscribeHarnessSelection,
		selectedHarnessId,
		() => HARNESSES[0].id,
	);

	const load = useCallback(() => {
		const controller = new AbortController();
		setState({ status: "loading" });
		fetchMcpServers(controller.signal)
			.then((document) =>
				setState({ status: "ready", servers: document.servers }),
			)
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				setState({
					status: "error",
					message: error instanceof Error ? error.message : String(error),
				});
			});
		return controller;
	}, []);

	useEffect(() => {
		const controller = load();
		return () => controller.abort();
	}, [load]);

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-10 p-8">
			<header className="flex items-start justify-between gap-4">
				<div className="flex flex-col gap-3">
					<p className="font-mono text-xs font-medium uppercase tracking-[0.2em] text-kicker">
						Agent Gateway
					</p>
					<h1 className="bg-gradient-to-b from-foreground to-foreground/55 bg-clip-text font-serif text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
						MCP Servers
					</h1>
					<p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
						Discover the Model Context Protocol servers exposed by this gateway,
						copy their endpoints, and connect them to your AI client.
					</p>
				</div>
			</header>

			{state.status === "loading" && <ServerGridSkeleton />}
			{state.status === "error" && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Could not load MCP servers</EmptyTitle>
						<EmptyDescription>{state.message}</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Button variant="outline" onClick={() => load()}>
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
						<EmptyTitle>No MCP servers configured</EmptyTitle>
						<EmptyDescription>
							Add a server to your gateway config (for example{" "}
							<code className="font-mono">resources/config.yaml</code>) and
							restart the gateway.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			)}
			{state.status === "ready" && state.servers.length > 0 && (
				<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
					{state.servers.map((server) => (
						<ServerCard
							key={server.name}
							server={server}
							harnessId={harnessId}
							onHarnessIdChange={setSelectedHarnessId}
						/>
					))}
				</div>
			)}
		</div>
	);
}

function ServerCard({
	server,
	harnessId,
	onHarnessIdChange,
}: {
	server: McpServerListing;
	harnessId: string;
	onHarnessIdChange: (harnessId: string) => void;
}) {
	return (
		<Card className="flex h-full flex-col transition-colors hover:border-lagoon/40">
			<Link
				to="/$serverName"
				params={{ serverName: server.name }}
				className="flex min-w-0 flex-col"
			>
				<CardHeader>
					<div className="flex items-center justify-between gap-2">
						<CardTitle className="truncate font-sans text-base font-semibold">
							{server.name}
						</CardTitle>
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
				</CardHeader>
				<CardContent className="flex flex-1 flex-col gap-4">
					{server.description ? (
						<p className="text-sm leading-relaxed text-muted-foreground">
							{server.description}
						</p>
					) : (
						<p className="text-sm text-muted-foreground">
							No description provided.
						</p>
					)}
				</CardContent>
			</Link>
			<CardContent className="flex flex-col gap-4 pt-0">
				<HarnessPanel
					server={server}
					harnessId={harnessId}
					onHarnessIdChange={onHarnessIdChange}
				/>
			</CardContent>
			<CardFooter>
				<CopyUrlRow server={server} />
			</CardFooter>
		</Card>
	);
}

function CopyUrlRow({ server }: { server: McpServerListing }) {
	const { copied, copy } = useCopy(server.url, "URL copied", server.url);

	return (
		<div className="flex w-full items-center justify-between gap-2">
			<span
				className={cn(
					"min-w-0 truncate rounded px-1 py-0.5 font-mono text-xs text-muted-foreground transition-shadow duration-300",
					copied && "copy-highlight",
				)}
			>
				{server.url}
			</span>
			<CopyButton copied={copied} onClick={copy} label="Copy URL" iconOnly />
		</div>
	);
}

function ServerGridSkeleton() {
	return (
		<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
			{[0, 1, 2].map((index) => (
				<Card key={index} className="flex flex-col gap-4 p-6">
					<Skeleton className="h-5 w-1/3" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-2/3" />
					<Skeleton className="h-8 w-24" />
				</Card>
			))}
		</div>
	);
}
