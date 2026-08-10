import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { ServerForm } from "#/components/server-form";
import { type AdminServer, listAdminServers } from "#/lib/admin";
import { getAdminToken } from "#/lib/auth";

export const Route = createFileRoute("/admin/$serverName/edit")({
	component: AdminEdit,
});

type LoadState =
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; server: AdminServer };

function AdminEdit() {
	const { serverName } = Route.useParams();
	const navigate = useNavigate();
	const [state, setState] = useState<LoadState>({ status: "loading" });

	const load = useCallback(() => {
		const token = getAdminToken();
		if (!token) {
			setState({ status: "error", message: "Not authenticated." });
			return;
		}
		listAdminServers(token)
			.then((servers) => {
				const server = servers.find(
					(candidate) => candidate.name === serverName,
				);
				if (!server) {
					setState({
						status: "error",
						message: `Unknown server "${serverName}".`,
					});
					return;
				}
				setState({ status: "ready", server });
			})
			.catch((error: unknown) => {
				setState({
					status: "error",
					message: error instanceof Error ? error.message : String(error),
				});
			});
	}, [serverName]);

	useEffect(() => {
		load();
	}, [load]);

	if (state.status === "loading") {
		return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;
	}
	if (state.status === "error") {
		return <p className="p-8 text-sm text-destructive">{state.message}</p>;
	}
	return (
		<ServerForm
			title={`Edit ${state.server.name}`}
			description="Changes apply to the running gateway immediately."
			mode="edit"
			initial={{
				name: state.server.name,
				description: state.server.description,
				upstream_url: state.server.upstream_url,
				auth: state.server.auth,
				verify_upstream_tls: state.server.verify_upstream_tls,
			}}
			onDone={() => navigate({ to: "/admin" })}
			onCancelHref="/admin"
		/>
	);
}
