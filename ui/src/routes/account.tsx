import { createFileRoute, Outlet, useLocation } from "@tanstack/react-router";
import { UserCogIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "#/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Skeleton } from "#/components/ui/skeleton";
import { UserLogin } from "#/components/user-login";
import {
	type AdminAuthStatus,
	checkUserAuth,
	endUserSession,
} from "#/lib/auth";

export const Route = createFileRoute("/account")({ component: AccountLayout });

function AccountLayout() {
	const location = useLocation();
	const [status, setStatus] = useState<AdminAuthStatus>("checking");
	const callback = location.pathname.endsWith("/account/callback");
	const check = useCallback(() => {
		setStatus("checking");
		void checkUserAuth().then((next) => {
			if (next === "unauthenticated") void endUserSession();
			setStatus(next);
		});
	}, []);

	useEffect(() => {
		if (!callback) check();
	}, [callback, check]);
	if (callback) return <Outlet />;
	if (status === "checking")
		return (
			<div className="mx-auto flex w-full max-w-md flex-col gap-4 p-8">
				<Skeleton className="h-9 w-1/2" />
				<Skeleton className="h-40 w-full" />
			</div>
		);
	if (status === "authenticated") return <Outlet />;
	if (status === "unauthenticated")
		return <UserLogin onAuthenticated={() => setStatus("authenticated")} />;

	return (
		<div className="mx-auto w-full max-w-2xl p-8">
			<Empty>
				<EmptyMedia variant="icon">
					<UserCogIcon />
				</EmptyMedia>
				<EmptyHeader>
					<EmptyTitle>Could not reach the gateway</EmptyTitle>
					<EmptyDescription>
						The user API did not respond. Check that the gateway is running.
					</EmptyDescription>
				</EmptyHeader>
				<EmptyContent>
					<Button variant="outline" onClick={check}>
						Retry
					</Button>
				</EmptyContent>
			</Empty>
		</div>
	);
}
