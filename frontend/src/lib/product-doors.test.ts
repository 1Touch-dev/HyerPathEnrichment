import { describe, expect, it } from "vitest";
import {
  canAccessDeskHome,
  filterByPermissions,
  getDefaultProduct,
  getUserHome,
  isStaffUser,
  resolvePostLoginPath,
  safeLocalRedirect,
  type ProductDoorUser,
} from "./product-doors";

function user(overrides: Partial<ProductDoorUser> = {}): ProductDoorUser {
  return {
    is_superuser: false,
    role_id: null,
    role_name: null,
    permissions: [],
    ...overrides,
  };
}

describe("product door resolution", () => {
  it.each([
    ["candidate", user(), "/app/matches", "candidate"],
    [
      "recruiter",
      user({
        role_id: "role-1",
        role_name: "recruiter",
        permissions: [{ resource: "linkedin_sourcing", action: "write" }],
      }),
      "/desk/sourcing-leads",
      "desk",
    ],
    [
      "support",
      user({
        role_id: "role-2",
        role_name: "support",
        permissions: [{ resource: "users", action: "read" }],
      }),
      "/desk/users",
      "desk",
    ],
    [
      "system health reader",
      user({
        role_id: "role-3",
        role_name: "admin",
        permissions: [{ resource: "system_health", action: "read" }],
      }),
      "/desk",
      "desk",
    ],
    ["superuser", user({ is_superuser: true }), "/desk", "desk"],
    ["unknown staff", user({ role_id: "role-5", role_name: "analyst" }), "/osint", "osint"],
  ] as const)("resolves the %s home", (_name, identity, home, product) => {
    expect(getUserHome(identity)).toBe(home);
    expect(getDefaultProduct(identity)).toBe(product);
  });

  it("uses role assignment, not role name, for the staff door", () => {
    expect(isStaffUser(user({ role_name: "recruiter" }))).toBe(false);
    expect(isStaffUser(user({ role_id: "role-1" }))).toBe(true);
  });

  it.each([
    ["superuser", user({ is_superuser: true }), true],
    [
      "staff with system health permission",
      user({
        role_id: "role-1",
        permissions: [{ resource: "system_health", action: "read" }],
      }),
      true,
    ],
    ["role-only staff", user({ role_id: "role-2", role_name: "team_owner" }), false],
    ["candidate", user(), false],
  ] as const)("classifies %s desk-home access", (_name, identity, expected) => {
    expect(canAccessDeskHome(identity)).toBe(expected);
  });
});

describe("permission filtering", () => {
  const items = [
    { label: "Open" },
    { label: "Users", permission: { resource: "users", action: "read" } },
    { label: "Queues", permission: { resource: "queues", action: "read" } },
  ];

  it("keeps public items and matching permission pairs", () => {
    expect(
      filterByPermissions(
        items,
        user({ permissions: [{ resource: "users", action: "read" }] }),
      ).map((item) => item.label),
    ).toEqual(["Open", "Users"]);
  });

  it("lets superusers cross every permission gate", () => {
    expect(filterByPermissions(items, user({ is_superuser: true }))).toEqual(items);
  });

  it("requires the exact permission pair for filtered items", () => {
    expect(
      filterByPermissions(
        items,
        user({
          role_name: "recruiter",
          permissions: [{ resource: "queues", action: "read" }],
        }),
      ).map((item) => item.label),
    ).toEqual(["Open", "Queues"]);
    expect(
      filterByPermissions(items, user({ role_name: "team_owner", permissions: [] })).map(
        (item) => item.label,
      ),
    ).toEqual(["Open"]);
  });
});

describe("safeLocalRedirect", () => {
  it("preserves a local path, query, and hash", () => {
    expect(safeLocalRedirect("/osint/jobs?state=done#latest")).toBe(
      "/osint/jobs?state=done#latest",
    );
  });

  it("returns a normalized local pathname", () => {
    expect(safeLocalRedirect("/a/../desk/users")).toBe("/desk/users");
  });

  it.each([
    "https://example.com",
    "//example.com/path",
    "/\\example.com/path",
    "/..//evil.com",
    "/%2e%2e//evil.com",
    "/a/..//evil.com",
    "javascript:alert(1)",
    "desk/users",
  ])("rejects unsafe redirect %s", (redirect) => {
    expect(safeLocalRedirect(redirect)).toBeNull();
  });
});

describe("resolvePostLoginPath", () => {
  it("sends staff with a Candidate redirect to their desk home", () => {
    const admin = user({ is_superuser: true });
    expect(resolvePostLoginPath(admin, "/app")).toBe("/desk");
    expect(resolvePostLoginPath(admin, "/app/matches")).toBe("/desk");
    expect(resolvePostLoginPath(admin, "app")).toBe("/desk");
  });

  it("still honors staff Desk and OSINT redirects", () => {
    const admin = user({ is_superuser: true });
    expect(resolvePostLoginPath(admin, "/desk/users")).toBe("/desk/users");
    expect(resolvePostLoginPath(admin, "/osint?tiers=tier1")).toBe("/osint?tiers=tier1");
  });

  it("sends candidates with a staff-door redirect to /app/matches", () => {
    expect(resolvePostLoginPath(user(), "/desk")).toBe("/app/matches");
    expect(resolvePostLoginPath(user(), "/osint?tiers=tier1")).toBe("/app/matches");
  });

  it("honors a candidate's own product redirect", () => {
    expect(resolvePostLoginPath(user(), "/app/documents")).toBe("/app/documents");
  });

  it("falls back to role home when the redirect is unsafe", () => {
    expect(resolvePostLoginPath(user({ is_superuser: true }), "https://example.com")).toBe("/desk");
  });
});
