import { createFileRoute } from "@tanstack/react-router";
import { ModelProviderForm } from "#/components/model-provider-form";
import { useAdminModelProviders } from "#/lib/model-gateway-queries";

export const Route = createFileRoute(
	"/admin/model-providers/$providerName/edit",
)({ component: EditModelProvider });

function EditModelProvider() {
	const { providerName } = Route.useParams();
	const query = useAdminModelProviders();
	if (query.isLoading)
		return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;
	if (query.isError)
		return (
			<p className="p-8 text-sm text-destructive">
				{query.error instanceof Error
					? query.error.message
					: String(query.error)}
			</p>
		);
	const provider = query.data?.find((entry) => entry.name === providerName);
	if (!provider)
		return (
			<p className="p-8 text-sm text-destructive">
				Unknown model provider “{providerName}”.
			</p>
		);
	return <ModelProviderForm provider={provider} />;
}
