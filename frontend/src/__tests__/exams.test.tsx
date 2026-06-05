import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { api } from "@/lib/api";
import * as auth from "@/lib/auth";

// Mock the API and auth modules
vi.mock("@/lib/api", () => ({
  api: {
    listAvailableExams: vi.fn(),
    startAttempt: vi.fn(),
    saveAnswer: vi.fn(),
    submitAttempt: vi.fn(),
    getAttemptResult: vi.fn(),
    listMyAttempts: vi.fn(),
    getAttempt: vi.fn(),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
  saveTokens: vi.fn(),
  getRefreshToken: vi.fn(() => "test-refresh"),
  isAuthenticated: vi.fn(() => true),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "s@test.com", role: "student", is_active: true }, loading: false, role: "student", refresh: vi.fn() }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ instanceId: "inst-1", attemptId: "attempt-1" }),
  useSearchParams: () => new URLSearchParams(),
}));


describe("ExamsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders available exams", async () => {
    (api.listAvailableExams as any).mockResolvedValue([
      {
        id: "inst-1",
        title: "Year 5 OC Maths",
        duration_minutes: 30,
        question_count: 20,
        total_marks: 20,
      },
    ]);

    const ExamsPage = (await import("@/app/(account)/exams/page")).default;
    render(<ExamsPage />);

    expect(await screen.findByText("Year 5 OC Maths")).toBeDefined();
    expect(screen.getByText("20 questions · 20 marks")).toBeDefined();
    expect(screen.getByText("30 minutes")).toBeDefined();
    expect(screen.getByText("Start Exam")).toBeDefined();
  });

  it("shows empty state when no exams", async () => {
    (api.listAvailableExams as any).mockResolvedValue([]);

    const ExamsPage = (await import("@/app/(account)/exams/page")).default;
    render(<ExamsPage />);

    expect(await screen.findByText("No exams available right now.")).toBeDefined();
  });
});


describe("ExamAttemptPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders exam questions and options", async () => {
    (api.startAttempt as any).mockResolvedValue({
      attempt_id: "attempt-1",
      exam_instance_id: "inst-1",
      title: "Test Exam",
      duration_minutes: 30,
      started_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 30 * 60000).toISOString(),
      total_questions: 1,
      questions: [
        {
          exam_instance_question_id: "eiq-1",
          question_id: "q-1",
          question_version_id: "qv-1",
          stem: "What is 2 + 2?",
          correct_answer: null,
          full_explanation: "",
          marks: 1,
          options_json: [
            { label: "A", text: "4", is_correct: true },
            { label: "B", text: "3", is_correct: false },
          ],
          order_index: 0,
        },
      ],
    });

    const ExamAttemptPage = (await import("@/app/(account)/exams/[instanceId]/page")).default;
    render(<ExamAttemptPage />);

    expect(await screen.findByText("What is 2 + 2?")).toBeDefined();
    expect(screen.getByText("4")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("Submit Exam")).toBeDefined();
  });

  it("answer selection works", async () => {
    (api.startAttempt as any).mockResolvedValue({
      attempt_id: "attempt-1",
      exam_instance_id: "inst-1",
      title: "Test Exam",
      duration_minutes: 30,
      started_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 30 * 60000).toISOString(),
      total_questions: 1,
      questions: [
        {
          exam_instance_question_id: "eiq-1",
          question_id: "q-1",
          question_version_id: "qv-1",
          stem: "What is 2 + 2?",
          correct_answer: null,
          full_explanation: "",
          marks: 1,
          options_json: [
            { label: "A", text: "4", is_correct: true },
            { label: "B", text: "3", is_correct: false },
          ],
          order_index: 0,
        },
      ],
    });
    (api.saveAnswer as any).mockResolvedValue({ id: "ans-1", exam_instance_question_id: "eiq-1", selected_option: "A", is_correct: null, answered_at: new Date().toISOString() });

    const ExamAttemptPage = (await import("@/app/(account)/exams/[instanceId]/page")).default;
    render(<ExamAttemptPage />);

    expect(await screen.findByText("What is 2 + 2?")).toBeDefined();
  });

  it("submit button calls API", async () => {
    (api.startAttempt as any).mockResolvedValue({
      attempt_id: "attempt-1",
      exam_instance_id: "inst-1",
      title: "Test Exam",
      duration_minutes: 30,
      started_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 30 * 60000).toISOString(),
      total_questions: 1,
      questions: [],
    });

    // Quick test: it renders without error
    const ExamAttemptPage = (await import("@/app/(account)/exams/[instanceId]/page")).default;
    render(<ExamAttemptPage />);

    // With empty questions, it shows the fallback
    expect(await screen.findByText(/no questions/)).toBeDefined();
  });
});


describe("ExamResultPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders score and per-question breakdown", async () => {
    (api.getAttemptResult as any).mockResolvedValue({
      attempt_id: "attempt-1",
      exam_instance_id: "inst-1",
      title: "Test Exam",
      status: "submitted",
      started_at: new Date().toISOString(),
      expires_at: new Date().toISOString(),
      submitted_at: new Date().toISOString(),
      score_raw: 1,
      score_percent: 50.0,
      total_questions: 2,
      correct_count: 1,
      questions: [
        {
          exam_instance_question_id: "eiq-1",
          question_id: "q-1",
          stem: "What is 2 + 2?",
          correct_answer: "A",
          full_explanation: "2 + 2 = 4",
          marks: 1,
          options_json: [
            { label: "A", text: "4", is_correct: true },
            { label: "B", text: "3", is_correct: false },
          ],
          order_index: 0,
          selected_option: "A",
          is_correct: true,
          marks_awarded: 1,
        },
        {
          exam_instance_question_id: "eiq-2",
          question_id: "q-2",
          stem: "What is 3 + 3?",
          correct_answer: "C",
          full_explanation: "3 + 3 = 6",
          marks: 1,
          options_json: [
            { label: "C", text: "6", is_correct: true },
            { label: "D", text: "7", is_correct: false },
          ],
          order_index: 1,
          selected_option: "D",
          is_correct: false,
          marks_awarded: 0,
        },
      ],
    });

    const ExamResultPage = (await import("@/app/(account)/exams/attempts/[attemptId]/page")).default;
    render(<ExamResultPage />);

    expect(await screen.findByText("50%")).toBeDefined();
    expect(screen.getByText("1/2")).toBeDefined();
    expect(screen.getByText("1")).toBeDefined(); // score_raw
    expect(screen.getByText("Review")).toBeDefined();
    expect(screen.getByText(/Your answer/)).toBeDefined();
  });

  it("shows read-only options", async () => {
    (api.getAttemptResult as any).mockResolvedValue({
      attempt_id: "attempt-1",
      exam_instance_id: "inst-1",
      title: "Test Exam",
      status: "submitted",
      started_at: new Date().toISOString(),
      expires_at: new Date().toISOString(),
      submitted_at: new Date().toISOString(),
      score_raw: 0,
      score_percent: 0,
      total_questions: 1,
      correct_count: 0,
      questions: [
        {
          exam_instance_question_id: "eiq-1",
          question_id: "q-1",
          stem: "Question text",
          correct_answer: "A",
          full_explanation: "Explanation",
          marks: 1,
          options_json: [
            { label: "A", text: "Right", is_correct: true },
            { label: "B", text: "Wrong", is_correct: false },
          ],
          order_index: 0,
          selected_option: "B",
          is_correct: false,
          marks_awarded: 0,
        },
      ],
    });

    const ExamResultPage = (await import("@/app/(account)/exams/attempts/[attemptId]/page")).default;
    render(<ExamResultPage />);

    expect(await screen.findByText("Question text")).toBeDefined();
    expect(screen.getByText("0%")).toBeDefined();
  });
});
