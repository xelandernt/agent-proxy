import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { Skeleton } from "#/components/ui/skeleton";
import {
	completeOAuthLogin,
	fetchAdminAuthInfo,
	fetchAuthorizationServer,
} from "#/lib/auth";

export const Route = createFileRoute("/admin/callback")({
	component: AdminCallback,
});

function AdminCallback() {
	const navigate = useNavigate();
	const started = useRef(false);

	useEffect(() => {
		if (started.current) return;
		started.current = true;
		(async () => {
			try {
				const authInfo = await fetchAdminAuthInfo();
				const oauthInfo = authInfo?.oauth;
				if (!oauthInfo) throw new Error("Admin OAuth is not configured.");
				const server = await fetchAuthorizationServer(oauthInfo.issuer);
				if (!server)
					throw new Error("Authorization server metadata unavailable.");
				await completeOAuthLogin(oauthInfo, server);
			} catch (error) {
				sessionStorage.setItem(
					"admin-login-error",
					error instanceof Error ? error.message : String(error),
				);
			}
			navigate({ to: "/admin", replace: true });
		})();
	}, [navigate]);

	return (
		<div className="mx-auto flex w-full max-w-md flex-col gap-4 p-8">
			<Skeleton className="h-9 w-2/3" />
			<Skeleton className="h-40 w-full" />
		</div>
	);
}
