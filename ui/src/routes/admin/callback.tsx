import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Skeleton } from "#/components/ui/skeleton";
import {
	completeOAuthLogin,
	fetchAuthorizationServerMetadata,
} from "#/lib/auth";

export const Route = createFileRoute("/admin/callback")({
	validateSearch: (search: Record<string, unknown>) => ({
		code: typeof search.code === "string" ? search.code : undefined,
		state: typeof search.state === "string" ? search.state : undefined,
	}),
	component: AdminCallback,
});

function AdminCallback() {
	const navigate = useNavigate();
	const search = Route.useSearch();

	useEffect(() => {
		const code = search.code ?? "";
		const state = search.state ?? "";
		(async () => {
			try {
				if (!code) throw new Error("Authorization response missing a code.");
				const metadata = await fetchAuthorizationServerMetadata();
				if (!metadata)
					throw new Error("Authorization server metadata unavailable.");
				await completeOAuthLogin(code, state, metadata);
			} catch (error) {
				sessionStorage.setItem(
					"admin-login-error",
					error instanceof Error ? error.message : String(error),
				);
			}
			navigate({ to: "/admin", replace: true });
		})();
	}, [search.code, search.state, navigate]);

	return (
		<div className="mx-auto flex w-full max-w-md flex-col gap-4 p-8">
			<Skeleton className="h-9 w-2/3" />
			<Skeleton className="h-40 w-full" />
		</div>
	);
}
