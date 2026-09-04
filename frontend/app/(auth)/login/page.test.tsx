import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LoginPage from "./page";

const pushMock = vi.fn();
const loginMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));
vi.mock("@/providers/auth-provider", () => ({
  useAuth: () => ({ login: loginMock }),
}));

beforeEach(() => {
  pushMock.mockReset();
  loginMock.mockReset().mockResolvedValue({
    is_superuser: false,
    role_id: "role-1",
    role_name: "recruiter",
    permissions: [{ resource: "linkedin_sourcing", action: "write" }],
  });
  window.history.replaceState({}, "", "/login");
});

async function submitLogin() {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "recruiter@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign In" }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
}

describe("login navigation", () => {
  it("honors a safe local redirect", async () => {
    window.history.replaceState({}, "", "/login?redirect=%2Fosint%2Fjobs%3Fstate%3Ddone");
    render(<LoginPage />);
    await submitLogin();
    expect(pushMock).toHaveBeenCalledWith("/osint/jobs?state=done");
  });

  it("falls back to the role home for an unsafe redirect", async () => {
    window.history.replaceState({}, "", "/login?redirect=https%3A%2F%2Fexample.com");
    render(<LoginPage />);
    await submitLogin();
    expect(pushMock).toHaveBeenCalledWith("/desk/sourcing-leads");
  });
});
