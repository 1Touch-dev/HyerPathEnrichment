import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppBottomNav } from "./AppBottomNav";

describe("AppBottomNav unread match indicator", () => {
  it("renders the unread dot indicator on the Matches link when matchesUnreadCount > 0", () => {
    render(<AppBottomNav pathname="/app/enrich" matchesUnreadCount={3} />);

    const matchesLink = screen.getByText("Matches").closest("a");
    expect(matchesLink).not.toBeNull();
    expect(matchesLink?.querySelector("span.bg-destructive")).not.toBeNull();
  });

  it("hides the unread dot indicator on the Matches link when matchesUnreadCount is 0", () => {
    render(<AppBottomNav pathname="/app/enrich" matchesUnreadCount={0} />);

    const matchesLink = screen.getByText("Matches").closest("a");
    expect(matchesLink?.querySelector("span.bg-destructive")).toBeNull();
  });

  it("defaults matchesUnreadCount to 0 and hides the indicator when the prop is omitted", () => {
    render(<AppBottomNav pathname="/app/enrich" />);

    const matchesLink = screen.getByText("Matches").closest("a");
    expect(matchesLink?.querySelector("span.bg-destructive")).toBeNull();
  });

  it("does not render an unread indicator on other main-nav links even when matchesUnreadCount > 0", () => {
    render(<AppBottomNav pathname="/app/enrich" matchesUnreadCount={3} />);

    const lookupLink = screen.getByText("Look up").closest("a");
    expect(lookupLink?.querySelector("span.bg-destructive")).toBeNull();
  });
});
