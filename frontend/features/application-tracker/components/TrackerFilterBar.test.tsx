import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { TrackerFilterBar } from "./TrackerFilterBar";

const replaceMock = vi.fn();
let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/tracker",
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => currentSearchParams,
}));

// Radix Select relies on pointer capture / scrollIntoView APIs jsdom doesn't implement.
beforeAll(() => {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.scrollIntoView = () => {};
});

describe("TrackerFilterBar", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    currentSearchParams = new URLSearchParams();
  });

  it("defaults to 'All statuses' and 'Newest' when no search params are set", () => {
    render(<TrackerFilterBar />);
    expect(screen.getByText("All statuses")).toBeInTheDocument();
    expect(screen.getByText("Newest")).toBeInTheDocument();
  });

  it("reflects the status search param in the status select", () => {
    currentSearchParams = new URLSearchParams("status=interview");
    render(<TrackerFilterBar />);
    expect(screen.getByText("Interview")).toBeInTheDocument();
  });

  it("reflects the sort search param in the sort select", () => {
    currentSearchParams = new URLSearchParams("sort=score");
    render(<TrackerFilterBar />);
    expect(screen.getByText("Score")).toBeInTheDocument();
  });

  it("navigates with a new status param when a status option is selected", async () => {
    render(<TrackerFilterBar />);
    fireEvent.click(screen.getByLabelText("Status"));
    const listbox = await screen.findByRole("listbox");
    fireEvent.click(within(listbox).getByText("Interview"));
    expect(replaceMock).toHaveBeenCalledWith("/app/tracker?status=interview");
  });

  it("preserves the existing status param when the sort option is changed", async () => {
    currentSearchParams = new URLSearchParams("status=interview");
    render(<TrackerFilterBar />);
    fireEvent.click(screen.getByLabelText("Sort"));
    const listbox = await screen.findByRole("listbox");
    fireEvent.click(within(listbox).getByText("Score"));
    expect(replaceMock).toHaveBeenCalledWith("/app/tracker?status=interview&sort=score");
  });

  it("removes the status param entirely when 'All statuses' is selected", async () => {
    currentSearchParams = new URLSearchParams("status=interview&sort=score");
    render(<TrackerFilterBar />);
    fireEvent.click(screen.getByLabelText("Status"));
    const listbox = await screen.findByRole("listbox");
    fireEvent.click(within(listbox).getByText("All statuses"));
    expect(replaceMock).toHaveBeenCalledWith("/app/tracker?sort=score");
  });
});
