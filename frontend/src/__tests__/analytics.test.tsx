import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import * as auth from "@/lib/auth";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  useParams: () => ({ id: "student-1" }),
}));

let _testRole = "parent";
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "p@test.com", role: _testRole, is_active: true }, loading: false, role: _testRole, refresh: vi.fn() }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// We import the page lazily to avoid the mock timing issues
vi.mock("@/lib/api", () => ({
  api: {
    me: vi.fn(),
    listStudents: vi.fn(),
    getStudentSummary: vi.fn(),
    getStudentTopics: vi.fn(),
    getStudentSkills: vi.fn(),
    getStudentRecommendations: vi.fn(),
    getStudentTrend: vi.fn(),
    getMyProgress: vi.fn(),
    getMyHistory: vi.fn(),
    getMyTrend: vi.fn(),
    getAccessToken: vi.fn(() => "test-token"),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
}));


describe("StudentAnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders analytics summary cards", async () => {
    const mockListStudents = (await import("@/lib/api")).api.listStudents as any;
    const mockSummary = (await import("@/lib/api")).api.getStudentSummary as any;
    const mockTopics = (await import("@/lib/api")).api.getStudentTopics as any;
    const mockSkills = (await import("@/lib/api")).api.getStudentSkills as any;
    const mockRecs = (await import("@/lib/api")).api.getStudentRecommendations as any;
    const mockTrend = (await import("@/lib/api")).api.getStudentTrend as any;

    mockListStudents.mockResolvedValue([
      { id: "student-1", display_name: "Test Student", year_level: 5, first_login_completed: true },
    ]);
    mockSummary.mockResolvedValue({
      total_attempts: 3,
      average_score: 75.0,
      best_score: 90.0,
      latest_score: 65.0,
      total_questions_answered: 30,
      total_correct_answers: 22,
      overall_accuracy: 73.3,
    });
    mockTopics.mockResolvedValue({ topics: [] });
    mockSkills.mockResolvedValue({ skills: [] });
    mockTrend.mockResolvedValue([]);
    mockRecs.mockResolvedValue({
      weak_topics: [],
      strong_topics: [],
      weak_skills: [],
      strong_skills: [],
      slow_topics: [],
      recommendations: [
        { type: "topic", target_id: "t1", target_name: "Fractions", message: "Practice Fractions" },
      ],
    });

    const StudentAnalyticsPage = (await import("@/app/(account)/parent/students/[id]/page")).default;
    render(<StudentAnalyticsPage />);

    expect(await screen.findByText("Test Student")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("75%")).toBeDefined();
    expect(screen.getByText("90%")).toBeDefined();
    expect(screen.getByText("73.3%")).toBeDefined();
    expect(screen.getByText("Recommendations")).toBeDefined();
    expect(screen.getByText("Practice Fractions")).toBeDefined();
  });

  it("renders topic and skill tables with weaknesses", async () => {
    const mockListStudents = (await import("@/lib/api")).api.listStudents as any;
    const mockSummary = (await import("@/lib/api")).api.getStudentSummary as any;
    const mockTopics = (await import("@/lib/api")).api.getStudentTopics as any;
    const mockSkills = (await import("@/lib/api")).api.getStudentSkills as any;
    const mockRecs = (await import("@/lib/api")).api.getStudentRecommendations as any;
    const mockTrend2 = (await import("@/lib/api")).api.getStudentTrend as any;

    mockListStudents.mockResolvedValue([
      { id: "student-1", display_name: "Test Student", year_level: 5, first_login_completed: true },
    ]);
    mockSummary.mockResolvedValue({
      total_attempts: 1, average_score: 50, best_score: 50, latest_score: 50,
      total_questions_answered: 4, total_correct_answers: 2, overall_accuracy: 50,
    });
    mockTopics.mockResolvedValue({
      topics: [
        { topic_id: "t1", topic_name: "Fractions", attempts: 2, correct_count: 1, accuracy_rate: 50, average_time_seconds: 30 },
      ],
    });
    mockSkills.mockResolvedValue({
      skills: [
        { skill_id: "s1", skill_name: "Addition", attempts: 2, correct_count: 2, accuracy_rate: 100, average_time_seconds: 20 },
      ],
    });
    mockTrend2.mockResolvedValue([]);
    mockRecs.mockResolvedValue({
      weak_topics: [{ id: "t1", name: "Fractions", accuracy_rate: 50, attempts: 2 }],
      strong_topics: [],
      weak_skills: [],
      strong_skills: [{ id: "s1", name: "Addition", accuracy_rate: 100, attempts: 2 }],
      slow_topics: [],
      recommendations: [{ type: "topic", target_id: "t1", target_name: "Fractions", message: "Practice Fractions more." }],
    });

    const StudentAnalyticsPage = (await import("@/app/(account)/parent/students/[id]/page")).default;
    render(<StudentAnalyticsPage />);

    expect(await screen.findByText("Topic Performance")).toBeDefined();
    expect(screen.getByText("Addition")).toBeDefined();
    expect(screen.getByText("Skill Performance")).toBeDefined();
    expect(screen.getAllByText("Fractions").length).toBeGreaterThanOrEqual(2);
  });
});


describe("StudentProgressPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _testRole = "student";
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders progress with summary and history", async () => {
    const mockProgress = (await import("@/lib/api")).api.getMyProgress as any;
    const mockHistory = (await import("@/lib/api")).api.getMyHistory as any;
    const mockTrend = (await import("@/lib/api")).api.getMyTrend as any;

    mockProgress.mockResolvedValue({
      summary: {
        total_attempts: 2,
        average_score: 80,
        best_score: 90,
        latest_score: 70,
        total_questions_answered: 20,
        total_correct_answers: 16,
        overall_accuracy: 75,
      },
      weak_topics: [],
      strong_topics: [{ id: "t1", name: "Geometry", accuracy_rate: 100, attempts: 5 }],
      weak_skills: [{ id: "s1", name: "Division", accuracy_rate: 40, attempts: 5 }],
      strong_skills: [],
      slow_topics: [],
    });

    mockHistory.mockResolvedValue([
      { attempt_id: "a1", exam_title: "OC Maths", status: "submitted", score_percent: 90, total_questions: 10, correct_count: 9, completed_at: "2026-06-01T10:00:00Z" },
      { attempt_id: "a2", exam_title: "OC English", status: "submitted", score_percent: 70, total_questions: 10, correct_count: 7, completed_at: "2026-06-02T10:00:00Z" },
    ]);

    mockTrend.mockResolvedValue([]);

    const StudentProgressPage = (await import("@/app/(account)/me/progress/page")).default;
    render(<StudentProgressPage />);

    expect(await screen.findByText("My Progress")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined(); // Exams Taken
    expect(screen.getByText("80%")).toBeDefined(); // Average
    expect(screen.getAllByText("90%").length).toBeGreaterThanOrEqual(1); // Best + history entry
    expect(screen.getByText("75%")).toBeDefined(); // Accuracy
    expect(screen.getByText("Strengths")).toBeDefined();
    expect(screen.getByText("Geometry")).toBeDefined();
    expect(screen.getByText("Areas to Improve")).toBeDefined();
    expect(screen.getByText("Division")).toBeDefined();
  });
});
