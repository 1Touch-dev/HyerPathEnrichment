import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Provider } from "react-redux";
import { AppSidebar } from "./AppSidebar";
import { store } from "@/store";
import { getNavSections } from "./nav-config";

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/enrich",
}));

function renderSidebar(matchesUnreadCount?: number) {
  return render(
    <Provider store={store}>
      <AppSidebar
        product="candidate"
        sections={getNavSections("candidate", null)}
        matchesUnreadCount={matchesUnreadCount}
      />
    </Provider>,
  );
}

describe("AppSidebar unread match badge", () => {
  it("renders the unread count badge on the Matches link when matchesUnreadCount > 0", () => {
    renderSidebar(5);

    const matchesLink = screen.getByRole("link", { name: /matches/i });
    expect(within(matchesLink).getByText("5")).toBeInTheDocument();
  });

  it("hides the unread badge on the Matches link when matchesUnreadCount is 0", () => {
    renderSidebar(0);

    const matchesLink = screen.getByRole("link", { name: /matches/i });
    expect(within(matchesLink).queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it("defaults matchesUnreadCount to 0 and hides the badge when the prop is omitted", () => {
    renderSidebar();

    const matchesLink = screen.getByRole("link", { name: /matches/i });
    expect(within(matchesLink).queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it("does not render an unread badge on other nav links even when matchesUnreadCount > 0", () => {
    renderSidebar(5);

    const cvLink = screen.getByRole("link", { name: /my cv/i });
    expect(within(cvLink).queryByText(/^\d+$/)).not.toBeInTheDocument();
  });
});
