import { TanStackDevtools } from "@tanstack/react-devtools";
import { createRootRoute, HeadContent, Scripts } from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { BackgroundDither } from "#/components/background-dither";
import { DitherToggle, ThemeToggle } from "#/components/toggles";
import { Toaster } from "#/components/ui/sonner";
import { ThemeProvider } from "#/lib/theme";

import appCss from "../styles.css?url";

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
				<ThemeProvider>
					<header className="sticky top-0 z-40 flex items-center justify-end gap-1 bg-background/70 p-4 backdrop-blur">
						<DitherToggle />
						<ThemeToggle />
					</header>
					{children}
				</ThemeProvider>
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
