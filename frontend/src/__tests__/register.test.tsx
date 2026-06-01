import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import RegisterPage from "@/app/(auth)/register/page";

vi.mock("@/lib/auth", () => ({
  saveTokens: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { register: vi.fn() },
}));

describe("RegisterPage", () => {
  it("renders the register form", () => {
    render(<RegisterPage />);
    expect(screen.getByTestId("register-form")).toBeInTheDocument();
  });

  it("renders display name input", () => {
    render(<RegisterPage />);
    expect(screen.getByTestId("display-name-input")).toBeInTheDocument();
  });

  it("renders email input", () => {
    render(<RegisterPage />);
    expect(screen.getByTestId("email-input")).toBeInTheDocument();
  });

  it("renders password input", () => {
    render(<RegisterPage />);
    expect(screen.getByTestId("password-input")).toBeInTheDocument();
  });

  it("does not show error message initially", () => {
    render(<RegisterPage />);
    expect(screen.queryByTestId("error-message")).not.toBeInTheDocument();
  });
});
