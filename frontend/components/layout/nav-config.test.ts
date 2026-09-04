import { describe, expect, it } from "vitest";
import { getNavSections } from "./nav-config";
import type { ProductDoorUser } from "@/src/lib/product-doors";

function labels(product: "candidate" | "desk" | "osint", user?: ProductDoorUser) {
  return getNavSections(product, user)
    .flatMap((section) => section.items)
    .map((item) => item.label);
}

describe("product navigation", () => {
  it("contains only Candidate features and Candidate system links", () => {
    expect(labels("candidate")).toEqual([
      "My CV",
      "Interview Prep",
      "Matches",
      "Swipe jobs",
      "Applications",
      "Portfolio",
      "Outreach",
      "Privacy",
      "Settings",
    ]);
  });

  it("defines exactly Look up and Settings for OSINT", () => {
    expect(labels("osint")).toEqual(["Look up", "Settings"]);
  });

  it("filters Desk navigation by exact returned permission pairs", () => {
    const recruiter: ProductDoorUser = {
      is_superuser: false,
      role_id: "role-1",
      role_name: "recruiter",
      permissions: [
        { resource: "linkedin_sourcing", action: "write" },
        { resource: "brands", action: "read" },
        { resource: "users", action: "read" },
        { resource: "roles", action: "read" },
        { resource: "feature_flags", action: "read" },
        { resource: "queues", action: "read" },
      ],
    };

    expect(labels("desk", recruiter)).toEqual([
      "Sourcing leads",
      "Brands",
      "Users",
      "Roles",
      "Feature flags",
      "Queues",
    ]);
  });

  it("unlocks shared analytics and system-health links from their exact permission pairs", () => {
    const staffUser: ProductDoorUser = {
      is_superuser: false,
      role_id: "role-2",
      role_name: "recruiter",
      permissions: [
        { resource: "analytics", action: "read" },
        { resource: "system_health", action: "read" },
      ],
    };

    expect(labels("desk", staffUser)).toEqual([
      "System health",
      "Analytics",
      "Demand intelligence",
      "Signals",
    ]);
  });

  it("shows every Desk item to a superuser", () => {
    const superuser: ProductDoorUser = {
      is_superuser: true,
      role_id: null,
      role_name: null,
      permissions: [],
    };
    expect(labels("desk", superuser)).toEqual(
      expect.arrayContaining(["Roles", "Feature flags", "Queues", "Signals"]),
    );
  });

  it.each(["admin", "team_owner"])(
    "does not show privileged items to %s without read permissions",
    (role) => {
      const ownerLikeUser: ProductDoorUser = {
        is_superuser: false,
        role_id: "role-owner",
        role_name: role,
        permissions: [],
      };
      expect(labels("desk", ownerLikeUser)).not.toEqual(
        expect.arrayContaining(["Roles", "Feature flags", "Queues"]),
      );
    },
  );
});
