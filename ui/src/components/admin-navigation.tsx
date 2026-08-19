import { Link, useLocation } from "@tanstack/react-router";
import {
	BotIcon,
	ChartNoAxesCombinedIcon,
	CloudIcon,
	KeyRoundIcon,
	LockIcon,
	LockKeyholeIcon,
	LockOpenIcon,
	ServerIcon,
	UserRoundIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AgentGatewayLogo } from "#/components/agent-gateway-logo";
import { Button } from "#/components/ui/button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "#/components/ui/tooltip";
import { checkAdminAuth } from "#/lib/auth";
import { cn } from "#/lib/utils";

export function AdminNavigation() {
	const location = useLocation();
	const [authenticated, setAuthenticated] = useState(false);
	const [sidebarHovered, setSidebarHovered] = useState(false);
	const [sidebarLocked, setSidebarLocked] = useState(false);
	const isCallbackPath = location.pathname.endsWith("/admin/callback");
	const mcpAuthActive =
		location.pathname.startsWith("/admin/auth-providers") ||
		location.pathname.startsWith("/docs");
	const modelProvidersActive = location.pathname.startsWith(
		"/admin/model-providers",
	);
	const modelsActive =
		location.pathname.startsWith("/admin/models") ||
		location.pathname.startsWith("/account/models");
	const accountActive =
		location.pathname === "/account" || location.pathname === "/account/";
	const adminUsageActive = location.pathname.startsWith("/admin/usage");
	const accountUsageActive = location.pathname.startsWith("/account/usage");
	const serversActive =
		!mcpAuthActive &&
		!modelProvidersActive &&
		!modelsActive &&
		!accountActive &&
		!adminUsageActive &&
		!accountUsageActive &&
		location.pathname !== "/admin/callback";
	const expanded = sidebarHovered || sidebarLocked;

	const refreshAuth = useCallback(async () => {
		const status = await checkAdminAuth();
		setAuthenticated(status === "authenticated");
	}, []);

	useEffect(() => {
		if (location.pathname.endsWith("/admin/callback")) return;
		void refreshAuth();
	}, [location.pathname, refreshAuth]);

	if (isCallbackPath) return null;

	const navItemClass =
		"flex h-10 items-center gap-3 rounded-md px-2.5 font-mono text-sm transition-colors";
	const labelClass = cn(
		"overflow-hidden whitespace-nowrap transition-[max-width,opacity] duration-200",
		expanded ? "max-w-32 opacity-100" : "max-w-0 opacity-0",
	);

	const handleMouseEnter = () => {
		setSidebarHovered(true);
		if (!authenticated) void refreshAuth();
	};

	return (
		<TooltipProvider>
			<aside
				className={cn(
					"fixed inset-y-0 left-0 z-50 flex flex-col border-r bg-background/95 p-3 shadow-sm backdrop-blur transition-[width] duration-200",
					expanded ? "w-52" : "w-16",
				)}
				onMouseEnter={handleMouseEnter}
				onMouseLeave={() => setSidebarHovered(false)}
				onFocus={() => setSidebarHovered(true)}
				onBlur={(event) => {
					if (!event.currentTarget.contains(event.relatedTarget)) {
						setSidebarHovered(false);
					}
				}}
				aria-label="Application navigation"
			>
				<Link
					to="/"
					aria-label="Agent Gateway home"
					className="flex h-12 min-w-0 items-center px-1 no-underline"
				>
					<AgentGatewayLogo expanded={expanded} />
				</Link>

				<nav className="flex flex-col gap-1" aria-label="Sections">
					{authenticated && (
						<Tooltip>
							<TooltipTrigger asChild>
								<Link
									to="/admin/usage"
									className={cn(
										navItemClass,
										adminUsageActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={adminUsageActive ? "page" : undefined}
									aria-label="Model usage"
								>
									<ChartNoAxesCombinedIcon className="size-4 shrink-0" />
									<span className={labelClass}>Usage</span>
								</Link>
							</TooltipTrigger>
							<TooltipContent side="right">Model usage</TooltipContent>
						</Tooltip>
					)}
					{expanded && authenticated && (
						<p className="mt-3 px-2.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
							MCP
						</p>
					)}

					<Tooltip>
						<TooltipTrigger asChild>
							{authenticated ? (
								<Link
									to="/admin/auth-providers"
									search={{ provider: undefined }}
									className={cn(
										navItemClass,
										mcpAuthActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={mcpAuthActive ? "page" : undefined}
									aria-label="MCP authentication"
								>
									<KeyRoundIcon className="size-4 shrink-0" />
									<span className={labelClass}>Auth</span>
								</Link>
							) : (
								<span
									className={cn(
										navItemClass,
										"cursor-not-allowed text-muted-foreground/50",
									)}
								>
									<LockKeyholeIcon className="size-4 shrink-0" />
									<span className={labelClass}>Auth</span>
								</span>
							)}
						</TooltipTrigger>
						<TooltipContent side="right">MCP authentication</TooltipContent>
					</Tooltip>

					<Tooltip>
						<TooltipTrigger asChild>
							{authenticated ? (
								<Link
									to="/"
									className={cn(
										navItemClass,
										serversActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={serversActive ? "page" : undefined}
									aria-label="MCP servers"
								>
									<ServerIcon className="size-4 shrink-0" />
									<span className={labelClass}>MCP servers</span>
								</Link>
							) : (
								<Link
									to="/"
									className={cn(
										navItemClass,
										serversActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={serversActive ? "page" : undefined}
									aria-label="MCP servers"
								>
									<ServerIcon className="size-4 shrink-0" />
									<span className={labelClass}>MCP servers</span>
								</Link>
							)}
						</TooltipTrigger>
						<TooltipContent side="right">MCP servers</TooltipContent>
					</Tooltip>

					{expanded && authenticated && (
						<p className="mt-3 px-2.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
							Models
						</p>
					)}

					<Tooltip>
						<TooltipTrigger asChild>
							{authenticated ? (
								<Link
									to="/admin/models"
									className={cn(
										navItemClass,
										modelsActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={modelsActive ? "page" : undefined}
									aria-label="Models"
								>
									<BotIcon className="size-4 shrink-0" />
									<span className={labelClass}>Models</span>
								</Link>
							) : (
								<Link
									to="/account/models"
									className={cn(
										navItemClass,
										modelsActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={modelsActive ? "page" : undefined}
									aria-label="Models"
								>
									<BotIcon className="size-4 shrink-0" />
									<span className={labelClass}>Models</span>
								</Link>
							)}
						</TooltipTrigger>
						<TooltipContent side="right">
							{authenticated ? "Manage models" : "Available models"}
						</TooltipContent>
					</Tooltip>

					<Tooltip>
						<TooltipTrigger asChild>
							{authenticated ? (
								<Link
									to="/admin/model-providers"
									className={cn(
										navItemClass,
										modelProvidersActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={modelProvidersActive ? "page" : undefined}
									aria-label="Model providers"
								>
									<CloudIcon className="size-4 shrink-0" />
									<span className={labelClass}>Providers</span>
								</Link>
							) : (
								<span
									className={cn(
										navItemClass,
										"cursor-not-allowed text-muted-foreground/50",
									)}
								>
									<LockKeyholeIcon className="size-4 shrink-0" />
									<span className={labelClass}>Providers</span>
								</span>
							)}
						</TooltipTrigger>
						<TooltipContent side="right">
							{authenticated
								? "Model providers"
								: "Model providers are available to administrators only"}
						</TooltipContent>
					</Tooltip>

					<div className="mt-3 border-t pt-3">
						{expanded && (
							<p className="mb-1 px-2.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
								Account
							</p>
						)}
						<Tooltip>
							<TooltipTrigger asChild>
								<Link
									to="/account/usage"
									className={cn(
										navItemClass,
										accountUsageActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={accountUsageActive ? "page" : undefined}
									aria-label="My usage"
								>
									<ChartNoAxesCombinedIcon className="size-4 shrink-0" />
									<span className={labelClass}>My usage</span>
								</Link>
							</TooltipTrigger>
							<TooltipContent side="right">Your model usage</TooltipContent>
						</Tooltip>
						<Tooltip>
							<TooltipTrigger asChild>
								<Link
									to="/account"
									className={cn(
										navItemClass,
										accountActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={accountActive ? "page" : undefined}
									aria-label="API keys"
								>
									<UserRoundIcon className="size-4 shrink-0" />
									<span className={labelClass}>API keys</span>
								</Link>
							</TooltipTrigger>
							<TooltipContent side="right">API keys</TooltipContent>
						</Tooltip>
					</div>
				</nav>

				<div className="mt-auto pt-4">
					<Tooltip>
						<TooltipTrigger asChild>
							<Button
								variant="ghost"
								size="sm"
								className={cn(
									"h-8 w-full justify-start gap-2.5 px-2 font-mono text-[11px] text-muted-foreground transition-shadow hover:text-foreground",
									sidebarLocked &&
										"bg-accent/70 text-primary shadow-[0_0_16px_rgba(79,184,178,0.45)] ring-1 ring-primary/30",
								)}
								aria-label={
									sidebarLocked ? "Unlock navigation" : "Lock navigation open"
								}
								onClick={() => setSidebarLocked((locked) => !locked)}
							>
								{sidebarLocked ? (
									<LockIcon className="size-3.5 shrink-0" />
								) : (
									<LockOpenIcon className="size-3.5 shrink-0" />
								)}
								<span className={labelClass}>
									{sidebarLocked ? "Unlock" : "Lock open"}
								</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="right">
							{sidebarLocked ? "Unlock navigation" : "Lock navigation open"}
						</TooltipContent>
					</Tooltip>
				</div>
			</aside>
		</TooltipProvider>
	);
}
