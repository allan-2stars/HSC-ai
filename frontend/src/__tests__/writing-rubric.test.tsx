import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { api } from "@/lib/api";
import * as auth from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ reviewId: "rev-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getWritingReview: vi.fn(),
    addWritingFeedback: vi.fn(),
    publishWritingReview: vi.fn(),
    scoreReview: vi.fn(),
    listRubrics: vi.fn(),
    createRubric: vi.fn(),
    listAIDrafts: vi.fn(() => Promise.resolve([])),
    generateAIDraft: vi.fn(),
    discardAIDraft: vi.fn(),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "a1", email: "admin@test.com", role: "admin", is_active: true },
    loading: false,
    role: "admin",
    refresh: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const reviewWithRubric = {
  id: "rev-1",
  submission_id: "sub-1",
  status: "under_review",
  reviewer_admin_id: null,
  assigned_at: null,
  review_started_at: "2026-06-17T00:00:00Z",
  published_at: null,
  latest_feedback_version: null,
  submission: {
    id: "sub-1",
    content: "Essay text.",
    word_count: 2,
    student_name: "Test Student",
    task_title: "Persuasive Essay",
    submitted_at: "2026-06-17T00:00:00Z",
  },
  feedback: null,
  rubric: {
    rubric_id: "rub-1",
    title: "Selective Writing Rubric",
    scores: [
      { dimension_id: "d1", name: "Ideas", description: "Quality of ideas", display_order: 1, rating: null, comment: null },
      { dimension_id: "d2", name: "Structure", description: "Organisation", display_order: 2, rating: null, comment: null },
    ],
  },
};

describe("Admin review detail — rubric scoring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
    (api.getWritingReview as any).mockResolvedValue(reviewWithRubric);
  });

  it("renders rubric dimensions for scoring", async () => {
    const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
    render(<Page />);
    expect(await screen.findByText("Ideas")).toBeDefined();
    expect(screen.getByText("Structure")).toBeDefined();
    expect(screen.getByText(/Selective Writing Rubric/)).toBeDefined();
  });

  it("saving scores calls scoreReview with all dimensions", async () => {
    (api.scoreReview as any).mockResolvedValue({ review_id: "rev-1", scores: [] });

    const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
    render(<Page />);
    await screen.findByText("Ideas");

    fireEvent.change(screen.getByLabelText("Comment for Ideas"), { target: { value: "Strong ideas." } });
    fireEvent.change(screen.getByLabelText("Rating for Structure"), { target: { value: "4" } });
    fireEvent.click(screen.getByText("Save Scores"));

    await waitFor(() => {
      expect(api.scoreReview).toHaveBeenCalledTimes(1);
    });
    const [reviewId, payload] = (api.scoreReview as any).mock.calls[0];
    expect(reviewId).toBe("rev-1");
    expect(payload).toHaveLength(2);
    expect(payload.find((s: any) => s.dimension_id === "d1").comment).toBe("Strong ideas.");
    expect(payload.find((s: any) => s.dimension_id === "d2").rating).toBe(4);
  });
});

describe("Admin rubrics page — create", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
    (api.listRubrics as any).mockResolvedValue([]);
  });

  it("creates a rubric with dimensions", async () => {
    (api.createRubric as any).mockResolvedValue({ id: "rub-1" });

    const Page = (await import("@/app/(account)/admin/writing/rubrics/page")).default;
    render(<Page />);

    fireEvent.click(await screen.findByText("Create Rubric"));
    fireEvent.change(screen.getByPlaceholderText("Rubric title"), { target: { value: "My Rubric" } });
    fireEvent.change(screen.getByPlaceholderText("Dimension 1 name"), { target: { value: "Ideas" } });
    // The submit button is the second "Create Rubric" (toggle keeps its label as Cancel after open)
    fireEvent.click(screen.getByText("Create Rubric"));

    await waitFor(() => {
      expect(api.createRubric).toHaveBeenCalledTimes(1);
    });
    const [body] = (api.createRubric as any).mock.calls[0];
    expect(body.title).toBe("My Rubric");
    expect(body.dimensions[0].name).toBe("Ideas");
  });
});
