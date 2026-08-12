import { createFileRoute, Link } from "@tanstack/react-router";
import { ServerCogIcon } from "lucide-react";

import { Button } from "#/components/ui/button";
import { ProviderGuidePage } from "#/lib/provider-docs/guide";
import { getProviderGuide } from "#/lib/provider-docs/registry";

export const Route = createFileRoute("/docs/$provider")({
	component: ProviderDocsPage,
});

function ProviderDocsPage() {
	const { provider } = Route.useParams();
	const guide = getProviderGuide(provider);

	if (!guide) {
		return (
			<div className="page-wrap flex flex-col items-start gap-4 py-16">
				<div className="flex items-center gap-2 text-[var(--sea-ink-soft)]">
					<ServerCogIcon className="size-5" />
					<p className="font-mono text-sm">
						No guide for provider <code>{provider}</code>.
					</p>
				</div>
				<Link to="/docs">
					<Button>Browse all provider guides</Button>
				</Link>
			</div>
		);
	}

	return <ProviderGuidePage guide={guide} />;
}
