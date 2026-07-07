import { Dossier } from '@/src/lib/types';
import { formatPercent, initialsFrom } from '@/src/lib/utils';

type DossierViewProps = {
  dossier: Dossier;
};

export function DossierView({ dossier }: DossierViewProps) {
  return (
    <section className="panel dossier-layout">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Merged dossier</span>
          <h2>{dossier.metadata.identifierSummary || 'Unified result set'}</h2>
        </div>
        <div className="meta-badges">
          <span>{dossier.metadata.pipelineId}</span>
          <span>{dossier.metadata.generatedAt.replace('T', ' ').slice(0, 19)} UTC</span>
        </div>
      </div>

      <div className="dossier-grid">
        <article className="card">
          <h3>Identity</h3>
          <div className="photo-row">
            <div className="avatar-fallback">{initialsFrom(dossier.metadata.identifierSummary || 'HP')}</div>
            <div>
              <p className="label">LinkedIn photo asset</p>
              <a href={dossier.photo?.assetUrl || '#'}>{dossier.photo?.assetUrl || 'Not requested'}</a>
              <p className="muted">Confidence {formatPercent(dossier.photo?.confidence || 0)}</p>
            </div>
          </div>
          <ul className="list">
            {dossier.emails.map((email) => (
              <li key={email}>{email}</li>
            ))}
          </ul>
        </article>

        <article className="card">
          <h3>Handles</h3>
          <ul className="list compact">
            {dossier.handles.map((handle) => (
              <li key={`${handle.platform}-${handle.username}`}>
                <strong>{handle.platform}</strong>
                <span>{handle.username}</span>
                <em>{formatPercent(handle.confidence)}</em>
              </li>
            ))}
          </ul>
        </article>

        <article className="card">
          <h3>Verified email intelligence</h3>
          <ul className="list compact">
            {dossier.verifiedEmails.map((email) => (
              <li key={email.value}>
                <strong>{email.value}</strong>
                <span>{email.status}</span>
                <em>{email.source}</em>
              </li>
            ))}
          </ul>
        </article>

        <article className="card">
          <h3>Employment & organizations</h3>
          <ul className="list">
            {(dossier.github?.organizations ?? []).map((org) => (
              <li key={org}>{org}</li>
            ))}
          </ul>
          <p className="muted">Public commits observed: {dossier.github?.publicCommits ?? 0}</p>
        </article>

        <article className="card span-2">
          <h3>Confidence engine</h3>
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
        </article>

        <article className="card span-2">
          <h3>Jobs & business intelligence</h3>
          <div className="split-columns">
            <div>
              <p className="label">Jobs</p>
              <ul className="list compact">
                {dossier.jobs.map((job) => (
                  <li key={`${job.title}-${job.company}`}>
                    <strong>{job.title}</strong>
                    <span>{job.company}</span>
                    <em>{job.location}</em>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="label">Business</p>
              {dossier.business ? (
                <ul className="list">
                  <li>{dossier.business.name}</li>
                  <li>{dossier.business.address}</li>
                  <li>{dossier.business.website}</li>
                  <li>{dossier.business.phone}</li>
                </ul>
              ) : (
                <p className="muted">No business query supplied.</p>
              )}
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
