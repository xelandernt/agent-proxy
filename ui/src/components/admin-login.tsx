import { KeyRoundIcon, LogInIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import { setAdminToken, startOAuthLogin } from "#/lib/auth";

export function AdminLogin({
	onAuthenticated,
}: {
	onAuthenticated: () => void;
}) {
	const [busy, setBusy] = useState<"oauth" | "token" | null>(null);
	const [tokenInput, setTokenInput] = useState("");
	const [error, setError] = useState<string | null>(() => {
		const stored = sessionStorage.getItem("admin-login-error");
		if (stored) sessionStorage.removeItem("admin-login-error");
		return stored;
	});

	const signInWithOAuth = async () => {
		setBusy("oauth");
		setError(null);
		const outcome = await startOAuthLogin();
		if (outcome === "unsupported") {
			setBusy(null);
			setError(
				"This gateway's admin provider does not host an OAuth authorization server. Paste an access token from your identity provider below.",
			);
		}
	};

	const submitToken = (event: FormEvent) => {
		event.preventDefault();
		const token = tokenInput.trim();
		if (!token) return;
		setAdminToken(token);
		setBusy("token");
		onAuthenticated();
	};

	return (
		<div className="mx-auto flex w-full max-w-md flex-col gap-6 p-8">
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2 font-sans text-base">
						<KeyRoundIcon className="size-4" />
						Admin sign in
					</CardTitle>
					<CardDescription>
						Authenticate with the gateway's admin identity provider to manage
						servers.
					</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-col gap-4">
					<Button onClick={signInWithOAuth} disabled={busy !== null}>
						<LogInIcon className="size-4" />
						{busy === "oauth" ? "Redirecting…" : "Sign in with provider"}
					</Button>
					<div className="flex items-center gap-3 text-xs text-muted-foreground">
						<span className="h-px flex-1 bg-border" />
						or paste an access token
						<span className="h-px flex-1 bg-border" />
					</div>
					<form onSubmit={submitToken} className="flex flex-col gap-3">
						<input
							type="password"
							value={tokenInput}
							onChange={(event) => setTokenInput(event.target.value)}
							placeholder="Bearer token"
							autoComplete="off"
							className="h-9 w-full rounded-md border bg-transparent px-3 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
						/>
						<Button
							type="submit"
							disabled={busy !== null || !tokenInput.trim()}
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
