'use client';

import type { ReactNode } from 'react';
import type { Dossier } from '@/src/lib/types';
import { ResultRow } from './ResultRow';
import type { DossierEntity } from './dossier-entity';

type DossierScanListProps = {
  dossier: Dossier;
  selectedId?: string | null;
  onSelect: (entity: DossierEntity) => void;
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</p>
      {children}
    </div>
  );
}

export function DossierScanList({ dossier, selectedId, onSelect }: DossierScanListProps) {
  return (
    <div className="flex flex-col gap-6">
      {dossier.handles.length ? (
        <Section title="Handles">
          <div className="flex flex-col gap-2">
            {dossier.handles.map((handle) => {
              const entity: DossierEntity = {
                kind: 'handle',
                id: `${handle.platform}-${handle.username}`,
                title: `${handle.platform} · ${handle.username}`,
                subtitle: handle.profileUrl,
                confidence: handle.confidence,
                entity: handle,
              };
              return (
                <ResultRow
                  key={entity.id}
                  title={entity.title}
                  subtitle={entity.subtitle}
                  confidence={entity.confidence}
                  selected={selectedId === entity.id}
                  onClick={() => onSelect(entity)}
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      {dossier.emails.length ? (
        <Section title="Emails">
          <div className="flex flex-col gap-2">
            {dossier.emails.map((email) => {
              const entity: DossierEntity = {
                kind: 'email',
                id: email,
                title: email,
                entity: email,
              };
              return (
                <ResultRow
                  key={entity.id}
                  title={entity.title}
                  subtitle="Unverified email"
                  selected={selectedId === entity.id}
                  onClick={() => onSelect(entity)}
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      {dossier.verifiedEmails.length ? (
        <Section title="Verified emails">
          <div className="flex flex-col gap-2">
            {dossier.verifiedEmails.map((email) => {
              const entity: DossierEntity = {
                kind: 'verifiedEmail',
                id: email.value,
                title: email.value,
                subtitle: `${email.status} · ${email.source}`,
                confidence: email.confidence,
                entity: email,
              };
              return (
                <ResultRow
                  key={entity.id}
                  title={entity.title}
                  subtitle={entity.subtitle}
                  confidence={entity.confidence}
                  selected={selectedId === entity.id}
                  onClick={() => onSelect(entity)}
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      {dossier.jobs.length ? (
        <Section title="Jobs">
          <div className="flex flex-col gap-2">
            {dossier.jobs.map((job) => {
              const remoteLabel = job.remote ? 'Remote' : 'On-site';
              const id = `${job.title}-${job.company}-${job.location}-${job.remote ? 'r' : 'o'}`;
              const entity: DossierEntity = {
                kind: 'job',
                id,
                title: `${job.title} · ${job.company}`,
                subtitle: `${job.location} · ${remoteLabel} · ${job.source}`,
                entity: job,
              };
              return (
                <ResultRow
                  key={entity.id}
                  title={entity.title}
                  subtitle={entity.subtitle}
                  selected={selectedId === entity.id}
                  onClick={() => onSelect(entity)}
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      {dossier.confidence.length ? (
        <Section title="Confidence">
          <div className="flex flex-col gap-2">
            {dossier.confidence.map((c) => {
              const entity: DossierEntity = {
                kind: 'confidence',
                id: c.label,
                title: c.label,
                subtitle: c.evidence.join(' · '),
                confidence: c.score,
                entity: c,
              };
              return (
                <ResultRow
                  key={entity.id}
                  title={entity.title}
                  subtitle={entity.subtitle}
                  confidence={entity.confidence}
                  selected={selectedId === entity.id}
                  onClick={() => onSelect(entity)}
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      {dossier.sources.length ? (
        <Section title="Sources">
          <div className="flex flex-col gap-2">
            {dossier.sources.map((source) => {
              const entity: DossierEntity = {
                kind: 'source',
                id: source,
                title: source,
                entity: source,
              };
              return (
                <ResultRow
                  key={entity.id}
                  title={entity.title}
                  selected={selectedId === entity.id}
                  onClick={() => onSelect(entity)}
                />
              );
            })}
          </div>
        </Section>
      ) : null}
    </div>
  );
}

