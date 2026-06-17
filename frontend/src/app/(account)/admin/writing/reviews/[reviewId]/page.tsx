"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type WritingReviewDetail } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function AdminWritingReviewDetailPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <ReviewDetail />
    </RoleGuard>
  );
}

function ReviewDetail() {
  const params = useParams();
  const reviewId = params.reviewId as string;
  const [review, setReview] = useState<WritingReviewDetail | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const token = getAccessToken();

  function load() {
    if (!token) return;
    api.getWritingReview(reviewId, token)
      .then((r) => {
        setReview(r);
        if (r.feedback) setComment(r.feedback.overall_comment);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load review");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, reviewId]);

  async function saveFeedback() {
    if (!token || !comment.trim()) { setError("Feedback comment is required."); return; }
    setBusy(true);
    setError("");
    try {
      const updated = await api.addWritingFeedback(reviewId, { overall_comment: comment }, token);
      setReview(updated);
    } catch (e: any) {
      setError(e.detail ?? "Failed to save feedback");
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await api.publishWritingReview(reviewId, token);
      load();
    } catch (e: any) {
      setError(e.detail ?? "Failed to publish");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error && !review) return <p className="p-8 text-error">{error}</p>;
  if (!review) return <p className="p-8 text-text-secondary">Review not found</p>;

  const published = review.status === "published";

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Review</h1>
          <p className="text-text-secondary text-sm">
            {review.submission.student_name} — {review.submission.task_title}
          </p>
        </div>
        <span className="text-xs px-2 py-0.5 rounded bg-interactive/10 text-interactive">
          {review.status.replace("_", " ")}
        </span>
      </div>

      <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-text-secondary mb-2">
          Submission · {review.submission.word_count} words
        </h2>
        <div className="bg-surface-secondary rounded p-3 whitespace-pre-wrap text-text-primary text-sm leading-relaxed max-h-96 overflow-y-auto">
          {review.submission.content || "(No content)"}
        </div>
      </div>

      <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-text-secondary mb-2">
          Feedback {review.feedback && <span className="text-text-tertiary">(v{review.feedback.version})</span>}
        </h2>
        {published ? (
          <div className="bg-surface-secondary rounded p-3 whitespace-pre-wrap text-text-primary text-sm leading-relaxed">
            {review.feedback?.overall_comment}
          </div>
        ) : (
          <>
            <textarea
              className="w-full h-48 bg-surface-secondary border border-border-subtle rounded p-3 text-text-primary text-sm leading-relaxed resize-y focus:outline-none focus:border-interactive"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Write educational feedback for this response..."
            />
            <p className="text-amber-400 text-xs mt-2">
              Writing feedback is educational guidance and does not represent official Selective School marking.
            </p>
          </>
        )}
      </div>

      {error && <p className="text-error text-sm mb-3">{error}</p>}

      {!published && (
        <div className="flex items-center gap-3">
          <button
            onClick={saveFeedback}
            disabled={busy}
            className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Saving..." : "Save Feedback"}
          </button>
          <button
            onClick={publish}
            disabled={busy || review.status !== "reviewed"}
            className="text-sm bg-success text-white px-4 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            title={review.status !== "reviewed" ? "Save feedback before publishing" : ""}
          >
            Publish to Student
          </button>
        </div>
      )}

      {published && (
        <p className="text-success text-sm">
          Published {review.published_at && `on ${new Date(review.published_at).toLocaleString()}`} — now visible to student and parent.
        </p>
      )}

      <div className="mt-8">
        <Link href="/admin/writing/reviews" className="text-interactive hover:underline text-sm">
          Back to Review Queue
        </Link>
      </div>
    </div>
  );
}
