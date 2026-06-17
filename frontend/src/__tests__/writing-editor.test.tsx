import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { api } from "@/lib/api";
import * as auth from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ submissionId: "sub-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getWritingSubmission: vi.fn(),
    saveWriting: vi.fn(),
    submitWriting: vi.fn(),
    getWritingFeedback: vi.fn(() => Promise.reject({ status: 404 })),
    getSubmissionRubric: vi.fn(() => Promise.reject({ status: 404 })),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "s@test.com", role: "student", is_active: true },
    loading: false,
    role: "student",
    refresh: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const draftSubmission = {
  id: "sub-1",
  writing_task_id: "task-1",
  student_id: "student-1",
  content: "Original draft",
  word_count: 2,
  status: "draft",
  started_at: "2026-06-16T00:00:00Z",
  submitted_at: null,
  created_at: "2026-06-16T00:00:00Z",
  updated_at: "2026-06-16T00:00:00Z",
};

describe("WritingEditor — submit-after-save-failure guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
    (api.getWritingSubmission as any).mockResolvedValue(draftSubmission);
    (api.getWritingFeedback as any).mockRejectedValue({ status: 404 });
    (api.getSubmissionRubric as any).mockRejectedValue({ status: 404 });
  });

  it("blocks submit and shows a visible error when the final save fails", async () => {
    (api.saveWriting as any).mockRejectedValue({ status: 500, detail: "Internal error" });

    const Page = (await import("@/app/(account)/me/writing/[submissionId]/page")).default;
    render(<Page />);

    await screen.findByDisplayValue("Original draft");

    fireEvent.click(screen.getByText("Submit Response"));

    await waitFor(() => {
      expect(
        screen.getByText(
          "Could not save your latest changes. Please check your connection and try again before submitting."
        )
      ).toBeDefined();
    });

    expect(api.submitWriting).not.toHaveBeenCalled();
  });

  it("submits normally when the final save succeeds", async () => {
    (api.saveWriting as any).mockResolvedValue({ ...draftSubmission, content: "Original draft" });
    (api.submitWriting as any).mockResolvedValue({
      ...draftSubmission,
      status: "submitted",
      submitted_at: "2026-06-16T01:00:00Z",
    });

    const Page = (await import("@/app/(account)/me/writing/[submissionId]/page")).default;
    render(<Page />);

    await screen.findByDisplayValue("Original draft");

    fireEvent.click(screen.getByText("Submit Response"));

    await waitFor(() => {
      expect(api.submitWriting).toHaveBeenCalledWith("sub-1", "test-token");
    });

    expect(await screen.findByText("Submitted")).toBeDefined();
  });
});
