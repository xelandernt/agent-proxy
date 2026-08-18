import { Link, useLocation } from "@tanstack/react-router";
import {
	BotIcon,
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
	const providersActive =
		location.pathname.startsWith("/admin/auth-providers") ||
		location.pathname.startsWith("/docs");
	const modelsActive =
		location.pathname.startsWith("/admin/models") ||
		location.pathname.startsWith("/account/models");
	const accountActive =
		location.pathname.startsWith("/account") && !modelsActive;
	const serversActive =
		!providersActive &&
		!modelsActive &&
		!accountActive &&
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
									aria-label="Servers"
								>
									<ServerIcon className="size-4 shrink-0" />
									<span className={labelClass}>Servers</span>
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
									aria-label="Servers"
								>
									<ServerIcon className="size-4 shrink-0" />
									<span className={labelClass}>Servers</span>
								</Link>
							)}
						</TooltipTrigger>
						<TooltipContent side="right">Servers</TooltipContent>
					</Tooltip>

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
									to="/admin/auth-providers"
									search={{ provider: undefined }}
									className={cn(
										navItemClass,
										providersActive
											? "bg-accent text-foreground"
											: "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
									)}
									aria-current={providersActive ? "page" : undefined}
									aria-label="Providers"
								>
									<KeyRoundIcon className="size-4 shrink-0" />
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
								? "Providers"
								: "Providers are available to administrators only"}
						</TooltipContent>
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
								aria-label="Account"
							>
								<UserRoundIcon className="size-4 shrink-0" />
								<span className={labelClass}>Account</span>
							</Link>
						</TooltipTrigger>
						<TooltipContent side="right">Account and API keys</TooltipContent>
					</Tooltip>
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
