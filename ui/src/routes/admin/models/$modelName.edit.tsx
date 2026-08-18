import { createFileRoute, Link } from "@tanstack/react-router";
import { ModelForm } from "#/components/model-form";
import { Button } from "#/components/ui/button";
import { useAdminModels } from "#/lib/model-gateway-queries";

export const Route = createFileRoute("/admin/models/$modelName/edit")({
	component: EditModel,
});

function EditModel() {
	const { modelName } = Route.useParams();
	const query = useAdminModels();
	if (query.isLoading)
		return (
			<p className="mx-auto max-w-3xl p-8 text-sm text-muted-foreground">
				Loading…
			</p>
		);
	const model = query.data?.find((entry) => entry.name === modelName);
	if (!model) {
		return (
			<div className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
				<p className="text-sm text-destructive">
					Model “{modelName}” was not found.
				</p>
				<Link to="/admin/models">
					<Button variant="outline">Back to models</Button>
				</Link>
			</div>
		);
	}
	return <ModelForm model={model} />;
}
