import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AuthProviderEditor } from "#/components/auth-provider-editor";

export const Route = createFileRoute("/admin/auth-providers/new")({
	validateSearch: (search: Record<string, unknown>) => ({
		provider: typeof search.provider === "string" ? search.provider : undefined,
	}),
	component: NewAuthProvider,
});

function NewAuthProvider() {
	const navigate = useNavigate();
	const { provider } = Route.useSearch();
	return (
		<AuthProviderEditor
			mode="create"
			initialProvider={provider}
			onDone={() => navigate({ to: "/admin/auth-providers" })}
		/>
	);
}
