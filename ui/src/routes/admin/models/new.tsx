import { createFileRoute } from "@tanstack/react-router";
import { ModelForm } from "#/components/model-form";

export const Route = createFileRoute("/admin/models/new")({
	component: NewModel,
});

function NewModel() {
	return <ModelForm />;
}
