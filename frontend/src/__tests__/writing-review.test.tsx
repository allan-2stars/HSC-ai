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

const reviewUnderReview = {
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
    content: "The student essay text.",
    word_count: 4,
    student_name: "Test Student",
    task_title: "Persuasive Essay",
    submitted_at: "2026-06-17T00:00:00Z",
  },
  feedback: null,
  rubric: null,
};

describe("Admin review detail — feedback authoring and publish gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
    (api.getWritingReview as any).mockResolvedValue(reviewUnderReview);
  });

  it("renders the submission content for review", async () => {
    const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
    render(<Page />);
    expect(await screen.findByText("The student essay text.")).toBeDefined();
  });

  it("publish is disabled until feedback is saved (status reviewed)", async () => {
    const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
    render(<Page />);
    await screen.findByText("The student essay text.");

    const publishBtn = screen.getByText("Publish to Student") as HTMLButtonElement;
    expect(publishBtn.disabled).toBe(true);
  });

  it("saving feedback calls the API and enables publishing", async () => {
    (api.addWritingFeedback as any).mockResolvedValue({
      ...reviewUnderReview,
      status: "reviewed",
      latest_feedback_version: 1,
      feedback: { version: 1, overall_comment: "Great work.", dimensions: null, created_at: null },
    });

    const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
    render(<Page />);
    await screen.findByText("The student essay text.");

    fireEvent.change(screen.getByPlaceholderText("Write educational feedback for this response..."), {
      target: { value: "Great work." },
    });
    fireEvent.click(screen.getByText("Save Feedback"));

    await waitFor(() => {
      expect(api.addWritingFeedback).toHaveBeenCalledWith(
        "rev-1",
        { overall_comment: "Great work." },
        "test-token"
      );
    });

    await waitFor(() => {
      const publishBtn = screen.getByText("Publish to Student") as HTMLButtonElement;
      expect(publishBtn.disabled).toBe(false);
    });
  });

  it("publishing calls the publish API", async () => {
    (api.getWritingReview as any).mockResolvedValue({
      ...reviewUnderReview,
      status: "reviewed",
      latest_feedback_version: 1,
      feedback: { version: 1, overall_comment: "Done.", dimensions: null, created_at: null },
    });
    (api.publishWritingReview as any).mockResolvedValue({
      ...reviewUnderReview,
      status: "published",
      published_at: "2026-06-17T01:00:00Z",
    });

    const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
    render(<Page />);
    await screen.findByText("The student essay text.");

    fireEvent.click(screen.getByText("Publish to Student"));

    await waitFor(() => {
      expect(api.publishWritingReview).toHaveBeenCalledWith("rev-1", "test-token");
    });
  });
});
