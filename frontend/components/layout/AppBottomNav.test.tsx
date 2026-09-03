import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppBottomNav } from "./AppBottomNav";
import { getNavSections } from "./nav-config";

const candidateSections = getNavSections("candidate", null);

describe("AppBottomNav unread match indicator", () => {
  it("renders the unread dot indicator on the Matches link when matchesUnreadCount > 0", () => {
    render(
      <AppBottomNav sections={candidateSections} pathname="/app/matches" matchesUnreadCount={3} />,
    );

    const matchesLink = screen.getByText("Matches").closest("a");
    expect(matchesLink).not.toBeNull();
    expect(matchesLink?.querySelector("span.bg-destructive")).not.toBeNull();
  });

  it("hides the unread dot indicator on the Matches link when matchesUnreadCount is 0", () => {
    render(
      <AppBottomNav sections={candidateSections} pathname="/app/matches" matchesUnreadCount={0} />,
    );

    const matchesLink = screen.getByText("Matches").closest("a");
    expect(matchesLink?.querySelector("span.bg-destructive")).toBeNull();
  });

  it("defaults matchesUnreadCount to 0 and hides the indicator when the prop is omitted", () => {
    render(<AppBottomNav sections={candidateSections} pathname="/app/matches" />);

    const matchesLink = screen.getByText("Matches").closest("a");
    expect(matchesLink?.querySelector("span.bg-destructive")).toBeNull();
  });

  it("does not render an unread indicator on other main-nav links even when matchesUnreadCount > 0", () => {
    render(
      <AppBottomNav sections={candidateSections} pathname="/app/matches" matchesUnreadCount={3} />,
    );

    const cvLink = screen.getByText("My CV").closest("a");
    expect(cvLink?.querySelector("span.bg-destructive")).toBeNull();
  });
});
