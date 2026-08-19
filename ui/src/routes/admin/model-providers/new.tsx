import { createFileRoute } from "@tanstack/react-router";
import { ModelProviderForm } from "#/components/model-provider-form";

export const Route = createFileRoute("/admin/model-providers/new")({
	component: NewModelProvider,
});

function NewModelProvider() {
	return <ModelProviderForm />;
}
