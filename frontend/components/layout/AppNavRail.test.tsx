import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { AppNavRail } from "./AppNavRail";

describe("AppNavRail unread match indicator", () => {
  it("renders the unread dot indicator on the Matches link when matchesUnreadCount > 0", () => {
    render(<AppNavRail pathname="/app/enrich" matchesUnreadCount={3} />);

    const matchesLink = screen.getByRole("link", { name: /matches/i });
    expect(
      within(matchesLink).getByText("", { selector: "span.bg-destructive" }),
    ).toBeInTheDocument();
  });

  it("hides the unread dot indicator on the Matches link when matchesUnreadCount is 0", () => {
    render(<AppNavRail pathname="/app/enrich" matchesUnreadCount={0} />);

    const matchesLink = screen.getByRole("link", { name: /matches/i });
    expect(matchesLink.querySelector("span.bg-destructive")).not.toBeInTheDocument();
  });

  it("defaults matchesUnreadCount to 0 and hides the indicator when the prop is omitted", () => {
    render(<AppNavRail pathname="/app/enrich" />);

    const matchesLink = screen.getByRole("link", { name: /matches/i });
    expect(matchesLink.querySelector("span.bg-destructive")).not.toBeInTheDocument();
  });

  it("does not render an unread indicator on other nav links even when matchesUnreadCount > 0", () => {
    render(<AppNavRail pathname="/app/enrich" matchesUnreadCount={3} />);

    const lookupLink = screen.getByRole("link", { name: /look up/i });
    expect(lookupLink.querySelector("span.bg-destructive")).not.toBeInTheDocument();
  });
});
