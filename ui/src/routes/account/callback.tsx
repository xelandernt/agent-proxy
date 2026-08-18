import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { Skeleton } from "#/components/ui/skeleton";
import {
	completeUserOAuthLogin,
	fetchAuthorizationServer,
	fetchUserAuthInfo,
} from "#/lib/auth";

export const Route = createFileRoute("/account/callback")({
	component: AccountCallback,
});

function AccountCallback() {
	const navigate = useNavigate();
	const started = useRef(false);
	useEffect(() => {
		if (started.current) return;
		started.current = true;
		void (async () => {
			try {
				const oauthInfo = (await fetchUserAuthInfo())?.oauth;
				if (!oauthInfo) throw new Error("User OAuth is not configured.");
				const server = await fetchAuthorizationServer(oauthInfo.issuer);
				if (!server)
					throw new Error("Authorization server metadata unavailable.");
				await completeUserOAuthLogin(oauthInfo, server);
			} catch (error) {
				sessionStorage.setItem(
					"user-login-error",
					error instanceof Error ? error.message : String(error),
				);
			}
			await navigate({ to: "/account", replace: true });
		})();
	}, [navigate]);
	return (
		<div className="mx-auto flex w-full max-w-md flex-col gap-4 p-8">
			<Skeleton className="h-9 w-2/3" />
			<Skeleton className="h-40 w-full" />
		</div>
	);
}
