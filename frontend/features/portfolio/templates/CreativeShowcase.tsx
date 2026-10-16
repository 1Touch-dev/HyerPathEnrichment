import type { PortfolioTemplateProps } from "./types";
import { displayNameOf, ExternalLink, visibleSections } from "./sections";

export function CreativeShowcase({ model }: PortfolioTemplateProps) {
  const { content, sectionOrder, sectionVisibility } = model;
  const sections = visibleSections(sectionOrder, sectionVisibility, content);
  const name = displayNameOf(content);

  return (
    <div
      className="min-h-full overflow-hidden"
      style={{
        background:
          "radial-gradient(circle at 10% 10%, color-mix(in srgb, var(--pf-accent) 35%, transparent), transparent 40%), radial-gradient(circle at 90% 0%, color-mix(in srgb, var(--pf-accent) 25%, transparent), transparent 35%), var(--pf-bg)",
        color: "var(--pf-text)",
        fontFamily: "var(--pf-font-body)",
      }}
    >
      <section className="relative px-6 pb-16 pt-20 sm:px-12 sm:pb-24 sm:pt-28">
        <p
          className="mb-4 text-sm uppercase tracking-[0.35em]"
          style={{ color: "var(--pf-muted)" }}
        >
          Creative portfolio
        </p>
        <h1
          className="max-w-4xl text-5xl font-black leading-[0.95] tracking-tight sm:text-7xl"
          style={{ fontFamily: "var(--pf-font-display)" }}
        >
          {content.headline || `Hello, I'm ${name}.`}
        </h1>
        <p className="mt-6 max-w-xl text-lg" style={{ color: "var(--pf-muted)" }}>
          {content.summary || content.professionalRole || "Building bold digital experiences."}
        </p>
        {(content.email || content.resumeUrl) && (
          <div className="mt-8 flex flex-wrap gap-3">
            {content.resumeUrl && (
              <ExternalLink
                href={content.resumeUrl}
                className="rounded-full px-5 py-2.5 text-sm font-semibold"
                style={{ background: "var(--pf-accent)", color: "#111" }}
              >
                View resume
              </ExternalLink>
            )}
            {content.email && (
              <a
                href={`mailto:${content.email}`}
                className="rounded-full border px-5 py-2.5 text-sm font-semibold"
                style={{ borderColor: "var(--pf-border)" }}
              >
                Contact
              </a>
            )}
          </div>
        )}
      </section>

      <div className="space-y-20 px-6 pb-24 sm:px-12">
        {sections.includes("projects") && (
          <section>
            <h2
              className="mb-8 text-3xl font-bold"
              style={{ fontFamily: "var(--pf-font-display)" }}
            >
              Featured projects
            </h2>
            <div className="grid gap-6 md:grid-cols-2">
              {[...content.projects]
                .sort((a, b) => a.displayOrder - b.displayOrder)
                .map((project, idx) => (
                  <article
                    key={project.id}
                    className={`overflow-hidden rounded-3xl border ${idx === 0 ? "md:col-span-2" : ""}`}
                    style={{ background: "var(--pf-surface)", borderColor: "var(--pf-border)" }}
                  >
                    {project.imageUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={project.imageUrl}
                        alt={project.title}
                        className={`w-full object-cover ${idx === 0 ? "h-64 sm:h-80" : "h-48"}`}
                      />
                    ) : (
                      <div
                        className={`flex items-end p-6 ${idx === 0 ? "h-48 sm:h-64" : "h-36"}`}
                        style={{
                          background: `linear-gradient(135deg, color-mix(in srgb, var(--pf-accent) 55%, #000), transparent)`,
                        }}
                      >
                        <span className="text-4xl font-black opacity-40">
                          {String(idx + 1).padStart(2, "0")}
                        </span>
                      </div>
                    )}
                    <div className="space-y-3 p-6">
                      <h3 className="text-2xl font-bold">{project.title}</h3>
                      {project.description && (
                        <p className="text-sm leading-6" style={{ color: "var(--pf-muted)" }}>
                          {project.description}
                        </p>
                      )}
                      {project.techStack.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {project.techStack.map((tech) => (
                            <span
                              key={tech}
                              className="rounded-full px-3 py-1 text-xs font-medium"
                              style={{
                                background: "color-mix(in srgb, var(--pf-accent) 20%, transparent)",
                              }}
                            >
                              {tech}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex gap-4 pt-1 text-sm font-semibold">
                        {project.demoUrl && (
                          <ExternalLink href={project.demoUrl}>Live demo →</ExternalLink>
                        )}
                        {project.repoUrl && (
                          <ExternalLink href={project.repoUrl}>Repository →</ExternalLink>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
            </div>
          </section>
        )}

        {sections.includes("about") && (
          <section className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
            <h2 className="text-3xl font-bold" style={{ fontFamily: "var(--pf-font-display)" }}>
              About me
            </h2>
            <p
              className="whitespace-pre-wrap text-lg leading-8"
              style={{ color: "var(--pf-muted)" }}
            >
              {content.about || content.summary}
            </p>
          </section>
        )}

        {sections.includes("skills") && (
          <section>
            <h2 className="mb-6 text-3xl font-bold">Skills</h2>
            <div className="flex flex-wrap gap-3">
              {content.skills.map((skill) => (
                <span
                  key={skill.id}
                  className="rounded-2xl border px-4 py-2 text-sm font-medium"
                  style={{ borderColor: "var(--pf-border)" }}
                >
                  {skill.name}
                </span>
              ))}
            </div>
          </section>
        )}

        {(sections.includes("experience") || sections.includes("education")) && (
          <section className="grid gap-10 md:grid-cols-2">
            {sections.includes("experience") && (
              <div>
                <h2 className="mb-4 text-2xl font-bold">Experience</h2>
                <div className="space-y-5">
                  {content.experience.map((job) => (
                    <div key={job.id}>
                      <h3 className="font-semibold">{job.title}</h3>
                      <p className="text-sm" style={{ color: "var(--pf-muted)" }}>
                        {job.company}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {sections.includes("education") && (
              <div>
                <h2 className="mb-4 text-2xl font-bold">Education</h2>
                <div className="space-y-5">
                  {content.education.map((ed) => (
                    <div key={ed.id}>
                      <h3 className="font-semibold">{ed.institution}</h3>
                      <p className="text-sm" style={{ color: "var(--pf-muted)" }}>
                        {[ed.degree, ed.endYear].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {sections.includes("social") && (
          <section className="flex flex-wrap gap-5 text-sm font-semibold">
            {content.socialLinks.map((link) => (
              <ExternalLink key={link.id} href={link.url}>
                {link.label || link.platform} →
              </ExternalLink>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}
