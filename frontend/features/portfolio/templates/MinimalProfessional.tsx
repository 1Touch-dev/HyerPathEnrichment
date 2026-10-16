import type { PortfolioTemplateProps } from "./types";
import { displayNameOf, ExternalLink, visibleSections } from "./sections";

export function MinimalProfessional({ model }: PortfolioTemplateProps) {
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
      <div className="mx-auto max-w-3xl px-6 py-16 sm:px-10 sm:py-24">
        <header className="space-y-6 border-b pb-12" style={{ borderColor: "var(--pf-border)" }}>
          <p
            className="text-xs font-medium uppercase tracking-[0.22em]"
            style={{ color: "var(--pf-muted)" }}
          >
            {content.professionalRole || content.location || "Portfolio"}
          </p>
          <h1
            className="text-4xl font-semibold tracking-tight sm:text-5xl"
            style={{ fontFamily: "var(--pf-font-display)" }}
          >
            {content.headline || name}
          </h1>
          {content.summary && (
            <p className="max-w-2xl text-lg leading-relaxed" style={{ color: "var(--pf-muted)" }}>
              {content.summary}
            </p>
          )}
          <div className="flex flex-wrap gap-4 text-sm" style={{ color: "var(--pf-muted)" }}>
            {content.displayName && <span>{content.displayName}</span>}
            {content.location && <span>· {content.location}</span>}
          </div>
        </header>

        <div className="space-y-16 pt-14">
          {sections.map((key) => {
            if (key === "about") {
              return (
                <section key={key} className="space-y-4">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    About
                  </h2>
                  <p className="whitespace-pre-wrap text-base leading-7">
                    {content.about || content.summary}
                  </p>
                </section>
              );
            }
            if (key === "projects") {
              return (
                <section key={key} className="space-y-6">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Selected work
                  </h2>
                  <div className="space-y-4">
                    {[...content.projects]
                      .sort((a, b) => a.displayOrder - b.displayOrder)
                      .map((project) => (
                        <article
                          key={project.id}
                          className="rounded-2xl border p-6"
                          style={{
                            background: "var(--pf-surface)",
                            borderColor: "var(--pf-border)",
                          }}
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <h3 className="text-xl font-semibold">{project.title}</h3>
                            <div className="flex gap-3 text-sm">
                              {project.demoUrl && (
                                <ExternalLink
                                  href={project.demoUrl}
                                  className="underline-offset-4 hover:underline"
                                >
                                  Live
                                </ExternalLink>
                              )}
                              {project.repoUrl && (
                                <ExternalLink
                                  href={project.repoUrl}
                                  className="underline-offset-4 hover:underline"
                                >
                                  Code
                                </ExternalLink>
                              )}
                            </div>
                          </div>
                          {project.description && (
                            <p
                              className="mt-3 text-sm leading-6"
                              style={{ color: "var(--pf-muted)" }}
                            >
                              {project.description}
                            </p>
                          )}
                          {project.techStack.length > 0 && (
                            <p
                              className="mt-4 text-xs tracking-wide"
                              style={{ color: "var(--pf-muted)" }}
                            >
                              {project.techStack.join(" · ")}
                            </p>
                          )}
                        </article>
                      ))}
                  </div>
                </section>
              );
            }
            if (key === "experience") {
              return (
                <section key={key} className="space-y-6">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Experience
                  </h2>
                  <div className="space-y-8">
                    {[...content.experience]
                      .sort((a, b) => a.displayOrder - b.displayOrder)
                      .map((job) => (
                        <div key={job.id}>
                          <div className="flex flex-wrap justify-between gap-2">
                            <h3 className="font-semibold">
                              {job.title} · {job.company}
                            </h3>
                            <span className="text-sm" style={{ color: "var(--pf-muted)" }}>
                              {[job.startDate, job.isCurrent ? "Present" : job.endDate]
                                .filter(Boolean)
                                .join(" – ")}
                            </span>
                          </div>
                          {job.description && (
                            <p
                              className="mt-2 text-sm leading-6"
                              style={{ color: "var(--pf-muted)" }}
                            >
                              {job.description}
                            </p>
                          )}
                        </div>
                      ))}
                  </div>
                </section>
              );
            }
            if (key === "education") {
              return (
                <section key={key} className="space-y-4">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Education
                  </h2>
                  {[...content.education]
                    .sort((a, b) => a.displayOrder - b.displayOrder)
                    .map((ed) => (
                      <div key={ed.id}>
                        <h3 className="font-semibold">{ed.institution}</h3>
                        <p className="text-sm" style={{ color: "var(--pf-muted)" }}>
                          {[ed.degree, ed.fieldOfStudy, ed.endYear].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                    ))}
                </section>
              );
            }
            if (key === "skills") {
              return (
                <section key={key} className="space-y-4">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Skills
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {content.skills.map((skill) => (
                      <span
                        key={skill.id}
                        className="rounded-full border px-3 py-1 text-sm"
                        style={{ borderColor: "var(--pf-border)" }}
                      >
                        {skill.name}
                      </span>
                    ))}
                  </div>
                </section>
              );
            }
            if (key === "certifications") {
              return (
                <section key={key} className="space-y-4">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Certifications
                  </h2>
                  {content.certifications.map((cert) => (
                    <div key={cert.id} className="text-sm">
                      <span className="font-medium">{cert.title}</span>
                      {(cert.issuer || cert.year) && (
                        <span style={{ color: "var(--pf-muted)" }}>
                          {" "}
                          — {[cert.issuer, cert.year].filter(Boolean).join(", ")}
                        </span>
                      )}
                    </div>
                  ))}
                </section>
              );
            }
            if (key === "social") {
              return (
                <section key={key} className="space-y-3">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Links
                  </h2>
                  <div className="flex flex-wrap gap-4 text-sm">
                    {content.socialLinks.map((link) => (
                      <ExternalLink
                        key={link.id}
                        href={link.url}
                        className="underline-offset-4 hover:underline"
                      >
                        {link.label || link.platform}
                      </ExternalLink>
                    ))}
                  </div>
                </section>
              );
            }
            if (key === "contact") {
              return (
                <section key={key} className="space-y-3">
                  <h2
                    className="text-sm font-semibold uppercase tracking-[0.18em]"
                    style={{ color: "var(--pf-muted)" }}
                  >
                    Contact
                  </h2>
                  <div className="flex flex-wrap gap-4 text-sm">
                    {content.email && (
                      <a
                        href={`mailto:${content.email}`}
                        className="underline-offset-4 hover:underline"
                      >
                        {content.email}
                      </a>
                    )}
                    {content.resumeUrl && (
                      <ExternalLink
                        href={content.resumeUrl}
                        className="underline-offset-4 hover:underline"
                      >
                        Resume
                      </ExternalLink>
                    )}
                  </div>
                </section>
              );
            }
            return null;
          })}
        </div>
      </div>
    </div>
  );
}
