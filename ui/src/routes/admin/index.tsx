import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

export const Route = createFileRoute("/admin/")({ component: AdminIndex });

function AdminIndex() {
	const navigate = useNavigate();

	useEffect(() => {
		void navigate({ to: "/", replace: true });
	}, [navigate]);

	return null;
}
