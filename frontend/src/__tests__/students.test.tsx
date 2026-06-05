import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import StudentsPage from "@/app/(account)/students/page";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

vi.mock("@/lib/api", () => ({
  api: {
    listStudents: vi.fn(),
    createStudent: vi.fn(),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "p@test.com", role: "parent", is_active: true }, loading: false, role: "parent", refresh: vi.fn() }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

describe("StudentsPage", () => {
  beforeEach(() => {
    vi.mocked(getAccessToken).mockReturnValue("mock-token");
    vi.mocked(api.listStudents).mockResolvedValue([]);
  });

  it("renders create student form when fewer than 3 students", () => {
    render(<StudentsPage />);
    expect(screen.getByTestId("create-student-form")).toBeInTheDocument();
  });

  it("renders student name input", () => {
    render(<StudentsPage />);
    expect(screen.getByTestId("student-name-input")).toBeInTheDocument();
  });

  it("renders year level select", () => {
    render(<StudentsPage />);
    expect(screen.getByTestId("year-level-select")).toBeInTheDocument();
  });

  it("hides create form when 3 students exist", async () => {
    vi.mocked(api.listStudents).mockResolvedValue([
      { id: "1", display_name: "A", year_level: 4, first_login_completed: false },
      { id: "2", display_name: "B", year_level: 5, first_login_completed: false },
      { id: "3", display_name: "C", year_level: 6, first_login_completed: false },
    ]);
    render(<StudentsPage />);
    await waitFor(() => {
      expect(screen.queryByTestId("create-student-form")).not.toBeInTheDocument();
    });
  });
});
