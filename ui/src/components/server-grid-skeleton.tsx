import { Card } from "#/components/ui/card";
import { Skeleton } from "#/components/ui/skeleton";

export function ServerGridSkeleton() {
	return (
		<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
			{[0, 1, 2].map((index) => (
				<Card key={index} className="flex flex-col gap-4 p-6">
					<Skeleton className="h-5 w-1/3" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-2/3" />
					<Skeleton className="h-8 w-24" />
				</Card>
			))}
		</div>
	);
}
