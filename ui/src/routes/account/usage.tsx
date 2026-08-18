import { createFileRoute } from "@tanstack/react-router";
import { ModelUsageDashboard } from "#/components/model-usage-dashboard";

export const Route = createFileRoute("/account/usage")({
	component: () => <ModelUsageDashboard audience="user" />,
});
