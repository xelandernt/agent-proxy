import { TanStackDevtools } from "@tanstack/react-devtools";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { FileQuestionIcon } from "lucide-react";
import { BackgroundDither } from "#/components/background-dither";
import { DitherToggle, ThemeToggle } from "#/components/toggles";
import { Button } from "#/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Toaster } from "#/components/ui/sonner";
import { UsagePill } from "#/components/usage-pill";
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
					<header className="relative z-40 flex items-center justify-between px-8 pt-6">
						<Link
							to="/"
							aria-label="Agent Gateway home"
							className="group inline-flex items-center no-underline"
						>
							<span className="display-title text-lg font-bold tracking-tight text-[var(--sea-ink-soft)] transition-colors group-hover:text-[var(--sea-ink)]">
								Agent Gateway
							</span>
						</Link>
						<div className="flex items-center gap-1">
							<UsagePill />
							<DitherToggle />
							<ThemeToggle />
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
