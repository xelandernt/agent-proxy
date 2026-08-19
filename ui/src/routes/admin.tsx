import { createFileRoute, Outlet, useLocation } from "@tanstack/react-router";
import { ServerCogIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AdminLogin } from "#/components/admin-login";
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
import {
	type AdminAuthStatus,
	checkAdminAuth,
	endAdminSession,
} from "#/lib/auth";
import { onAuthenticationExpired } from "#/lib/auth-session";

export const Route = createFileRoute("/admin")({ component: AdminLayout });

function AdminLayout() {
	const location = useLocation();
	const [status, setStatus] = useState<AdminAuthStatus>("checking");

	const onCallbackPath = location.pathname.endsWith("/admin/callback");

	const check = useCallback(() => {
		setStatus("checking");
		checkAdminAuth().then((next) => {
			if (next === "unauthenticated") endAdminSession();
			setStatus(next);
		});
	}, []);

	useEffect(() => {
		if (onCallbackPath) return;
		check();
	}, [onCallbackPath, check]);
	useEffect(
		() => onAuthenticationExpired("admin", () => setStatus("unauthenticated")),
		[],
	);

	if (onCallbackPath) return <Outlet />;

	if (status === "checking") {
		return (
			<div className="mx-auto flex w-full max-w-md flex-col gap-4 p-8">
				<Skeleton className="h-9 w-1/2" />
				<Skeleton className="h-40 w-full" />
			</div>
		);
	}

	if (status === "authenticated") {
		return <Outlet />;
	}

	if (status === "unauthenticated") {
		return <AdminLogin onAuthenticated={() => setStatus("authenticated")} />;
	}

	return (
		<div className="mx-auto w-full max-w-2xl p-8">
			<Empty>
				<EmptyMedia variant="icon">
					<ServerCogIcon />
				</EmptyMedia>
				<EmptyHeader>
					<EmptyTitle>Could not reach the gateway</EmptyTitle>
					<EmptyDescription>
						The admin API did not respond. Check that the gateway is running.
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
