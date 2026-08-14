import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { PortfolioEditor } from "./PortfolioEditor";
import * as hooks from "../hooks/usePortfolioProfile";
import type { PortfolioProfile } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

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
};

const saveMutateMock = vi.fn();
const addMutateMock = vi.fn();
const deleteMutateMock = vi.fn();

function mockUsePortfolioProfile(overrides: Partial<UseQueryResult<PortfolioProfile>> = {}) {
  vi.spyOn(hooks, "usePortfolioProfile").mockReturnValue({
    data: undefined,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<PortfolioProfile>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  saveMutateMock.mockReset();
  addMutateMock.mockReset();
  deleteMutateMock.mockReset();
  vi.spyOn(hooks, "useSavePortfolioProfile").mockReturnValue({
    mutate: saveMutateMock,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useSavePortfolioProfile>);
  vi.spyOn(hooks, "useAddPortfolioItem").mockReturnValue({
    mutate: addMutateMock,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useAddPortfolioItem>);
  vi.spyOn(hooks, "useDeletePortfolioItem").mockReturnValue({
    mutate: deleteMutateMock,
    isPending: false,
  } as unknown as ReturnType<typeof hooks.useDeletePortfolioItem>);
  mockUsePortfolioProfile();
});

describe("PortfolioEditor", () => {
  it("shows a disabled 'View public page' button when no profile exists yet", () => {
    mockUsePortfolioProfile({ data: undefined, isLoading: false });
    render(<PortfolioEditor />, { wrapper });

    expect(screen.getByRole("button", { name: "View public page" })).toBeDisabled();
  });

  it("shows an enabled 'View public page' link pointing at publicUrl once a profile exists", () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });

    const link = screen.getByRole("link", { name: "View public page" });
    expect(link).toHaveAttribute("href", "/p/jane-doe");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("disables the save button while the slug is shorter than 3 characters", () => {
    mockUsePortfolioProfile({ data: undefined, isLoading: false });
    render(<PortfolioEditor />, { wrapper });

    expect(screen.getByText("Save profile")).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Portfolio URL"), { target: { value: "ab" } });
    expect(screen.getByText("Save profile")).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Portfolio URL"), { target: { value: "abc" } });
    expect(screen.getByText("Save profile")).not.toBeDisabled();
  });

  it("calls saveProfile.mutate with the current form values on submit", () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });

    const form = screen.getByText("Save profile").closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    expect(saveMutateMock).toHaveBeenCalledWith({
      slug: "jane-doe",
      headline: "Backend Engineer",
      summary: "I build things.",
      isPublished: true,
    });
  });

  it("calls deleteItem.mutate with the item id when Remove is clicked", () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    render(<PortfolioEditor />, { wrapper });

    fireEvent.click(screen.getByText("Remove"));
    expect(deleteMutateMock).toHaveBeenCalledWith("i1");
  });

  it("clears the new-item fields when handleAddItem succeeds", async () => {
    mockUsePortfolioProfile({ data: sampleProfile, isLoading: false });
    addMutateMock.mockImplementation((_payload, options?: { onSuccess?: () => void }) => {
      options?.onSuccess?.();
    });
    render(<PortfolioEditor />, { wrapper });

    const titleInput = screen.getByPlaceholderText("Title");
    const urlInput = screen.getByPlaceholderText("https://...");
    fireEvent.change(titleInput, { target: { value: "New project" } });
    fireEvent.change(urlInput, { target: { value: "https://example.com" } });

    const addForm = screen.getByText("Add").closest("form");
    addForm!.requestSubmit();

    expect(addMutateMock).toHaveBeenCalledWith(
      {
        itemType: "other_link",
        title: "New project",
        description: null,
        url: "https://example.com",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    await waitFor(() => expect(titleInput).toHaveValue(""));
    expect(urlInput).toHaveValue("");
  });
});
