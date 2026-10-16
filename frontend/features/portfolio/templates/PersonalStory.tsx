import type { PortfolioTemplateProps } from "./types";
import { displayNameOf, ExternalLink, visibleSections } from "./sections";

export function PersonalStory({ model }: PortfolioTemplateProps) {
  const { content, sectionOrder, sectionVisibility } = model;
  const sections = visibleSections(sectionOrder, sectionVisibility, content);
  const name = displayNameOf(content);

  const milestones = [
    ...content.experience.map((job) => ({
      id: `exp-${job.id}`,
      label: job.title,
      detail: job.company,
      when: [job.startDate, job.isCurrent ? "Present" : job.endDate].filter(Boolean).join(" – "),
      body: job.description,
    })),
    ...content.education.map((ed) => ({
      id: `edu-${ed.id}`,
      label: ed.institution,
      detail: [ed.degree, ed.fieldOfStudy].filter(Boolean).join(" · "),
      when: ed.endYear || ed.startYear || "",
      body: ed.description,
    })),
    ...content.certifications.map((cert) => ({
      id: `cert-${cert.id}`,
      label: cert.title,
      detail: cert.issuer || "",
      when: cert.year || "",
      body: null as string | null,
    })),
  ];

  return (
    <div
      className="min-h-full"
      style={{
        background: "var(--pf-bg)",
        color: "var(--pf-text)",
        fontFamily: "var(--pf-font-body)",
      }}
    >
      <article className="mx-auto max-w-3xl px-6 py-16 sm:px-8 sm:py-24">
        <p className="text-sm italic" style={{ color: "var(--pf-muted)" }}>
          A personal introduction
        </p>
        <h1
          className="mt-4 text-4xl leading-tight tracking-tight sm:text-6xl"
          style={{ fontFamily: "var(--pf-font-display)" }}
        >
          {content.headline || `The story of ${name}`}
        </h1>
        <p className="mt-6 text-xl leading-8" style={{ color: "var(--pf-muted)" }}>
          {content.summary || content.professionalRole || ""}
        </p>
        <div
          className="mt-8 flex flex-wrap items-center gap-4 text-sm"
          style={{ color: "var(--pf-muted)" }}
        >
          <span className="font-medium" style={{ color: "var(--pf-text)" }}>
            {name}
          </span>
          {content.location && <span>· {content.location}</span>}
          {content.email && (
            <a href={`mailto:${content.email}`} className="underline-offset-4 hover:underline">
              {content.email}
            </a>
          )}
        </div>

        {sections.includes("about") && (
          <section className="mt-16 space-y-4">
            <h2 className="text-2xl" style={{ fontFamily: "var(--pf-font-display)" }}>
              Where I come from
            </h2>
            <p
              className="whitespace-pre-wrap text-lg leading-8"
              style={{ color: "var(--pf-muted)" }}
            >
              {content.about || content.summary}
            </p>
          </section>
        )}

        {milestones.length > 0 &&
          (sections.includes("experience") ||
            sections.includes("education") ||
            sections.includes("certifications")) && (
            <section className="mt-16">
              <h2 className="mb-8 text-2xl" style={{ fontFamily: "var(--pf-font-display)" }}>
                The journey so far
              </h2>
              <div className="space-y-10">
                {milestones.map((m, idx) => (
                  <div
                    key={m.id}
                    className="grid gap-2 border-t pt-8 sm:grid-cols-[7rem_1fr]"
                    style={{ borderColor: "var(--pf-border)" }}
                  >
                    <div className="text-sm" style={{ color: "var(--pf-muted)" }}>
                      {m.when || `Chapter ${idx + 1}`}
                    </div>
                    <div>
                      <h3 className="text-xl" style={{ fontFamily: "var(--pf-font-display)" }}>
                        {m.label}
                      </h3>
                      {m.detail && (
                        <p
                          className="mt-1 text-sm font-medium"
                          style={{ color: "var(--pf-accent)" }}
                        >
                          {m.detail}
                        </p>
                      )}
                      {m.body && (
                        <p className="mt-3 leading-7" style={{ color: "var(--pf-muted)" }}>
                          {m.body}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

        {sections.includes("projects") && (
          <section className="mt-16">
            <h2 className="mb-8 text-2xl" style={{ fontFamily: "var(--pf-font-display)" }}>
              Work I&apos;m proud of
            </h2>
            <div className="space-y-8">
              {content.projects.map((project) => (
                <article key={project.id}>
                  <h3 className="text-xl font-medium">{project.title}</h3>
                  {project.description && (
                    <p className="mt-2 leading-7" style={{ color: "var(--pf-muted)" }}>
                      {project.description}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-4 text-sm">
                    {project.demoUrl && (
                      <ExternalLink href={project.demoUrl}>See it live</ExternalLink>
                    )}
                    {project.repoUrl && <ExternalLink href={project.repoUrl}>Source</ExternalLink>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {sections.includes("skills") && (
          <section className="mt-16">
            <h2 className="mb-4 text-2xl" style={{ fontFamily: "var(--pf-font-display)" }}>
              What I bring
            </h2>
            <p className="leading-8" style={{ color: "var(--pf-muted)" }}>
              {content.skills.map((s) => s.name).join(" · ")}
            </p>
          </section>
        )}

        {(sections.includes("social") || sections.includes("contact")) && (
          <section className="mt-16 border-t pt-10" style={{ borderColor: "var(--pf-border)" }}>
            <h2 className="mb-4 text-2xl" style={{ fontFamily: "var(--pf-font-display)" }}>
              Let&apos;s continue the conversation
            </h2>
            <div className="flex flex-wrap gap-4 text-sm">
              {content.resumeUrl && <ExternalLink href={content.resumeUrl}>Resume</ExternalLink>}
              {content.socialLinks.map((link) => (
                <ExternalLink key={link.id} href={link.url}>
                  {link.label || link.platform}
                </ExternalLink>
              ))}
            </div>
          </section>
        )}
      </article>
    </div>
  );
}
