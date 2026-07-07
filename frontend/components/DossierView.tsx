import { Dossier } from '@/src/lib/types';
import { formatPercent, initialsFrom } from '@/src/lib/utils';

type DossierViewProps = {
  dossier: Dossier;
};

function EmptyState({ message }: { message: string }) {
  return <p className="muted">{message}</p>;
}

function formatTimestamp(value: string) {
  if (!value) {
    return 'Not available';
  }

  return `${value.replace('T', ' ').slice(0, 19)} UTC`;
}

export function DossierView({ dossier }: DossierViewProps) {
  const title = dossier.metadata.identifierSummary || 'Enrichment result';

  return (
    <section className="panel dossier-layout">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Merged dossier</span>
          <h2>{title}</h2>
        </div>
        <div className="meta-badges">
          {dossier.metadata.pipelineId ? <span>{dossier.metadata.pipelineId}</span> : null}
          <span>{formatTimestamp(dossier.metadata.generatedAt)}</span>
          {dossier.metadata.requestedTiers.length ? (
            <span>{dossier.metadata.requestedTiers.join(', ')}</span>
          ) : null}
        </div>
      </div>

      <div className="dossier-grid">
        <article className="card">
          <h3>Identity</h3>
          <div className="photo-row">
            <div className="avatar-fallback">{initialsFrom(title)}</div>
            <div>
              <p className="label">LinkedIn photo asset</p>
              {dossier.photo ? (
                <>
                  <a href={dossier.photo.assetUrl} target="_blank" rel="noreferrer">
                    {dossier.photo.assetUrl}
                  </a>
                  <p className="muted">
                    Source {dossier.photo.source} • Captured {formatTimestamp(dossier.photo.capturedAt)} • Confidence{' '}
                    {formatPercent(dossier.photo.confidence)}
                  </p>
                </>
              ) : (
                <EmptyState message="No LinkedIn photo returned by the enrichment pipeline." />
              )}
            </div>
          </div>
          {dossier.emails.length ? (
            <ul className="list">
              {dossier.emails.map((email) => (
                <li key={email}>{email}</li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No email addresses returned." />
          )}
        </article>

        <article className="card">
          <h3>Handles</h3>
          {dossier.handles.length ? (
            <ul className="list compact">
              {dossier.handles.map((handle) => (
                <li key={`${handle.platform}-${handle.username}`}>
                  <strong>{handle.platform}</strong>
                  <span>{handle.username}</span>
                  <a href={handle.profileUrl} target="_blank" rel="noreferrer">
                    {handle.profileUrl}
                  </a>
                  <em>{formatPercent(handle.confidence)}</em>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No social handles returned." />
          )}
        </article>

        <article className="card">
          <h3>Verified email intelligence</h3>
          {dossier.verifiedEmails.length ? (
            <ul className="list compact">
              {dossier.verifiedEmails.map((email) => (
                <li key={email.value}>
                  <strong>{email.value}</strong>
                  <span>{email.status}</span>
                  <em>{email.source}</em>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No verified email intelligence returned." />
          )}
        </article>

        <article className="card">
          <h3>Employment & organizations</h3>
          {dossier.github?.profile ? (
            <p className="label">
              GitHub profile:{' '}
              <a href={dossier.github.profile} target="_blank" rel="noreferrer">
                {dossier.github.profile}
              </a>
            </p>
          ) : null}
          {(dossier.github?.organizations ?? []).length ? (
            <ul className="list">
              {dossier.github?.organizations.map((org) => (
                <li key={org}>{org}</li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No organizations returned." />
          )}
          <p className="muted">Public commits observed: {dossier.github?.publicCommits ?? 0}</p>
          {dossier.coworkers.length ? (
            <ul className="list">
              {dossier.coworkers.map((coworker) => (
                <li key={coworker}>{coworker}</li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No coworkers returned." />
          )}
        </article>

        <article className="card span-2">
          <h3>Source signals</h3>
          {dossier.sources.length ? (
            <ul className="list compact">
              {dossier.sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No enrichment sources recorded for this dossier." />
          )}
        </article>

        <article className="card span-2">
          <h3>Confidence engine</h3>
          {dossier.confidence.length ? (
            <div className="confidence-list">
              {dossier.confidence.map((item) => (
                <div key={item.label} className="confidence-item">
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.evidence.join(' • ')}</p>
                  </div>
                  <span>{formatPercent(item.score)}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No confidence scoring returned." />
          )}
        </article>

        <article className="card span-2">
          <h3>Jobs & business intelligence</h3>
          <div className="split-columns">
            <div>
              <p className="label">Jobs</p>
              {dossier.jobs.length ? (
                <ul className="list compact">
                  {dossier.jobs.map((job) => (
                    <li key={`${job.title}-${job.company}-${job.location}`}>
                      <strong>{job.title}</strong>
                      <span>{job.company}</span>
                      <em>{job.location}</em>
                      <span>{job.remote ? 'Remote' : 'On-site'}</span>
                      <span>{job.source}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState message="No job listings returned." />
              )}
            </div>
            <div>
              <p className="label">Business</p>
              {dossier.business ? (
                <ul className="list">
                  <li>{dossier.business.name}</li>
                  <li>{dossier.business.address}</li>
                  <li>
                    <a href={dossier.business.website} target="_blank" rel="noreferrer">
                      {dossier.business.website}
                    </a>
                  </li>
                  <li>{dossier.business.phone}</li>
                  <li>Rating: {dossier.business.rating}</li>
                </ul>
              ) : (
                <EmptyState message="No business profile returned." />
              )}
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
