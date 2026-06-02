import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import * as auth from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: "student-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    me: vi.fn(),
    listStudents: vi.fn(),
    listAllAssignments: vi.fn(),
    getMyAssignments: vi.fn(),
    getMyAssignment: vi.fn(),
    updateAssignment: vi.fn(),
    startAttempt: vi.fn(),
    startAttemptWithAssignment: vi.fn(),
    saveAnswer: vi.fn(),
    submitAttempt: vi.fn(),
    getAttemptResult: vi.fn(),
    recordIntegrityEvent: vi.fn(),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
}));


describe("StudentAssignmentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders assignments with status badges", async () => {
    const mock = (await import("@/lib/api")).api.getMyAssignments as any;
    mock.mockResolvedValue([
      {
        id: "a1",
        student_id: "s1",
        exam_instance_id: "ei1",
        title_snapshot: "OC Maths Practice",
        due_at: "2026-06-10T00:00:00Z",
        status: "assigned",
        created_at: "2026-06-01T00:00:00Z",
      },
      {
        id: "a2",
        student_id: "s1",
        exam_instance_id: "ei2",
        title_snapshot: "Selective Thinking Skills",
        due_at: null,
        status: "completed",
        created_at: "2026-05-01T00:00:00Z",
      },
    ]);

    const Page = (await import("@/app/(account)/me/assignments/page")).default;
    render(<Page />);

    expect(await screen.findByText("OC Maths Practice")).toBeDefined();
    expect(screen.getByText("assigned")).toBeDefined();
    // "Selective Thinking Skills" appears in both active and completed lists
    expect(screen.getAllByText("Selective Thinking Skills").length).toBe(2);
  });

  it("shows empty state when no assignments", async () => {
    const mock = (await import("@/lib/api")).api.getMyAssignments as any;
    mock.mockResolvedValue([]);

    const Page = (await import("@/app/(account)/me/assignments/page")).default;
    render(<Page />);

    expect(await screen.findByText("No active assignments right now.")).toBeDefined();
  });

  it("shows Start Exam button for active assignments", async () => {
    const mock = (await import("@/lib/api")).api.getMyAssignments as any;
    mock.mockResolvedValue([
      {
        id: "a1",
        student_id: "s1",
        exam_instance_id: "ei1",
        title_snapshot: "OC Maths Practice",
        due_at: null,
        status: "assigned",
        created_at: "2026-06-01T00:00:00Z",
      },
    ]);

    const Page = (await import("@/app/(account)/me/assignments/page")).default;
    render(<Page />);

    expect(await screen.findByText("Start Exam")).toBeDefined();
  });
});


describe("ParentAssignmentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders assignments with student names", async () => {
    const mockAssign = (await import("@/lib/api")).api.listAllAssignments as any;
    const mockStudents = (await import("@/lib/api")).api.listStudents as any;

    mockAssign.mockResolvedValue([
      {
        id: "a1",
        student_id: "s1",
        exam_instance_id: "ei1",
        title_snapshot: "OC Maths",
        due_at: null,
        status: "assigned",
        student_name: "Test Student",
        created_at: "2026-06-01T00:00:00Z",
      },
    ]);
    mockStudents.mockResolvedValue([
      { id: "s1", display_name: "Test Student", year_level: 5, first_login_completed: true },
    ]);

    const Page = (await import("@/app/(account)/parent/assignments/page")).default;
    render(<Page />);

    expect(await screen.findByText("OC Maths")).toBeDefined();
    expect(screen.getByText("assigned")).toBeDefined();
  });

  it("shows cancel button for active assignments", async () => {
    const mockAssign = (await import("@/lib/api")).api.listAllAssignments as any;
    const mockStudents = (await import("@/lib/api")).api.listStudents as any;

    mockAssign.mockResolvedValue([
      {
        id: "a1",
        student_id: "s1",
        exam_instance_id: "ei1",
        title_snapshot: "OC Maths",
        due_at: null,
        status: "assigned",
        student_name: "Test Student",
        created_at: "2026-06-01T00:00:00Z",
      },
    ]);
    mockStudents.mockResolvedValue([
      { id: "s1", display_name: "Test Student", year_level: 5, first_login_completed: true },
    ]);

    const Page = (await import("@/app/(account)/parent/assignments/page")).default;
    render(<Page />);

    expect(await screen.findByText("Cancel")).toBeDefined();
  });
});
