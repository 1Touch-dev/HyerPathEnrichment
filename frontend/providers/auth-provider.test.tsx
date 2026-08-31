import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./auth-provider";

// auth-provider.tsx's register() talks to /api/auth/register via the global
// `fetch`, not through src/lib/backend-client.ts (that module is server-only
// and cannot be imported from a client component). There is no existing
// precedent in this repo for mocking a client component's direct `fetch`
// call, so this test establishes the pattern with `vi.stubGlobal("fetch", ...)`.

function mockFetchOnce(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("AuthProvider register()", () => {
  beforeEach(() => {
    // fetchUser() runs on mount (GET /api/auth/me); default it to "unauthenticated"
    // so every test starts from a clean, resolved loading state before we
    // swap in a fresh mock for the register() call itself.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 401 })),
    );
  });

  async function renderAuth() {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    return result;
  }

  it("omits invite_token entirely from the request body when inviteToken is undefined", async () => {
    const result = await renderAuth();
    const registerFetch = mockFetchOnce({ id: "u1" });
    vi.stubGlobal("fetch", registerFetch);

    await act(async () => {
      await result.current.register("a@example.com", "pw", "First", "Last", undefined);
    });

    expect(registerFetch).toHaveBeenCalledTimes(1);
    const [, init] = registerFetch.mock.calls[0];
    const sentBody = JSON.parse(init.body as string);
    expect(sentBody).not.toHaveProperty("invite_token");
    expect(sentBody).toEqual({
      email: "a@example.com",
      password: "pw",
      first_name: "First",
      last_name: "Last",
    });
  });

  it("includes invite_token set to the exact value when inviteToken is a non-empty string", async () => {
    const result = await renderAuth();
    const registerFetch = mockFetchOnce({ id: "u1" });
    vi.stubGlobal("fetch", registerFetch);

    await act(async () => {
      await result.current.register("a@example.com", "pw", "First", "Last", "invite-token-xyz");
    });

    const [, init] = registerFetch.mock.calls[0];
    const sentBody = JSON.parse(init.body as string);
    expect(sentBody.invite_token).toBe("invite-token-xyz");
  });

  it("omits invite_token when inviteToken is an empty string (falsy, matches backend's `if user_data.invite_token:` gate)", async () => {
    const result = await renderAuth();
    const registerFetch = mockFetchOnce({ id: "u1" });
    vi.stubGlobal("fetch", registerFetch);

    await act(async () => {
      await result.current.register("a@example.com", "pw", "First", "Last", "");
    });

    const [, init] = registerFetch.mock.calls[0];
    const sentBody = JSON.parse(init.body as string);
    expect(sentBody).not.toHaveProperty("invite_token");
    expect(sentBody.invite_token).not.toBe("");
    expect(sentBody.invite_token).toBeUndefined();
  });
});
