import { ActivityIcon, RefreshCwIcon } from "lucide-react";
import { Button } from "#/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";
import { REFRESH_INTERVAL_MS, useUsageSeriesAll } from "#/lib/queries";
import { useRefetchCountdown } from "#/lib/refresh";
import { cn } from "#/lib/utils";

function windowTotal(servers: { points: { total: number }[] }[]): number {
	return servers.reduce(
		(sum, server) =>
			sum + server.points.reduce((inner, point) => inner + point.total, 0),
		0,
	);
}

export function UsagePill() {
	const query = useUsageSeriesAll();
	const countdown = useRefetchCountdown(
		query.dataUpdatedAt,
		REFRESH_INTERVAL_MS,
	);
	const total = windowTotal(query.data?.servers ?? []);
	const perServer = (query.data?.servers ?? [])
		.map((server) => ({
			name: server.name,
			total: server.points.reduce((sum, point) => sum + point.total, 0),
		}))
		.sort((a, b) => b.total - a.total);

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="ghost"
					size="sm"
					aria-label="Gateway usage, last 24 hours"
					className="gap-1.5 font-mono text-xs text-muted-foreground hover:text-foreground"
				>
					<ActivityIcon className="size-4" />
					<span className="tabular-nums">{total}</span>
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end" className="min-w-56">
				<DropdownMenuGroup>
					<DropdownMenuLabel className="flex items-baseline justify-between gap-4">
						<span>Usage · 24h</span>
						<span className="font-mono text-base font-bold tabular-nums text-foreground">
							{total}
						</span>
					</DropdownMenuLabel>
					<DropdownMenuItem
						onClick={() => query.refetch()}
						disabled={query.isFetching}
					>
						<RefreshCwIcon
							className={cn("size-4", query.isFetching && "animate-spin")}
						/>
						Refresh
						<span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
							{countdown > 0 ? `${countdown}s` : "…"}
						</span>
					</DropdownMenuItem>
				</DropdownMenuGroup>
				{perServer.length > 0 && (
					<>
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							{perServer.map((server) => (
								<DropdownMenuItem key={server.name} disabled>
									<span className="min-w-0 truncate">{server.name}</span>
									<span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
										{server.total}
									</span>
								</DropdownMenuItem>
							))}
						</DropdownMenuGroup>
					</>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
