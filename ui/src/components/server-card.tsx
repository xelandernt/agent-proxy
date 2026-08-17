import { Link } from "@tanstack/react-router";
import { PencilIcon, Trash2Icon } from "lucide-react";
import { HarnessPanel } from "#/components/harness-panel";
import { Sparkline } from "#/components/sparkline";
import { Badge } from "#/components/ui/badge";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardFooter,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import { CopyButton, useCopy } from "#/lib/copy";
import type { McpServerListing, SeriesPoint } from "#/lib/mcp";
import { cn } from "#/lib/utils";

export function ServerCard({
	server,
	harnessId,
	onHarnessIdChange,
	sparkline,
	management,
}: {
	server: McpServerListing;
	harnessId: string;
	onHarnessIdChange: (harnessId: string) => void;
	sparkline?: SeriesPoint[];
	management?: {
		deleting: boolean;
		onDelete: () => void;
	};
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
					{sparkline && (
						<div className="flex flex-col gap-1">
							<p className="font-mono text-[10px] uppercase tracking-[0.2em] text-kicker">
								Activity · 24h
							</p>
							<Sparkline points={sparkline} />
						</div>
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
			<CardFooter className="flex-col items-stretch gap-3">
				<CopyUrlRow server={server} />
				{management && (
					<div className="flex justify-end gap-2">
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
							disabled={management.deleting}
							onClick={management.onDelete}
							className="text-destructive"
						>
							<Trash2Icon className="size-3.5" />
							{management.deleting ? "Deleting…" : "Delete"}
						</Button>
					</div>
				)}
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
