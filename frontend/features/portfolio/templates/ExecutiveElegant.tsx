import type { PortfolioTemplateProps } from "./types";
import { displayNameOf, ExternalLink, visibleSections } from "./sections";

export function ExecutiveElegant({ model }: PortfolioTemplateProps) {
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
      <header
        className="border-b"
        style={{
          borderColor: "var(--pf-border)",
          background:
            "linear-gradient(180deg, color-mix(in srgb, var(--pf-accent) 12%, var(--pf-bg)), var(--pf-bg))",
        }}
      >
        <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-14 sm:flex-row sm:items-end sm:justify-between sm:px-10 sm:py-20">
          <div className="space-y-3">
            <p
              className="text-xs font-semibold uppercase tracking-[0.28em]"
              style={{ color: "var(--pf-accent)" }}
            >
              Professional profile
            </p>
            <h1
              className="text-4xl font-semibold tracking-tight sm:text-5xl"
              style={{ fontFamily: "var(--pf-font-display)" }}
            >
              {name}
            </h1>
            <p className="text-lg" style={{ color: "var(--pf-muted)" }}>
              {[content.professionalRole || content.headline, content.location]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            {content.email && (
              <a
                href={`mailto:${content.email}`}
                className="rounded-md px-4 py-2 font-medium text-white"
                style={{ background: "var(--pf-accent)" }}
              >
                Contact
              </a>
            )}
            {content.resumeUrl && (
              <ExternalLink
                href={content.resumeUrl}
                className="rounded-md border px-4 py-2 font-medium"
                style={{ borderColor: "var(--pf-border)" }}
              >
                Download CV
              </ExternalLink>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-12 px-6 py-12 sm:px-10 lg:grid-cols-[1.4fr_0.9fr]">
        <div className="space-y-12">
          {sections.includes("about") && (
            <section>
              <h2
                className="mb-4 text-sm font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--pf-accent)" }}
              >
                Profile summary
              </h2>
              <p
                className="whitespace-pre-wrap text-base leading-7"
                style={{ color: "var(--pf-muted)" }}
              >
                {content.about || content.summary}
              </p>
            </section>
          )}

          {sections.includes("experience") && (
            <section>
              <h2
                className="mb-6 text-sm font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--pf-accent)" }}
              >
                Experience
              </h2>
              <ol
                className="relative space-y-8 border-l pl-6"
                style={{ borderColor: "var(--pf-border)" }}
              >
                {[...content.experience]
                  .sort((a, b) => a.displayOrder - b.displayOrder)
                  .map((job) => (
                    <li key={job.id} className="relative">
                      <span
                        className="absolute -left-[1.91rem] top-1.5 h-3 w-3 rounded-full border-2"
                        style={{ borderColor: "var(--pf-accent)", background: "var(--pf-bg)" }}
                      />
                      <div className="flex flex-wrap justify-between gap-2">
                        <h3 className="text-lg font-semibold">{job.title}</h3>
                        <span className="text-sm" style={{ color: "var(--pf-muted)" }}>
                          {[job.startDate, job.isCurrent ? "Present" : job.endDate]
                            .filter(Boolean)
                            .join(" – ")}
                        </span>
                      </div>
                      <p className="text-sm font-medium" style={{ color: "var(--pf-accent)" }}>
                        {job.company}
                        {job.location ? ` · ${job.location}` : ""}
                      </p>
                      {job.description && (
                        <p className="mt-2 text-sm leading-6" style={{ color: "var(--pf-muted)" }}>
                          {job.description}
                        </p>
                      )}
                      {job.achievements.length > 0 && (
                        <ul
                          className="mt-3 list-disc space-y-1 pl-5 text-sm"
                          style={{ color: "var(--pf-muted)" }}
                        >
                          {job.achievements.map((a) => (
                            <li key={a}>{a}</li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
              </ol>
            </section>
          )}

          {sections.includes("projects") && (
            <section>
              <h2
                className="mb-4 text-sm font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--pf-accent)" }}
              >
                Selected initiatives
              </h2>
              <div className="space-y-4">
                {content.projects.map((project) => (
                  <article
                    key={project.id}
                    className="rounded-lg border p-5"
                    style={{ borderColor: "var(--pf-border)", background: "var(--pf-surface)" }}
                  >
                    <h3 className="font-semibold">{project.title}</h3>
                    {project.description && (
                      <p className="mt-2 text-sm" style={{ color: "var(--pf-muted)" }}>
                        {project.description}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-10">
          {sections.includes("skills") && (
            <section
              className="rounded-lg border p-5"
              style={{ borderColor: "var(--pf-border)", background: "var(--pf-surface)" }}
            >
              <h2
                className="mb-4 text-sm font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--pf-accent)" }}
              >
                Capabilities
              </h2>
              <ul className="space-y-2 text-sm">
                {content.skills.map((skill) => (
                  <li
                    key={skill.id}
                    className="flex justify-between gap-3 border-b py-2 last:border-0"
                    style={{ borderColor: "var(--pf-border)" }}
                  >
                    <span>{skill.name}</span>
                    {skill.level && <span style={{ color: "var(--pf-muted)" }}>{skill.level}</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {sections.includes("education") && (
            <section>
              <h2
                className="mb-4 text-sm font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--pf-accent)" }}
              >
                Education
              </h2>
              <div className="space-y-4">
                {content.education.map((ed) => (
                  <div key={ed.id}>
                    <h3 className="font-semibold">{ed.institution}</h3>
                    <p className="text-sm" style={{ color: "var(--pf-muted)" }}>
                      {[ed.degree, ed.fieldOfStudy, ed.endYear].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.includes("certifications") && (
            <section>
              <h2
                className="mb-4 text-sm font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--pf-accent)" }}
              >
                Credentials
              </h2>
              <div className="space-y-3 text-sm">
                {content.certifications.map((cert) => (
                  <div key={cert.id}>
                    <p className="font-medium">{cert.title}</p>
                    <p style={{ color: "var(--pf-muted)" }}>
                      {[cert.issuer, cert.year].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.includes("social") && (
            <section className="space-y-2 text-sm">
              {content.socialLinks.map((link) => (
                <ExternalLink key={link.id} href={link.url} className="block hover:underline">
                  {link.label || link.platform}
                </ExternalLink>
              ))}
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
