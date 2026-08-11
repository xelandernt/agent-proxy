import { Card, CardContent, CardHeader, CardTitle } from "#/components/ui/card";
import { Skeleton } from "#/components/ui/skeleton";

export function ServerPageSkeleton() {
	return (
		<div className="flex flex-col gap-8">
			<Skeleton className="h-10 w-1/3" />
			<Skeleton className="h-4 w-2/3" />
			<Card>
				<CardHeader>
					<CardTitle className="font-sans text-base font-semibold">
						Usage
					</CardTitle>
				</CardHeader>
				<CardContent className="flex flex-col gap-4">
					<Skeleton className="h-8 w-64" />
					<Skeleton className="h-10 w-28" />
					<Skeleton className="h-40 w-full" />
				</CardContent>
			</Card>
		</div>
	);
}
