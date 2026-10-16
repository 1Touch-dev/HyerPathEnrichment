import type { PortfolioTemplateProps } from "./types";
import { displayNameOf, ExternalLink, visibleSections } from "./sections";

export function DeveloperDark({ model }: PortfolioTemplateProps) {
  const { content, sectionOrder, sectionVisibility } = model;
  const sections = visibleSections(sectionOrder, sectionVisibility, content);
  const name = displayNameOf(content);

  return (
    <div
      className="min-h-full"
      style={{
        background: "var(--pf-bg)",
        color: "var(--pf-text)",
        fontFamily: "var(--pf-font-body)",
      }}
    >
      <div
        className="border-b px-4 py-3 text-xs"
        style={{ borderColor: "var(--pf-border)", color: "var(--pf-muted)" }}
      >
        <span style={{ color: "var(--pf-accent)" }}>~/</span>
        portfolio
        <span className="mx-2 opacity-40">·</span>
        {content.professionalRole || "developer"}
      </div>

      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 lg:grid-cols-[240px_minmax(0,1fr)] lg:px-8 lg:py-16">
        <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
          <div>
            <p className="font-mono text-xs" style={{ color: "var(--pf-accent)" }}>
              const engineer =
            </p>
            <h1
              className="mt-2 text-3xl font-bold"
              style={{ fontFamily: "var(--pf-font-display)" }}
            >
              {name}
            </h1>
            <p className="mt-2 text-sm" style={{ color: "var(--pf-muted)" }}>
              {content.headline || content.professionalRole || "Building reliable systems"}
            </p>
          </div>
          {content.location && (
            <p className="font-mono text-xs" style={{ color: "var(--pf-muted)" }}>
              loc: {content.location}
            </p>
          )}
          {sections.includes("skills") && (
            <div>
              <h2
                className="mb-3 font-mono text-xs uppercase tracking-wider"
                style={{ color: "var(--pf-muted)" }}
              >
                stack
              </h2>
              <div className="flex flex-wrap gap-2">
                {content.skills.map((skill) => (
                  <span
                    key={skill.id}
                    className="rounded border px-2 py-1 font-mono text-[11px]"
                    style={{ borderColor: "var(--pf-border)", color: "var(--pf-accent)" }}
                  >
                    {skill.name}
                  </span>
                ))}
              </div>
            </div>
          )}
          {sections.includes("social") && (
            <div className="space-y-2 font-mono text-xs">
              {content.socialLinks.map((link) => (
                <div key={link.id}>
                  <ExternalLink
                    href={link.url}
                    className="hover:underline"
                    style={{ color: "var(--pf-accent)" }}
                  >
                    {link.platform}
                  </ExternalLink>
                </div>
              ))}
            </div>
          )}
          {sections.includes("contact") && (
            <div className="space-y-2 text-sm">
              {content.email && (
                <a href={`mailto:${content.email}`} className="block hover:underline">
                  {content.email}
                </a>
              )}
              {content.resumeUrl && (
                <ExternalLink href={content.resumeUrl} className="block hover:underline">
                  resume.pdf
                </ExternalLink>
              )}
            </div>
          )}
        </aside>

        <main className="space-y-12">
          {sections.includes("about") && (
            <section
              className="rounded-xl border p-5"
              style={{ borderColor: "var(--pf-border)", background: "var(--pf-surface)" }}
            >
              <h2 className="mb-3 font-mono text-xs" style={{ color: "var(--pf-accent)" }}>
                // about
              </h2>
              <p
                className="whitespace-pre-wrap text-sm leading-7"
                style={{ color: "var(--pf-muted)" }}
              >
                {content.about || content.summary}
              </p>
            </section>
          )}

          {sections.includes("projects") && (
            <section>
              <h2 className="mb-4 font-mono text-xs" style={{ color: "var(--pf-accent)" }}>
                // projects
              </h2>
              <div className="space-y-4">
                {[...content.projects]
                  .sort((a, b) => a.displayOrder - b.displayOrder)
                  .map((project) => (
                    <article
                      key={project.id}
                      className="rounded-xl border p-5"
                      style={{ borderColor: "var(--pf-border)", background: "var(--pf-surface)" }}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-lg font-semibold">{project.title}</h3>
                        <div className="flex gap-3 font-mono text-xs">
                          {project.repoUrl && (
                            <ExternalLink
                              href={project.repoUrl}
                              className="hover:underline"
                              style={{ color: "var(--pf-accent)" }}
                            >
                              repo
                            </ExternalLink>
                          )}
                          {project.demoUrl && (
                            <ExternalLink
                              href={project.demoUrl}
                              className="hover:underline"
                              style={{ color: "var(--pf-accent)" }}
                            >
                              demo
                            </ExternalLink>
                          )}
                        </div>
                      </div>
                      {project.description && (
                        <p className="mt-3 text-sm leading-6" style={{ color: "var(--pf-muted)" }}>
                          {project.description}
                        </p>
                      )}
                      {project.techStack.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {project.techStack.map((tech) => (
                            <span
                              key={tech}
                              className="rounded bg-black/30 px-2 py-0.5 font-mono text-[11px]"
                              style={{ color: "var(--pf-accent)" }}
                            >
                              {tech}
                            </span>
                          ))}
                        </div>
                      )}
                    </article>
                  ))}
              </div>
            </section>
          )}

          {sections.includes("experience") && (
            <section>
              <h2 className="mb-4 font-mono text-xs" style={{ color: "var(--pf-accent)" }}>
                // experience
              </h2>
              <div className="space-y-5">
                {content.experience.map((job) => (
                  <div
                    key={job.id}
                    className="border-l-2 pl-4"
                    style={{ borderColor: "var(--pf-accent)" }}
                  >
                    <h3 className="font-semibold">
                      {job.title} @ {job.company}
                    </h3>
                    <p className="font-mono text-xs" style={{ color: "var(--pf-muted)" }}>
                      {[job.startDate, job.isCurrent ? "present" : job.endDate]
                        .filter(Boolean)
                        .join(" → ")}
                    </p>
                    {job.description && (
                      <p className="mt-2 text-sm" style={{ color: "var(--pf-muted)" }}>
                        {job.description}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.includes("education") && (
            <section>
              <h2 className="mb-4 font-mono text-xs" style={{ color: "var(--pf-accent)" }}>
                // education
              </h2>
              {content.education.map((ed) => (
                <div key={ed.id} className="mb-3">
                  <h3 className="font-semibold">{ed.institution}</h3>
                  <p className="text-sm" style={{ color: "var(--pf-muted)" }}>
                    {[ed.degree, ed.fieldOfStudy, ed.endYear].filter(Boolean).join(" · ")}
                  </p>
                </div>
              ))}
            </section>
          )}

          {sections.includes("certifications") && (
            <section>
              <h2 className="mb-4 font-mono text-xs" style={{ color: "var(--pf-accent)" }}>
                // certifications
              </h2>
              {content.certifications.map((cert) => (
                <div key={cert.id} className="mb-2 text-sm">
                  <span className="font-medium">{cert.title}</span>
                  {cert.issuer && (
                    <span style={{ color: "var(--pf-muted)" }}> — {cert.issuer}</span>
                  )}
                </div>
              ))}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
