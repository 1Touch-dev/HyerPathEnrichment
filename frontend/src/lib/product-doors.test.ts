import { describe, expect, it } from "vitest";
import {
  filterByPermissions,
  getDefaultProduct,
  getUserHome,
  isStaffUser,
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
      user({ role_id: "role-1", role_name: "recruiter" }),
      "/desk/sourcing-leads",
      "desk",
    ],
    ["support", user({ role_id: "role-2", role_name: "support" }), "/desk/users", "desk"],
    ["admin", user({ role_id: "role-3", role_name: "admin" }), "/desk", "desk"],
    ["team owner", user({ role_id: "role-4", role_name: "team_owner" }), "/desk", "desk"],
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
