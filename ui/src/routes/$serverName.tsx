import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeftIcon, ServerIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

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
import { Skeleton } from "#/components/ui/skeleton";
import { UsagePanel } from "#/components/usage-panel";
import { CopyButton, useCopy } from "#/lib/copy";
import { fetchMcpServers, type McpServerListing } from "#/lib/mcp";
import { cn } from "#/lib/utils";

export const Route = createFileRoute("/$serverName")({ component: ServerPage });

type LoadState =
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; server: McpServerListing };

function ServerPage() {
	const { serverName } = Route.useParams();
	const [state, setState] = useState<LoadState>({ status: "loading" });

	const load = useCallback(() => {
		const controller = new AbortController();
		setState({ status: "loading" });
		fetchMcpServers(controller.signal)
			.then((document) => {
				const server = document.servers.find(
					(candidate) => candidate.name === serverName,
				);
				if (!server) {
					setState({
						status: "error",
						message: `Unknown MCP server "${serverName}".`,
					});
					return;
				}
				setState({ status: "ready", server });
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				setState({
					status: "error",
					message: error instanceof Error ? error.message : String(error),
				});
			});
		return controller;
	}, [serverName]);

	useEffect(() => {
		const controller = load();
		return () => controller.abort();
	}, [load]);

	return (
		<div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-8">
			<Link
				to="/"
				className="inline-flex w-fit items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
			>
				<ArrowLeftIcon className="size-3" />
				All servers
			</Link>

			{state.status === "loading" && <ServerPageSkeleton />}
			{state.status === "error" && (
				<Empty>
					<EmptyMedia variant="icon">
						<ServerIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Server not found</EmptyTitle>
						<EmptyDescription>{state.message}</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Button variant="outline" onClick={() => load()}>
							Retry
						</Button>
					</EmptyContent>
				</Empty>
			)}
			{state.status === "ready" && (
				<>
					<header className="flex flex-col gap-3">
						<div className="flex items-center gap-3">
							<h1 className="font-serif text-4xl font-bold tracking-tight">
								{state.server.name}
							</h1>
							{state.server.auth === "oauth2" && (
								<Badge
									variant="outline"
									className="gap-1.5 px-2.5 py-1 text-xs font-medium text-muted-foreground"
								>
									<span className="size-1.5 rounded-full bg-lagoon" />
									OAuth
								</Badge>
							)}
						</div>
						<p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
							{state.server.description || "No description provided."}
						</p>
						<ServerUrlRow url={state.server.url} />
					</header>
					<UsagePanel serverName={state.server.name} />
				</>
			)}
		</div>
	);
}

function ServerUrlRow({ url }: { url: string }) {
	const { copied, copy } = useCopy(url, "URL copied", url);

	return (
		<div className="flex w-full max-w-2xl items-center justify-between gap-3 rounded-lg border bg-muted/40 py-2 pl-3 pr-2">
			<span
				className={cn(
					"min-w-0 truncate font-mono text-sm text-muted-foreground transition-shadow duration-300",
					copied && "copy-highlight",
				)}
			>
				{url}
			</span>
			<CopyButton copied={copied} onClick={copy} label="Copy URL" />
		</div>
	);
}

function ServerPageSkeleton() {
	return (
		<div className="flex flex-col gap-8">
			<Skeleton className="h-10 w-1/3" />
			<Skeleton className="h-4 w-2/3" />
			<Card>
				<CardHeader>
					<CardTitle className="font-sans text-base font-semibold">
						Usage
					</CardTitle>
				</CardHeader>
				<CardContent className="flex flex-col gap-4">
					<Skeleton className="h-8 w-64" />
					<Skeleton className="h-10 w-28" />
					<Skeleton className="h-40 w-full" />
				</CardContent>
			</Card>
		</div>
	);
}
