"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Copy, ExternalLink, Maximize2, Monitor, Smartphone, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type {
  PortfolioContent,
  PortfolioEducation,
  PortfolioExperience,
  PortfolioProject,
  PortfolioSectionKey,
  PortfolioSkill,
  PortfolioTemplateId,
  PortfolioThemeConfig,
} from "@/src/lib/types";
import {
  usePortfolioProfile,
  usePublishPortfolioProfile,
  useSavePortfolioProfile,
} from "../hooks/usePortfolioProfile";
import { defaultSectionVisibility, defaultTheme, emptyContent, newEntityId } from "../lib/defaults";
import { TEMPLATE_DEFAULT_PALETTE, TEMPLATE_META } from "../templates/registry";
import { PortfolioRenderer } from "../templates/PortfolioRenderer";
import { SlugField } from "./SlugField";

type PreviewMode = "desktop" | "mobile";

export function PortfolioStudio() {
  const { data: profile, isLoading } = usePortfolioProfile();
  const saveProfile = useSavePortfolioProfile();
  const publishProfile = usePublishPortfolioProfile();

  const [slug, setSlug] = useState("");
  const [templateId, setTemplateId] = useState<PortfolioTemplateId>("minimal_professional");
  const [theme, setTheme] = useState<PortfolioThemeConfig>(defaultTheme());
  const [content, setContent] = useState<PortfolioContent>(emptyContent());
  const [sectionVisibility, setSectionVisibility] = useState(defaultSectionVisibility());
  const [sectionOrder, setSectionOrder] = useState<PortfolioSectionKey[]>([
    "about",
    "projects",
    "experience",
    "education",
    "skills",
    "certifications",
    "social",
    "contact",
  ]);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("desktop");
  const [fullscreen, setFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!profile) return;
    setSlug(profile.slug);
    setTemplateId(profile.templateId);
    setTheme(profile.theme);
    setContent(profile.content);
    setSectionVisibility(profile.sectionVisibility);
    setSectionOrder(profile.sectionOrder);
    setDirty(false);
  }, [profile]);

  const previewModel = useMemo(
    () => ({
      templateId,
      theme,
      content,
      sectionVisibility,
      sectionOrder,
    }),
    [templateId, theme, content, sectionVisibility, sectionOrder],
  );

  function patchContent(patch: Partial<PortfolioContent>) {
    setContent((prev) => ({ ...prev, ...patch }));
    setDirty(true);
  }

  function handleSelectTemplate(id: PortfolioTemplateId) {
    setTemplateId(id);
    setTheme((prev) => ({
      ...prev,
      palette: (TEMPLATE_DEFAULT_PALETTE[id] as PortfolioThemeConfig["palette"]) || prev.palette,
    }));
    setDirty(true);
  }

  async function handleSaveDraft() {
    if (slug.length < 3) {
      toast.error("Choose a slug with at least 3 characters.");
      return;
    }
    try {
      await saveProfile.mutateAsync({
        slug,
        displayName: content.displayName,
        headline: content.headline,
        summary: content.summary,
        isPublished: profile?.isPublished ?? false,
        templateId,
        theme,
        content,
        sectionVisibility,
        sectionOrder,
        publish: false,
      });
      setDirty(false);
      toast.success("Draft saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save draft");
    }
  }

  async function handlePublish() {
    if (slug.length < 3) {
      toast.error("Choose a slug with at least 3 characters.");
      return;
    }
    try {
      if (dirty || !profile) {
        await saveProfile.mutateAsync({
          slug,
          displayName: content.displayName,
          headline: content.headline,
          summary: content.summary,
          isPublished: true,
          templateId,
          theme,
          content,
          sectionVisibility,
          sectionOrder,
          publish: true,
        });
      } else {
        await publishProfile.mutateAsync();
      }
      setDirty(false);
      toast.success("Portfolio published");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to publish");
    }
  }

  async function handleCopyUrl() {
    const url =
      typeof window !== "undefined"
        ? `${window.location.origin}/p/${slug}`
        : profile?.publicUrl || `/p/${slug}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success("Link copied");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Could not copy link");
    }
  }

  function addProject() {
    const project: PortfolioProject = {
      id: newEntityId(),
      title: "New project",
      description: "",
      imageUrl: null,
      techStack: [],
      demoUrl: null,
      repoUrl: null,
      displayOrder: content.projects.length,
    };
    patchContent({ projects: [...content.projects, project] });
  }

  function updateProject(id: string, patch: Partial<PortfolioProject>) {
    patchContent({
      projects: content.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    });
  }

  function removeProject(id: string) {
    patchContent({ projects: content.projects.filter((p) => p.id !== id) });
  }

  function addExperience() {
    const entry: PortfolioExperience = {
      id: newEntityId(),
      company: "Company",
      title: "Role / title",
      location: null,
      startDate: "",
      endDate: null,
      isCurrent: false,
      description: "",
      achievements: [],
      displayOrder: content.experience.length,
    };
    patchContent({ experience: [...content.experience, entry] });
  }

  function updateExperience(id: string, patch: Partial<PortfolioExperience>) {
    patchContent({
      experience: content.experience.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    });
  }

  function removeExperience(id: string) {
    patchContent({ experience: content.experience.filter((e) => e.id !== id) });
  }

  function addEducation() {
    const entry: PortfolioEducation = {
      id: newEntityId(),
      institution: "Institution",
      degree: null,
      fieldOfStudy: null,
      startYear: "",
      endYear: null,
      description: null,
      activities: [],
      displayOrder: content.education.length,
    };
    patchContent({ education: [...content.education, entry] });
  }

  function updateEducation(id: string, patch: Partial<PortfolioEducation>) {
    patchContent({
      education: content.education.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    });
  }

  function removeEducation(id: string) {
    patchContent({ education: content.education.filter((e) => e.id !== id) });
  }

  function addSkill() {
    const skill: PortfolioSkill = {
      id: newEntityId(),
      name: "New skill",
      category: null,
      level: null,
      displayOrder: content.skills.length,
    };
    patchContent({ skills: [...content.skills, skill] });
  }

  function updateSkill(id: string, patch: Partial<PortfolioSkill>) {
    patchContent({
      skills: content.skills.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  }

  function removeSkill(id: string) {
    patchContent({ skills: content.skills.filter((s) => s.id !== id) });
  }

  if (isLoading) {
    return (
      <div className="h-[70vh] animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
    );
  }

  const statusLabel = profile?.isPublished
    ? dirty || profile.hasUnpublishedChanges
      ? "Unpublished changes"
      : "Published"
    : "Draft";

  const editor = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={
              statusLabel === "Published"
                ? "success"
                : statusLabel === "Draft"
                  ? "outline"
                  : "secondary"
            }
          >
            {statusLabel}
          </Badge>
          {dirty && <Badge variant="outline">Unsaved</Badge>}
        </div>
        <div className="flex flex-wrap gap-2">
          {profile?.isPublished && (
            <Button asChild size="sm" variant="outline">
              <a href={profile.publicUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                Open live page
              </a>
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleSaveDraft}
            disabled={saveProfile.isPending || slug.length < 3}
          >
            {saveProfile.isPending ? "Saving…" : "Save draft"}
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handlePublish}
            disabled={saveProfile.isPending || publishProfile.isPending || slug.length < 3}
          >
            {publishProfile.isPending ? "Publishing…" : "Publish changes"}
          </Button>
        </div>
      </div>

      <div className="mt-4 space-y-3 border-b border-border/70 pb-4">
        <SlugField
          value={slug}
          onChange={(v) => {
            setSlug(v);
            setDirty(true);
          }}
        />
        <div className="flex flex-wrap gap-2">
          {TEMPLATE_META.map((meta) => (
            <Button
              key={meta.id}
              type="button"
              size="sm"
              variant={templateId === meta.id ? "default" : "outline"}
              onClick={() => handleSelectTemplate(meta.id)}
            >
              {meta.name}
            </Button>
          ))}
        </div>
      </div>

      <Tabs defaultValue="content" className="mt-4 flex min-h-0 flex-1 flex-col">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="design">Design</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="content" className="mt-4 min-h-0 flex-1 space-y-6 overflow-y-auto pr-1">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Profile & headline</h3>
            <div className="grid gap-3">
              <div>
                <Label htmlFor="displayName">Display name</Label>
                <Input
                  id="displayName"
                  value={content.displayName ?? ""}
                  onChange={(e) => patchContent({ displayName: e.target.value || null })}
                />
              </div>
              <div>
                <Label htmlFor="role">Professional role</Label>
                <Input
                  id="role"
                  value={content.professionalRole ?? ""}
                  onChange={(e) => patchContent({ professionalRole: e.target.value || null })}
                />
              </div>
              <div>
                <Label htmlFor="headline">Headline</Label>
                <Input
                  id="headline"
                  value={content.headline ?? ""}
                  onChange={(e) => patchContent({ headline: e.target.value || null })}
                  maxLength={120}
                />
              </div>
              <div>
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={content.location ?? ""}
                  onChange={(e) => patchContent({ location: e.target.value || null })}
                />
              </div>
              <div>
                <Label htmlFor="summary">Summary</Label>
                <Textarea
                  id="summary"
                  value={content.summary ?? ""}
                  onChange={(e) => patchContent({ summary: e.target.value || null })}
                  rows={3}
                />
              </div>
              <div>
                <Label htmlFor="about">About</Label>
                <Textarea
                  id="about"
                  value={content.about ?? ""}
                  onChange={(e) => patchContent({ about: e.target.value || null })}
                  rows={5}
                />
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Projects</h3>
              <Button type="button" size="sm" variant="outline" onClick={addProject}>
                Add project
              </Button>
            </div>
            {content.projects.length === 0 && (
              <p className="rounded-xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
                No projects yet. Add one to showcase your work in the preview.
              </p>
            )}
            <div className="space-y-4">
              {content.projects.map((project) => (
                <div key={project.id} className="space-y-2 rounded-xl border border-border/70 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <Input
                      value={project.title}
                      onChange={(e) => updateProject(project.id, { title: e.target.value })}
                      placeholder="Project title"
                    />
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Remove project"
                      onClick={() => removeProject(project.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <Textarea
                    value={project.description ?? ""}
                    onChange={(e) =>
                      updateProject(project.id, { description: e.target.value || null })
                    }
                    placeholder="Description"
                    rows={2}
                  />
                  <Input
                    value={project.techStack.join(", ")}
                    onChange={(e) =>
                      updateProject(project.id, {
                        techStack: e.target.value
                          .split(",")
                          .map((t) => t.trim())
                          .filter(Boolean),
                      })
                    }
                    placeholder="Tech stack (comma-separated)"
                  />
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Input
                      value={project.demoUrl ?? ""}
                      onChange={(e) =>
                        updateProject(project.id, { demoUrl: e.target.value || null })
                      }
                      placeholder="Demo URL"
                    />
                    <Input
                      value={project.repoUrl ?? ""}
                      onChange={(e) =>
                        updateProject(project.id, { repoUrl: e.target.value || null })
                      }
                      placeholder="Repo URL"
                    />
                  </div>
                  <Input
                    value={project.imageUrl ?? ""}
                    onChange={(e) =>
                      updateProject(project.id, { imageUrl: e.target.value || null })
                    }
                    placeholder="Image URL (optional)"
                  />
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Experience</h3>
              <Button type="button" size="sm" variant="outline" onClick={addExperience}>
                Add experience
              </Button>
            </div>
            {content.experience.length === 0 && (
              <p className="rounded-xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
                No experience yet. Add a box for each role with company, duration, and details.
              </p>
            )}
            <div className="space-y-4">
              {content.experience.map((job) => (
                <div key={job.id} className="space-y-3 rounded-xl border border-border/70 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="grid flex-1 gap-2 sm:grid-cols-2">
                      <div>
                        <Label htmlFor={`exp-company-${job.id}`}>Company</Label>
                        <Input
                          id={`exp-company-${job.id}`}
                          value={job.company}
                          onChange={(e) => updateExperience(job.id, { company: e.target.value })}
                          placeholder="Company name"
                        />
                      </div>
                      <div>
                        <Label htmlFor={`exp-title-${job.id}`}>Role / title</Label>
                        <Input
                          id={`exp-title-${job.id}`}
                          value={job.title}
                          onChange={(e) => updateExperience(job.id, { title: e.target.value })}
                          placeholder="Job title"
                        />
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Remove experience"
                      onClick={() => removeExperience(job.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <div>
                      <Label htmlFor={`exp-start-${job.id}`}>Start</Label>
                      <Input
                        id={`exp-start-${job.id}`}
                        value={job.startDate ?? ""}
                        onChange={(e) =>
                          updateExperience(job.id, { startDate: e.target.value || null })
                        }
                        placeholder="Jan 2022"
                      />
                    </div>
                    <div>
                      <Label htmlFor={`exp-end-${job.id}`}>End</Label>
                      <Input
                        id={`exp-end-${job.id}`}
                        value={job.isCurrent ? "Present" : (job.endDate ?? "")}
                        onChange={(e) =>
                          updateExperience(job.id, {
                            endDate: e.target.value || null,
                            isCurrent: false,
                          })
                        }
                        placeholder="Dec 2024"
                        disabled={job.isCurrent}
                      />
                    </div>
                    <div className="flex items-end justify-between gap-2 rounded-lg border border-border/60 px-3 py-2">
                      <Label htmlFor={`exp-current-${job.id}`}>Current role</Label>
                      <Switch
                        id={`exp-current-${job.id}`}
                        checked={job.isCurrent}
                        onCheckedChange={(checked) =>
                          updateExperience(job.id, {
                            isCurrent: checked,
                            endDate: checked ? null : job.endDate,
                          })
                        }
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor={`exp-location-${job.id}`}>Location (optional)</Label>
                    <Input
                      id={`exp-location-${job.id}`}
                      value={job.location ?? ""}
                      onChange={(e) =>
                        updateExperience(job.id, { location: e.target.value || null })
                      }
                      placeholder="City, Country / Remote"
                    />
                  </div>
                  <div>
                    <Label htmlFor={`exp-desc-${job.id}`}>What you did</Label>
                    <Textarea
                      id={`exp-desc-${job.id}`}
                      value={job.description ?? ""}
                      onChange={(e) =>
                        updateExperience(job.id, { description: e.target.value || null })
                      }
                      placeholder="Describe your role, impact, and responsibilities…"
                      rows={3}
                    />
                  </div>
                  <div>
                    <Label htmlFor={`exp-achievements-${job.id}`}>
                      Achievements (one per line, optional)
                    </Label>
                    <Textarea
                      id={`exp-achievements-${job.id}`}
                      value={job.achievements.join("\n")}
                      onChange={(e) =>
                        updateExperience(job.id, {
                          achievements: e.target.value
                            .split("\n")
                            .map((line) => line.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder={"Grew conversion 20%\nLed a team of 4"}
                      rows={2}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Education</h3>
              <Button type="button" size="sm" variant="outline" onClick={addEducation}>
                Add education
              </Button>
            </div>
            {content.education.length === 0 && (
              <p className="rounded-xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
                No education yet. Add a box for each school with duration, studies, and activities.
              </p>
            )}
            <div className="space-y-4">
              {content.education.map((ed) => (
                <div key={ed.id} className="space-y-3 rounded-xl border border-border/70 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <Label htmlFor={`edu-inst-${ed.id}`}>Institute / school</Label>
                      <Input
                        id={`edu-inst-${ed.id}`}
                        value={ed.institution}
                        onChange={(e) => updateEducation(ed.id, { institution: e.target.value })}
                        placeholder="University or school name"
                      />
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Remove education"
                      onClick={() => removeEducation(ed.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div>
                      <Label htmlFor={`edu-start-${ed.id}`}>Start year</Label>
                      <Input
                        id={`edu-start-${ed.id}`}
                        value={ed.startYear ?? ""}
                        onChange={(e) =>
                          updateEducation(ed.id, { startYear: e.target.value || null })
                        }
                        placeholder="2019"
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-end-${ed.id}`}>End year</Label>
                      <Input
                        id={`edu-end-${ed.id}`}
                        value={ed.endYear ?? ""}
                        onChange={(e) =>
                          updateEducation(ed.id, { endYear: e.target.value || null })
                        }
                        placeholder="2023"
                      />
                    </div>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div>
                      <Label htmlFor={`edu-degree-${ed.id}`}>Degree</Label>
                      <Input
                        id={`edu-degree-${ed.id}`}
                        value={ed.degree ?? ""}
                        onChange={(e) => updateEducation(ed.id, { degree: e.target.value || null })}
                        placeholder="B.Sc, M.A, Diploma…"
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edu-field-${ed.id}`}>What you studied</Label>
                      <Input
                        id={`edu-field-${ed.id}`}
                        value={ed.fieldOfStudy ?? ""}
                        onChange={(e) =>
                          updateEducation(ed.id, { fieldOfStudy: e.target.value || null })
                        }
                        placeholder="Computer Science, Design…"
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor={`edu-desc-${ed.id}`}>Notes (optional)</Label>
                    <Textarea
                      id={`edu-desc-${ed.id}`}
                      value={ed.description ?? ""}
                      onChange={(e) =>
                        updateEducation(ed.id, { description: e.target.value || null })
                      }
                      placeholder="Thesis, focus area, honors…"
                      rows={2}
                    />
                  </div>
                  <div>
                    <Label htmlFor={`edu-activities-${ed.id}`}>
                      Activities you participated in (one per line)
                    </Label>
                    <Textarea
                      id={`edu-activities-${ed.id}`}
                      value={(ed.activities ?? []).join("\n")}
                      onChange={(e) =>
                        updateEducation(ed.id, {
                          activities: e.target.value
                            .split("\n")
                            .map((line) => line.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder={"Student council\nDebate club\nHackathon organizer"}
                      rows={3}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Skills</h3>
              <Button type="button" size="sm" variant="outline" onClick={addSkill}>
                Add skill
              </Button>
            </div>
            {content.skills.length === 0 && (
              <p className="rounded-xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
                No skills yet. Add a box for each skill, optionally with category and level.
              </p>
            )}
            <div className="space-y-3">
              {content.skills.map((skill) => (
                <div
                  key={skill.id}
                  className="grid gap-2 rounded-xl border border-border/70 p-3 sm:grid-cols-[1fr_1fr_1fr_auto]"
                >
                  <div>
                    <Label htmlFor={`skill-name-${skill.id}`}>Skill</Label>
                    <Input
                      id={`skill-name-${skill.id}`}
                      value={skill.name}
                      onChange={(e) => updateSkill(skill.id, { name: e.target.value })}
                      placeholder="Python"
                    />
                  </div>
                  <div>
                    <Label htmlFor={`skill-cat-${skill.id}`}>Category</Label>
                    <Input
                      id={`skill-cat-${skill.id}`}
                      value={skill.category ?? ""}
                      onChange={(e) => updateSkill(skill.id, { category: e.target.value || null })}
                      placeholder="Backend, Design…"
                    />
                  </div>
                  <div>
                    <Label htmlFor={`skill-level-${skill.id}`}>Level</Label>
                    <Input
                      id={`skill-level-${skill.id}`}
                      value={skill.level ?? ""}
                      onChange={(e) => updateSkill(skill.id, { level: e.target.value || null })}
                      placeholder="Expert, Intermediate…"
                    />
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Remove skill"
                      onClick={() => removeSkill(skill.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Contact & social</h3>
            <Input
              value={content.email ?? ""}
              onChange={(e) => patchContent({ email: e.target.value || null })}
              placeholder="Email"
            />
            <Input
              value={content.resumeUrl ?? ""}
              onChange={(e) => patchContent({ resumeUrl: e.target.value || null })}
              placeholder="Resume URL"
            />
            <Textarea
              value={content.socialLinks.map((s) => `${s.platform}|${s.url}`).join("\n")}
              onChange={(e) => {
                const lines = e.target.value
                  .split("\n")
                  .map((l) => l.trim())
                  .filter(Boolean);
                patchContent({
                  socialLinks: lines.map((line, idx) => {
                    const [platform, url] = line.split("|").map((p) => p.trim());
                    const existing = content.socialLinks[idx];
                    return {
                      id: existing?.id || newEntityId(),
                      platform:
                        (platform as PortfolioContent["socialLinks"][number]["platform"]) ||
                        "other",
                      label: existing?.label ?? null,
                      url: url || platform || "",
                      displayOrder: idx,
                    };
                  }),
                });
              }}
              placeholder={"github|https://github.com/you\nlinkedin|https://linkedin.com/in/you"}
              rows={3}
            />
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Section visibility</h3>
            <div className="space-y-2">
              {(Object.keys(sectionVisibility) as PortfolioSectionKey[]).map((key) => (
                <div
                  key={key}
                  className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2"
                >
                  <Label htmlFor={`vis-${key}`} className="capitalize">
                    {key}
                  </Label>
                  <Switch
                    id={`vis-${key}`}
                    checked={sectionVisibility[key]}
                    onCheckedChange={(checked) => {
                      setSectionVisibility((prev) => ({ ...prev, [key]: checked }));
                      setDirty(true);
                    }}
                  />
                </div>
              ))}
            </div>
          </section>
        </TabsContent>

        <TabsContent value="design" className="mt-4 space-y-6 overflow-y-auto pr-1">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Templates</h3>
            <div className="grid gap-3">
              {TEMPLATE_META.map((meta) => (
                <button
                  key={meta.id}
                  type="button"
                  onClick={() => handleSelectTemplate(meta.id)}
                  className={`rounded-xl border p-4 text-left transition ${
                    templateId === meta.id
                      ? "border-primary bg-primary-soft/40 shadow-sm"
                      : "border-border/70 hover:border-primary/40"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{meta.name}</p>
                    {templateId === meta.id && <Check className="h-4 w-4 text-primary" />}
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{meta.tagline}</p>
                  <p className="mt-2 text-xs text-muted-foreground">Best for: {meta.bestFor}</p>
                </button>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Palette</h3>
            <div className="grid grid-cols-2 gap-2">
              {(["neutral", "vibrant", "ocean", "forest", "slate"] as const).map((palette) => (
                <Button
                  key={palette}
                  type="button"
                  variant={theme.palette === palette ? "default" : "outline"}
                  size="sm"
                  className="capitalize"
                  onClick={() => {
                    setTheme((prev) => ({ ...prev, palette }));
                    setDirty(true);
                  }}
                >
                  {palette}
                </Button>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Typography</h3>
            <div className="grid grid-cols-2 gap-2">
              {(["sans", "serif", "mono", "editorial"] as const).map((fontPairing) => (
                <Button
                  key={fontPairing}
                  type="button"
                  variant={theme.fontPairing === fontPairing ? "default" : "outline"}
                  size="sm"
                  className="capitalize"
                  onClick={() => {
                    setTheme((prev) => ({ ...prev, fontPairing }));
                    setDirty(true);
                  }}
                >
                  {fontPairing}
                </Button>
              ))}
            </div>
          </section>
        </TabsContent>

        <TabsContent value="settings" className="mt-4 space-y-6 overflow-y-auto pr-1">
          <SlugField
            value={slug}
            onChange={(v) => {
              setSlug(v);
              setDirty(true);
            }}
          />
          <div className="rounded-xl border border-border/70 bg-surface p-4 text-sm text-muted-foreground">
            <p className="mb-2 font-medium text-foreground">Public URL</p>
            <p className="mb-3 font-mono text-xs">
              {slug.length >= 3 ? `/p/${slug}` : "Pick a slug first"}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleCopyUrl}
                disabled={slug.length < 3}
              >
                {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
                Copy link
              </Button>
              {profile?.isPublished && (
                <Button asChild size="sm" variant="outline">
                  <a href={profile.publicUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Open live page
                  </a>
                </Button>
              )}
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            Draft changes stay private until you publish. The public page always shows the last
            published revision.
          </p>
        </TabsContent>
      </Tabs>
    </div>
  );

  const preview = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-sm font-medium">Live preview</p>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            size="icon"
            variant={previewMode === "desktop" ? "default" : "ghost"}
            aria-label="Desktop preview"
            onClick={() => setPreviewMode("desktop")}
          >
            <Monitor className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant={previewMode === "mobile" ? "default" : "ghost"}
            aria-label="Mobile preview"
            onClick={() => setPreviewMode("mobile")}
          >
            <Smartphone className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label="Fullscreen preview"
            onClick={() => setFullscreen(true)}
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-border/70 bg-muted/30 p-3">
        <div
          className={`mx-auto overflow-hidden rounded-lg border border-border/50 shadow-panel transition-all ${
            previewMode === "mobile" ? "max-w-[390px]" : "w-full"
          }`}
        >
          <PortfolioRenderer model={previewModel} preview />
        </div>
      </div>
    </div>
  );

  return (
    <>
      <div className="hidden min-h-[70vh] gap-6 xl:grid xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
        <div className="rounded-xl border border-border/70 bg-card p-4 shadow-panel sm:p-5">
          {editor}
        </div>
        <div className="min-h-[70vh] rounded-xl border border-border/70 bg-card p-4 shadow-panel">
          {preview}
        </div>
      </div>

      <div className="xl:hidden">
        <Tabs defaultValue="edit">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="edit">Editor</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
          </TabsList>
          <TabsContent value="edit" className="mt-4 rounded-xl border border-border/70 bg-card p-4">
            {editor}
          </TabsContent>
          <TabsContent
            value="preview"
            className="mt-4 h-[70vh] rounded-xl border border-border/70 bg-card p-4"
          >
            {preview}
          </TabsContent>
        </Tabs>
      </div>

      {fullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-background">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="text-sm font-medium">Fullscreen preview</p>
            <Button type="button" size="sm" variant="outline" onClick={() => setFullscreen(false)}>
              Close
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            <PortfolioRenderer model={previewModel} />
          </div>
        </div>
      )}
    </>
  );
}

/** Backward-compatible export name used by existing imports/tests. */
export { PortfolioStudio as PortfolioEditor };
