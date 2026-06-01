import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LoginPage from "@/app/(auth)/login/page";

vi.mock("@/lib/auth", () => ({
  saveTokens: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { login: vi.fn() },
}));

describe("LoginPage", () => {
  it("renders the login form", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("login-form")).toBeInTheDocument();
  });

  it("renders email input", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("email-input")).toBeInTheDocument();
  });

  it("renders password input", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("password-input")).toBeInTheDocument();
  });

  it("does not show error message initially", () => {
    render(<LoginPage />);
    expect(screen.queryByTestId("error-message")).not.toBeInTheDocument();
  });
});
