import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AuthProviderEditor } from "#/components/auth-provider-editor";
import { useAdminAuthProviders } from "#/lib/admin-queries";

export const Route = createFileRoute(
	"/admin/auth-providers/$providerName/edit",
)({ component: EditAuthProvider });

function EditAuthProvider() {
	const { providerName } = Route.useParams();
	const navigate = useNavigate();
	const query = useAdminAuthProviders();
	const provider = query.data?.find(
		(candidate) => candidate.name === providerName,
	);
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
	if (!provider)
		return (
			<p className="p-8 text-sm text-destructive">
				Unknown provider "{providerName}".
			</p>
		);
	return (
		<AuthProviderEditor
			mode="edit"
			initial={provider}
			onDone={() => navigate({ to: "/admin/auth-providers" })}
		/>
	);
}
