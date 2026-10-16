import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { PortfolioEditor } from "./PortfolioEditor";
import * as hooks from "../hooks/usePortfolioProfile";
import type { PortfolioProfile } from "@/src/lib/types";
import { emptyContent, defaultSectionVisibility, defaultTheme } from "../lib/defaults";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleContent = {
  ...emptyContent(),
  displayName: "Jane Doe",
  headline: "Backend Engineer",
  summary: "I build things.",
  about: "I build things.",
  projects: [
    {
      id: "i1",
      title: "My repo",
      description: null,
      imageUrl: null,
      techStack: ["Python"],
      demoUrl: null,
      repoUrl: "https://github.com/jane/repo",
      displayOrder: 0,
    },
  ],
};

const sampleProfile: PortfolioProfile = {
  profileId: "p1",
  userId: "u1",
  slug: "jane-doe",
  displayName: "Jane Doe",
  headline: "Backend Engineer",
  summary: "I build things.",
  isPublished: true,
  publicUrl: "/p/jane-doe",
  items: [
    {
      itemId: "i1",
      itemType: "github_repo",
      title: "My repo",
      description: null,
      url: "https://github.com/jane/repo",
      displayOrder: 0,
    },
  ],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  templateId: "minimal_professional",
  theme: defaultTheme(),
  content: sampleContent,
  sectionVisibility: defaultSectionVisibility(),
  sectionOrder: [
    "about",
    "projects",
    "experience",
    "education",
    "skills",
    "certifications",
    "social",
    "contact",
  ],
  hasUnpublishedChanges: false,
  draftRevision: {
    templateId: "minimal_professional",
    theme: defaultTheme(),
    content: sampleContent,
    sectionVisibility: defaultSectionVisibility(),
    sectionOrder: [
      "about",
      "projects",
      "experience",
      "education",
      "skills",
      "certifications",
      "social",
      "contact",
    ],
  },
  publishedRevision: null,
};

const saveMutateAsyncMock = vi.fn();
const publishMutateAsyncMock = vi.fn();

function mockUsePortfolioProfile(overrides: Partial<UseQueryResult<PortfolioProfile>> = {}) {
  vi.spyOn(hooks, "usePortfolioProfile").mockReturnValue({
    data: undefined,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<PortfolioProfile>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  saveMutateAsyncMock.mockReset().mockResolvedValue({ data: sampleProfile });
  publishMutateAsyncMock.mockReset().mockResolvedValue({ data: sampleProfile });
  vi.spyOn(hooks, "useSavePortfolioProfile").mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: saveMutateAsyncMock,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useSavePortfolioProfile>);
  vi.spyOn(hooks, "usePublishPortfolioProfile").mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: publishMutateAsyncMock,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.usePublishPortfolioProfile>);
  mockUsePortfolioProfile();
});

describe("PortfolioEditor (Portfolio Studio)", () => {
  it("shows Draft status when no profile exists yet", () => {
    mockUsePortfolioProfile({ data: undefined, isLoading: false });
    render(<PortfolioEditor />, { wrapper });
    expect(screen.getAllByText("Draft").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Save draft")[0]).toBeDisabled();
  });

  it("shows Open live page once a published profile exists", () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });
    const link = screen.getAllByRole("link", { name: /Open live page/i })[0];
    expect(link).toHaveAttribute("href", "/p/jane-doe");
  });

  it("enables save draft once a valid slug is entered", () => {
    mockUsePortfolioProfile({ data: undefined, isLoading: false });
    render(<PortfolioEditor />, { wrapper });
    expect(screen.getAllByText("Save draft")[0]).toBeDisabled();
    const slugInput = screen.getAllByLabelText("Portfolio URL")[0];
    fireEvent.change(slugInput, { target: { value: "abc" } });
    expect(screen.getAllByText("Save draft")[0]).not.toBeDisabled();
  });

  it("saves a draft with studio fields", async () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });
    fireEvent.click(screen.getAllByText("Save draft")[0]);
    await waitFor(() => expect(saveMutateAsyncMock).toHaveBeenCalled());
    expect(saveMutateAsyncMock).toHaveBeenCalledWith(
      expect.objectContaining({
        slug: "jane-doe",
        templateId: "minimal_professional",
        publish: false,
      }),
    );
  });

  it("switches templates without clearing content", () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });
    fireEvent.click(screen.getAllByRole("button", { name: "Developer Dark" })[0]);
    expect(screen.getAllByDisplayValue("My repo").length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue("Backend Engineer").length).toBeGreaterThan(0);
  });

  it("adds a project from the content tab", () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });
    fireEvent.click(screen.getAllByText("Add project")[0]);
    expect(screen.getAllByDisplayValue("New project").length).toBeGreaterThan(0);
  });
});
