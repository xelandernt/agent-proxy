import { Link } from "@tanstack/react-router";
import { ArrowLeftIcon, LogInIcon, UserIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import { Field, FieldLabel } from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import {
	establishUserSession,
	fetchUserAuthInfo,
	startUserOAuthLogin,
	type UserAuthInfo,
} from "#/lib/auth";

export function UserLogin({
	onAuthenticated,
}: {
	onAuthenticated: () => void;
}) {
	const [busy, setBusy] = useState<"oauth" | "token" | null>(null);
	const [token, setToken] = useState("");
	const [authInfo, setAuthInfo] = useState<UserAuthInfo | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		void fetchUserAuthInfo().then(setAuthInfo);
	}, []);
	useEffect(() => {
		const stored = sessionStorage.getItem("user-login-error");
		if (stored) {
			sessionStorage.removeItem("user-login-error");
			setError(stored);
		}
	}, []);

	const oauthLogin = async () => {
		setBusy("oauth");
		setError(null);
		if ((await startUserOAuthLogin()) === "unsupported") {
			setBusy(null);
			setError(
				"Browser sign-in is unavailable. Paste an identity-provider access token instead.",
			);
		}
	};

	const tokenLogin = async (event: FormEvent) => {
		event.preventDefault();
		setBusy("token");
		setError(null);
		if (!(await establishUserSession(token.trim()))) {
			setBusy(null);
			setError(
				"The gateway rejected the token. It must identify a user and include an email address.",
			);
			return;
		}
		onAuthenticated();
	};

	return (
		<div className="mx-auto flex w-full max-w-md flex-col gap-6 p-8">
			<Link to="/">
				<Button variant="ghost" size="sm">
					<ArrowLeftIcon className="size-4" />
					Back to servers
				</Button>
			</Link>
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<UserIcon className="size-4" />
						User sign in
					</CardTitle>
					<CardDescription>
						Sign in with your configured identity provider to manage personal
						proxy API keys.
					</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-col gap-4">
					{authInfo?.oauth && (
						<>
							<Button
								onClick={() => void oauthLogin()}
								disabled={busy !== null}
							>
								<LogInIcon className="size-4" />
								{busy === "oauth" ? "Redirecting…" : "Sign in with provider"}
							</Button>
							<div className="flex items-center gap-3 text-xs text-muted-foreground">
								<span className="h-px flex-1 bg-border" />
								or paste an access token
								<span className="h-px flex-1 bg-border" />
							</div>
						</>
					)}
					<form onSubmit={tokenLogin} className="flex flex-col gap-3">
						<Field>
							<FieldLabel htmlFor="user-token">Access token</FieldLabel>
							<Input
								id="user-token"
								type="password"
								value={token}
								onChange={(event) => setToken(event.target.value)}
								placeholder="Bearer token"
								autoComplete="off"
								className="font-mono"
							/>
						</Field>
						<Button
							type="submit"
							variant={authInfo?.oauth ? "outline" : "default"}
							disabled={busy !== null || !token.trim()}
						>
							{busy === "token" ? "Checking…" : "Sign in with token"}
						</Button>
					</form>
					{error && <p className="text-sm text-destructive">{error}</p>}
				</CardContent>
			</Card>
		</div>
	);
}
