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
    listAIDrafts: vi.fn(),
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

const draft = {
  id: "draft-1",
  review_id: "rev-1",
  provider: "mock",
  model: "mock",
  prompt_version: "wfd-v1",
  status: "generated" as const,
  draft_feedback: {
    strengths: ["Clear structure."],
    improvements: ["Vary sentence openings."],
    next_steps: ["Add a concrete example."],
    overall_feedback: "Solid attempt overall.",
  },
  generated_by_admin_id: "admin-1",
  created_at: "2026-06-18T00:00:00Z",
  updated_at: "2026-06-18T00:00:00Z",
};

async function renderPage() {
  const Page = (await import("@/app/(account)/admin/writing/reviews/[reviewId]/page")).default;
  render(<Page />);
  await screen.findByText("AI Draft Feedback");
}

describe("Admin review detail — AI draft feedback panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
    (api.getWritingReview as any).mockResolvedValue(reviewUnderReview);
    (api.listAIDrafts as any).mockResolvedValue([]);
  });

  it("shows the AI draft panel with the not-visible disclaimer", async () => {
    await renderPage();
    expect(screen.getByText(/not visible to student or parent/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Generate AI Draft/i })).toBeInTheDocument();
  });

  it("generates a draft and renders its structured sections", async () => {
    (api.generateAIDraft as any).mockResolvedValue(draft);
    // First load returns empty, after generation the list returns the new draft.
    (api.listAIDrafts as any)
      .mockResolvedValueOnce([])
      .mockResolvedValue([draft]);

    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Generate AI Draft/i }));

    await waitFor(() => expect(api.generateAIDraft).toHaveBeenCalledWith("rev-1", "test-token"));
    expect(await screen.findByText("Clear structure.")).toBeInTheDocument();
    expect(screen.getByText("Vary sentence openings.")).toBeInTheDocument();
    expect(screen.getByText("Add a concrete example.")).toBeInTheDocument();
    expect(screen.getByText("Solid attempt overall.")).toBeInTheDocument();
  });

  it("copies a draft into the editable official feedback box without publishing", async () => {
    (api.listAIDrafts as any).mockResolvedValue([draft]);
    await renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Copy to Official Feedback/i }));

    const textarea = screen.getByPlaceholderText(/Write educational feedback/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain("Solid attempt overall.");
    expect(textarea.value).toContain("Clear structure.");
    // Copying is client-side only — nothing is saved or published.
    expect(api.addWritingFeedback).not.toHaveBeenCalled();
    expect(api.publishWritingReview).not.toHaveBeenCalled();
  });

  it("discards a draft", async () => {
    (api.discardAIDraft as any).mockResolvedValue({ ...draft, status: "discarded" });
    (api.listAIDrafts as any).mockResolvedValue([draft]);
    await renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Discard Draft/i }));
    await waitFor(() => expect(api.discardAIDraft).toHaveBeenCalledWith("draft-1", "test-token"));
  });
});
