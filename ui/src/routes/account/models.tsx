import { createFileRoute, Link } from "@tanstack/react-router";
import { BoxIcon, KeyRoundIcon } from "lucide-react";
import { ModelPricingSummary } from "#/components/model-pricing-summary";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Skeleton } from "#/components/ui/skeleton";
import { CopySnippet } from "#/lib/copy";
import { GATEWAY_URL } from "#/lib/gateway";
import { useUserModels } from "#/lib/model-gateway-queries";

export const Route = createFileRoute("/account/models")({
	component: UserModels,
});

function UserModels() {
	const query = useUserModels();
	const openAiBaseUrl = `${GATEWAY_URL.replace(/\/$/, "")}/v1`;

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-8">
			<header className="flex items-center justify-between gap-4">
				<div>
					<h1 className="font-serif text-4xl font-bold tracking-tight">
						Models
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						Models available for your proxy API keys.
					</p>
				</div>
				<Link to="/account">
					<Button variant="outline">
						<KeyRoundIcon data-icon="inline-start" />
						Manage API keys
					</Button>
				</Link>
			</header>
			<Card>
				<CardHeader>
					<CardTitle>OpenAI-compatible endpoint</CardTitle>
					<CardDescription>
						Use this as the OpenAI SDK base URL with one of your proxy API keys.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<CopySnippet
						caption="Base URL"
						content={openAiBaseUrl}
						label="Copy endpoint URL"
						successMessage="Endpoint URL copied"
					/>
				</CardContent>
			</Card>

			{query.isLoading && (
				<div className="grid gap-4 md:grid-cols-2">
					{[0, 1, 2].map((index) => (
						<Card key={index} className="flex flex-col gap-4 p-6">
							<Skeleton className="h-5 w-1/3" />
							<Skeleton className="h-4 w-full" />
							<Skeleton className="h-9 w-full" />
						</Card>
					))}
				</div>
			)}

			{query.isError && (
				<Empty>
					<EmptyMedia variant="icon">
						<BoxIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Could not load models</EmptyTitle>
						<EmptyDescription>
							{query.error instanceof Error
								? query.error.message
								: String(query.error)}
						</EmptyDescription>
					</EmptyHeader>
					<EmptyContent>
						<Button variant="outline" onClick={() => query.refetch()}>
							Retry
						</Button>
					</EmptyContent>
				</Empty>
			)}

			{query.isSuccess && query.data.length === 0 && (
				<Empty>
					<EmptyMedia variant="icon">
						<BoxIcon />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>No models available</EmptyTitle>
						<EmptyDescription>
							An administrator has not configured any models yet.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			)}

			{query.isSuccess && query.data.length > 0 && (
				<div className="grid gap-4 md:grid-cols-2">
					{query.data.map((model) => (
						<Card key={model.name}>
							<CardHeader>
								<CardTitle className="font-mono text-base">
									{model.name}
								</CardTitle>
								<CardDescription>Available for API key access</CardDescription>
							</CardHeader>
							<CardContent className="flex flex-col gap-4">
								<ModelPricingSummary pricing={model.pricing} />
								<CopySnippet
									caption="OpenAI model ID"
									content={model.name}
									label="Copy model ID"
									successMessage="Model ID copied"
								/>
							</CardContent>
						</Card>
					))}
				</div>
			)}
		</div>
	);
}
