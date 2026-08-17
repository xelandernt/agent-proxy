import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ServerForm } from "#/components/server-form";

export const Route = createFileRoute("/admin/new")({ component: AdminNew });

function AdminNew() {
	const navigate = useNavigate();
	return (
		<ServerForm
			title="New server"
			description="The new endpoint becomes live on the gateway immediately after creation."
			mode="create"
			onDone={() => navigate({ to: "/" })}
			onCancelHref="/"
		/>
	);
}
