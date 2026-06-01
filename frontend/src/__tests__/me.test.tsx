import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AccountPage from "@/app/(account)/me/page";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

vi.mock("@/lib/api", () => ({
  api: { me: vi.fn() },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(),
  clearTokens: vi.fn(),
}));

describe("AccountPage", () => {
  beforeEach(() => {
    vi.mocked(getAccessToken).mockReturnValue("mock-token");
    vi.mocked(api.me).mockResolvedValue({
      id: "user-1",
      email: "parent@test.com",
      role: "parent",
      is_active: true,
    });
  });

  it("shows user email after load", async () => {
    render(<AccountPage />);
    await waitFor(() => {
      expect(screen.getByTestId("user-email")).toHaveTextContent("parent@test.com");
    });
  });

  it("shows user role after load", async () => {
    render(<AccountPage />);
    await waitFor(() => {
      expect(screen.getByTestId("user-role")).toHaveTextContent("parent");
    });
  });

  it("shows loading state before data arrives", () => {
    vi.mocked(api.me).mockReturnValue(new Promise(() => {}));
    render(<AccountPage />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });
});
