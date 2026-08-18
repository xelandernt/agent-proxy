import { TanStackDevtools } from "@tanstack/react-devtools";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createRootRoute,
	Link,
	Outlet,
	useLocation,
} from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import {
	FileQuestionIcon,
	LogInIcon,
	LogOutIcon,
	ShieldCheckIcon,
	UserRoundIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AdminNavigation } from "#/components/admin-navigation";
import { BackgroundDither } from "#/components/background-dither";
import { DitherToggle, ThemeToggle } from "#/components/toggles";
import { Button } from "#/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Toaster } from "#/components/ui/sonner";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "#/components/ui/tooltip";
import { UsagePill } from "#/components/usage-pill";
import {
	checkAdminAuth,
	checkUserAuth,
	endAdminSession,
	endUserSession,
} from "#/lib/auth";
import { patchGatewayFetch } from "#/lib/gateway";
import { ThemeProvider } from "#/lib/theme";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			staleTime: 30_000,
			retry: 1,
		},
	},
});

patchGatewayFetch();

export const Route = createRootRoute({
	component: RootDocument,
	notFoundComponent: RootNotFound,
});

function RootDocument() {
	return (
		<>
			<BackgroundDither />
			<QueryClientProvider client={queryClient}>
				<ThemeProvider>
					<AdminNavigation />
					<header className="relative z-40 flex items-center justify-end px-8 pt-6">
						<div className="flex items-center gap-1">
							<UsagePill />
							<DitherToggle />
							<ThemeToggle />
							<SessionControl />
						</div>
					</header>
					<Outlet />
				</ThemeProvider>
			</QueryClientProvider>
			<Toaster />
			<TanStackDevtools
				config={{
					position: "bottom-right",
				}}
				plugins={[
					{
						name: "Tanstack Router",
						render: <TanStackRouterDevtoolsPanel />,
					},
				]}
			/>
		</>
	);
}

function SessionControl() {
	const location = useLocation();
	const [authenticated, setAuthenticated] = useState(false);
	const [busy, setBusy] = useState(false);
	const userArea = location.pathname.startsWith("/account");
	const callback =
		location.pathname === "/admin/callback" ||
		location.pathname === "/account/callback";

	useEffect(() => {
		if (callback) {
			setAuthenticated(false);
			return;
		}
		let active = true;
		const checkAuth = userArea ? checkUserAuth : checkAdminAuth;
		checkAuth().then((status) => {
			if (active) setAuthenticated(status === "authenticated");
		});
		return () => {
			active = false;
		};
	}, [callback, userArea]);

	if (callback || (userArea && !authenticated)) return null;

	if (!authenticated) {
		return (
			<TooltipProvider>
				<DropdownMenu>
					<Tooltip>
						<TooltipTrigger asChild>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									aria-label="Sign in"
									className="transition-transform hover:scale-110 active:scale-95"
								>
									<LogInIcon className="size-4" />
								</Button>
							</DropdownMenuTrigger>
						</TooltipTrigger>
						<TooltipContent side="bottom">Sign in</TooltipContent>
					</Tooltip>
					<DropdownMenuContent align="end" className="min-w-48">
						<DropdownMenuLabel>Sign in as</DropdownMenuLabel>
						<DropdownMenuGroup>
							<DropdownMenuItem asChild>
								<Link to="/account">
									<UserRoundIcon />
									User
								</Link>
							</DropdownMenuItem>
							<DropdownMenuItem asChild>
								<Link to="/admin">
									<ShieldCheckIcon />
									Administrator
								</Link>
							</DropdownMenuItem>
						</DropdownMenuGroup>
					</DropdownMenuContent>
				</DropdownMenu>
			</TooltipProvider>
		);
	}

	const logout = async () => {
		setBusy(true);
		try {
			const endSession = userArea ? endUserSession : endAdminSession;
			if (await endSession()) {
				window.location.assign("/");
				return;
			}
			toast.error("Could not sign out. Try again.");
		} finally {
			setBusy(false);
		}
	};

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						aria-label="Sign out"
						disabled={busy}
						onClick={logout}
						className="transition-transform hover:scale-110 active:scale-95"
					>
						<LogOutIcon className="size-4" />
					</Button>
				</TooltipTrigger>
				<TooltipContent side="bottom">Sign out</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
}

function RootNotFound() {
	return (
		<div className="mx-auto flex w-full max-w-2xl flex-col p-8">
			<Empty>
				<EmptyMedia variant="icon">
					<FileQuestionIcon />
				</EmptyMedia>
				<EmptyHeader>
					<EmptyTitle>Page not found</EmptyTitle>
					<EmptyDescription>
						This address does not match any page on the gateway.
					</EmptyDescription>
				</EmptyHeader>
				<EmptyContent>
					<Link to="/">
						<Button variant="outline">Back to servers</Button>
					</Link>
				</EmptyContent>
			</Empty>
		</div>
	);
}
