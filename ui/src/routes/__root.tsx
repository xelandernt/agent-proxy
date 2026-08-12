import { TanStackDevtools } from "@tanstack/react-devtools";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createRootRoute,
	HeadContent,
	Link,
	Scripts,
} from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { BackgroundDither } from "#/components/background-dither";
import { DitherToggle, ThemeToggle } from "#/components/toggles";
import { Toaster } from "#/components/ui/sonner";
import { UsagePill } from "#/components/usage-pill";
import { patchGatewayFetch } from "#/lib/gateway";
import { ThemeProvider } from "#/lib/theme";

import appCss from "../styles.css?url";

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
	head: () => ({
		scripts: [
			{
				children: `
(function () {
  var stored = localStorage.getItem("theme");
  var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (stored === "dark" || (!stored && dark)) {
    document.documentElement.classList.add("dark");
  }
})();
`.trim(),
			},
		],
		meta: [
			{
				charSet: "utf-8",
			},
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1",
			},
			{
				title: "MCP Servers",
			},
		],
		links: [
			{
				rel: "stylesheet",
				href: appCss,
			},
		],
	}),
	shellComponent: RootDocument,
});

function RootDocument({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en" suppressHydrationWarning>
			<head>
				<HeadContent />
			</head>
			<body suppressHydrationWarning>
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
						{children}
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
				<Scripts />
			</body>
		</html>
	);
}
