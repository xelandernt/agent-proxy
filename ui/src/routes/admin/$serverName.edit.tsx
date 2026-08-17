import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ServerForm } from "#/components/server-form";
import { useAdminServers } from "#/lib/admin-queries";

export const Route = createFileRoute("/admin/$serverName/edit")({
	component: AdminEdit,
});

function AdminEdit() {
	const { serverName } = Route.useParams();
	const navigate = useNavigate();
	const serversQuery = useAdminServers();
	const server = serversQuery.data?.find(
		(candidate) => candidate.name === serverName,
	);

	if (serversQuery.isLoading) {
		return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;
	}
	if (serversQuery.isError) {
		return (
			<p className="p-8 text-sm text-destructive">
				{serversQuery.error instanceof Error
					? serversQuery.error.message
					: String(serversQuery.error)}
			</p>
		);
	}
	if (!server) {
		return (
			<p className="p-8 text-sm text-destructive">
				Unknown server "{serverName}".
			</p>
		);
	}
	return (
		<ServerForm
			title={`Edit ${server.name}`}
			description="Changes apply to the running gateway immediately."
			mode="edit"
			initial={{
				name: server.name,
				description: server.description,
				upstream_url: server.upstream_url,
				auth_provider: server.auth_provider,
				verify_upstream_tls: server.verify_upstream_tls,
				forward_client_credentials: server.forward_client_credentials,
			}}
			onDone={() => navigate({ to: "/" })}
			onCancelHref="/"
		/>
	);
}
