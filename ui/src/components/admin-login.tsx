import { Link } from "@tanstack/react-router";
import { ArrowLeftIcon, KeyRoundIcon, LogInIcon } from "lucide-react";
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
import {
	type AdminAuthInfo,
	establishAdminSession,
	fetchAdminAuthInfo,
	loginWithPassword,
	startOAuthLogin,
} from "#/lib/auth";

function FieldLabel({
	htmlFor,
	children,
}: {
	htmlFor: string;
	children: string;
}) {
	return (
		<label
			htmlFor={htmlFor}
			className="font-mono text-xs text-muted-foreground"
		>
			{children}
		</label>
	);
}

export function AdminLogin({
	onAuthenticated,
}: {
	onAuthenticated: () => void;
}) {
	const [busy, setBusy] = useState<"oauth" | "password" | "token" | null>(null);
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [tokenInput, setTokenInput] = useState("");
	const [authInfo, setAuthInfo] = useState<AdminAuthInfo | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		fetchAdminAuthInfo().then(setAuthInfo);
	}, []);

	useEffect(() => {
		const stored = sessionStorage.getItem("admin-login-error");
		if (stored) {
			sessionStorage.removeItem("admin-login-error");
			setError(stored);
		}
	}, []);

	const signInWithOAuth = async () => {
		setBusy("oauth");
		setError(null);
		const outcome = await startOAuthLogin();
		if (outcome === "unsupported") {
			setBusy(null);
			setError(
				"This gateway's admin identity provider has no browser sign-in configured. Paste an access token from your identity provider below.",
			);
		}
	};

	const submitPassword = async (event: FormEvent) => {
		event.preventDefault();
		if (!username.trim() || !password) return;
		setBusy("password");
		setError(null);
		const ok = await loginWithPassword(username, password);
		if (!ok) {
			setBusy(null);
			setError("Invalid username or password.");
			return;
		}
		onAuthenticated();
	};

	const submitToken = async (event: FormEvent) => {
		event.preventDefault();
		const token = tokenInput.trim();
		if (!token) return;
		setBusy("token");
		setError(null);
		const ok = await establishAdminSession(token);
		if (!ok) {
			setBusy(null);
			setError("The gateway rejected the token.");
			return;
		}
		onAuthenticated();
	};

	const staticPassword = authInfo !== null && authInfo.provider === "static";
	const oauthAvailable = authInfo !== null && authInfo.oauth !== null;

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
					{staticPassword ? (
						<form onSubmit={submitPassword} className="flex flex-col gap-3">
							<FieldLabel htmlFor="admin-username">Username</FieldLabel>
							<input
								id="admin-username"
								type="text"
								value={username}
								onChange={(event) => setUsername(event.target.value)}
								placeholder="Username"
								autoComplete="username"
								className="h-9 w-full rounded-md border bg-transparent px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
							/>
							<FieldLabel htmlFor="admin-password">Password</FieldLabel>
							<input
								id="admin-password"
								type="password"
								value={password}
								onChange={(event) => setPassword(event.target.value)}
								placeholder="Password"
								autoComplete="current-password"
								className="h-9 w-full rounded-md border bg-transparent px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
							/>
							<Button
								type="submit"
								disabled={busy !== null || !username.trim() || !password}
							>
								{busy === "password" ? "Signing in…" : "Sign in"}
							</Button>
						</form>
					) : oauthAvailable ? (
						<>
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
								<FieldLabel htmlFor="admin-token">Access token</FieldLabel>
								<input
									id="admin-token"
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
						</>
					) : (
						<>
							<p className="text-sm leading-relaxed text-muted-foreground">
								The admin provider{" "}
								<code className="font-mono">{authInfo?.provider}</code> verifies
								tokens but has no browser sign-in configured. Get an access
								token from your identity provider and paste it below.
							</p>
							<form onSubmit={submitToken} className="flex flex-col gap-3">
								<FieldLabel htmlFor="admin-token">Access token</FieldLabel>
								<input
									id="admin-token"
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
						</>
					)}
					{error && <p className="text-sm text-destructive">{error}</p>}
				</CardContent>
			</Card>
		</div>
	);
}
