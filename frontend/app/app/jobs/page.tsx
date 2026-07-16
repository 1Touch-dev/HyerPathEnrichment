import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function JobsIndexPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Results</h1>
        <p className="text-sm text-muted-foreground">Browse enrichment job results or view history.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Job results</CardTitle>
          <CardDescription>Open a specific job from history or start a new enrichment.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/app/history">View history</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/app/enrich">New enrichment</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
