import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export function TrustBlock() {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl font-semibold tracking-tight">Why Hyrepath</h2>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          { title: 'Self-hosted', body: 'Run the pipeline on your infrastructure. No third-party dossier store.' },
          { title: 'Open source', body: 'Inspect enrichers, merge logic, and suppression handling in the repo.' },
          { title: 'You own the data', body: 'Customer-supplied identifiers only. Opt-out honored before dispatch.' },
        ].map((item) => (
          <Card key={item.title} className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-base text-primary">{item.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{item.body}</CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

export function SampleDossierCard({ audience }: { audience: string }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl font-semibold tracking-tight">Sample dossier</h2>
      <Card className="border-border bg-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Static preview</p>
            <CardTitle className="font-mono text-lg">alexhyrepath</CardTitle>
          </div>
          <Badge variant="outline" className="font-mono">
            {audience}
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm md:grid-cols-3">
          <div>
            <p className="font-medium">Handles</p>
            <p className="text-muted-foreground">GitHub, X, LinkedIn — confidence scored</p>
          </div>
          <div>
            <p className="font-medium">Verified emails</p>
            <p className="text-muted-foreground">Work email with verification status</p>
          </div>
          <div>
            <p className="font-medium">Sources</p>
            <p className="text-muted-foreground">Maigret, GitRecon, Reacher — attributed</p>
          </div>
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">Preview only — marketing pages do not call the live API.</p>
    </section>
  );
}
