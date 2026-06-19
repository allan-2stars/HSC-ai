"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type WritingReviewDetail, type ReviewScoreInput, type WritingFeedbackDraft, type ScoreSuggestionItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const RATING_LABELS: Record<number, string> = {
  1: "Needs Work",
  2: "Developing",
  3: "Satisfactory",
  4: "Strong",
  5: "Excellent",
};

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
  const [scores, setScores] = useState<Record<string, { rating: number; comment: string }>>({});
  const [drafts, setDrafts] = useState<WritingFeedbackDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftBusy, setDraftBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<ScoreSuggestionItem[]>([]);
  const [suggestionBusy, setSuggestionBusy] = useState(false);

  const token = getAccessToken();

  function load() {
    if (!token) return;
    api.getWritingReview(reviewId, token)
      .then((r) => {
        setReview(r);
        if (r.feedback) setComment(r.feedback.overall_comment);
        if (r.rubric) {
          const initial: Record<string, { rating: number; comment: string }> = {};
          for (const s of r.rubric.scores) {
            initial[s.dimension_id] = { rating: s.rating ?? 3, comment: s.comment ?? "" };
          }
          setScores(initial);
        }
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load review");
      })
      .finally(() => setLoading(false));
  }

  function loadDrafts() {
    if (!token) return;
    api.listAIDrafts(reviewId, token)
      .then(setDrafts)
      .catch(() => { /* drafts are optional; ignore load errors */ });
  }

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    load();
    loadDrafts();
    loadSuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, reviewId]);

  async function generateDraft() {
    if (!token) return;
    setDraftBusy(true);
    setError("");
    try {
      await api.generateAIDraft(reviewId, token);
      loadDrafts();
    } catch (e: any) {
      setError(e.detail ?? "Failed to generate AI draft");
    } finally {
      setDraftBusy(false);
    }
  }

  function copyDraftToFeedback(draft: WritingFeedbackDraft) {
    // Client-side copy into the editable feedback box. The reviewer still
    // reviews/edits and explicitly saves; nothing is published automatically.
    const fb = draft.draft_feedback;
    const section = (title: string, items: string[]) =>
      items.length ? `${title}\n${items.map((i) => `- ${i}`).join("\n")}` : "";
    const text = [
      fb.overall_feedback,
      section("Strengths:", fb.strengths),
      section("Areas for improvement:", fb.improvements),
      section("Next steps:", fb.next_steps),
    ].filter(Boolean).join("\n\n");
    setComment(text);
  }

  async function discardDraft(draftId: string) {
    if (!token) return;
    setDraftBusy(true);
    try {
      await api.discardAIDraft(draftId, token);
      loadDrafts();
    } catch (e: any) {
      setError(e.detail ?? "Failed to discard draft");
    } finally {
      setDraftBusy(false);
    }
  }

  async function loadSuggestions() {
    if (!token) return;
    try {
      const list = await api.listScoreSuggestions(reviewId, token);
      setSuggestions(list);
    } catch { /* suggestions are optional */ }
  }

  async function generateSuggestions() {
    if (!token) return;
    setSuggestionBusy(true);
    setError("");
    try {
      await api.generateScoreSuggestions(reviewId, null, token);
      await loadSuggestions();
    } catch (e: any) {
      setError(e.detail ?? "Failed to generate score suggestions");
    } finally {
      setSuggestionBusy(false);
    }
  }

  async function applySuggestion(suggestionId: string) {
    if (!token) return;
    setSuggestionBusy(true);
    try {
      await api.applyScoreSuggestion(suggestionId, token);
      await loadSuggestions();
      load(); // reload review to show updated scores
    } catch (e: any) {
      setError(e.detail ?? "Failed to apply suggestion");
    } finally {
      setSuggestionBusy(false);
    }
  }

  async function dismissSuggestion(suggestionId: string) {
    if (!token) return;
    setSuggestionBusy(true);
    try {
      await api.dismissScoreSuggestion(suggestionId, token);
      await loadSuggestions();
    } catch (e: any) {
      setError(e.detail ?? "Failed to dismiss suggestion");
    } finally {
      setSuggestionBusy(false);
    }
  }

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

  async function saveScores() {
    if (!token || !review?.rubric) return;
    setBusy(true);
    setError("");
    try {
      const payload: ReviewScoreInput[] = review.rubric.scores.map((s) => ({
        dimension_id: s.dimension_id,
        rating: scores[s.dimension_id]?.rating ?? 3,
        comment: scores[s.dimension_id]?.comment ?? "",
      }));
      await api.scoreReview(reviewId, payload, token);
      load();
    } catch (e: any) {
      setError(e.detail ?? "Failed to save scores");
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

      {review.rubric && (
        <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
          <h2 className="text-sm font-medium text-text-secondary mb-3">
            Rubric · {review.rubric.title}
          </h2>
          <div className="space-y-4">
            {review.rubric.scores.map((dim) => (
              <div key={dim.dimension_id} className="border-b border-border-subtle/40 pb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-text-primary text-sm font-medium">{dim.name}</span>
                  {!published && (
                    <select
                      aria-label={`Rating for ${dim.name}`}
                      className="bg-surface-secondary border border-border-subtle rounded p-1 text-sm text-text-primary"
                      value={scores[dim.dimension_id]?.rating ?? 3}
                      onChange={(e) =>
                        setScores((prev) => ({
                          ...prev,
                          [dim.dimension_id]: {
                            rating: parseInt(e.target.value),
                            comment: prev[dim.dimension_id]?.comment ?? "",
                          },
                        }))
                      }
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>{n} — {RATING_LABELS[n]}</option>
                      ))}
                    </select>
                  )}
                  {published && (
                    <span className="text-success text-sm">
                      {dim.rating} — {dim.rating ? RATING_LABELS[dim.rating] : ""}
                    </span>
                  )}
                </div>
                {dim.description && <p className="text-text-tertiary text-xs mb-1">{dim.description}</p>}
                {published ? (
                  <p className="text-text-primary text-sm whitespace-pre-wrap">{dim.comment}</p>
                ) : (
                  <textarea
                    aria-label={`Comment for ${dim.name}`}
                    className="w-full h-16 bg-surface-secondary border border-border-subtle rounded p-2 text-text-primary text-sm resize-y focus:outline-none focus:border-interactive"
                    value={scores[dim.dimension_id]?.comment ?? ""}
                    onChange={(e) =>
                      setScores((prev) => ({
                        ...prev,
                        [dim.dimension_id]: {
                          rating: prev[dim.dimension_id]?.rating ?? 3,
                          comment: e.target.value,
                        },
                      }))
                    }
                    placeholder={`Comment on ${dim.name}...`}
                  />
                )}
              </div>
            ))}
          </div>
          {!published && (
            <button
              onClick={saveScores}
              disabled={busy}
              className="mt-3 text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90 disabled:opacity-50"
            >
              Save Scores
            </button>
          )}
        </div>
      )}

      {!published && (
        <div className="bg-surface border border-purple-500/30 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-medium text-text-secondary">AI Draft Feedback</h2>
            <button
              onClick={generateDraft}
              disabled={draftBusy}
              className="text-sm bg-purple-600 text-white px-3 py-1.5 rounded hover:opacity-90 disabled:opacity-50"
            >
              {draftBusy ? "Generating..." : "Generate AI Draft"}
            </button>
          </div>
          <p className="text-purple-300 text-xs mb-3">
            AI Draft — not visible to student or parent. The AI does not assign scores or publish;
            review and edit before saving as official feedback.
          </p>

          {drafts.filter((d) => d.status === "generated").length === 0 && (
            <p className="text-text-tertiary text-sm">No AI drafts yet.</p>
          )}

          <div className="space-y-4">
            {drafts.filter((d) => d.status === "generated").map((draft) => (
              <div key={draft.id} className="border border-border-subtle/60 rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-tertiary text-xs">
                    {draft.provider} · {draft.prompt_version}
                    {draft.created_at && ` · ${new Date(draft.created_at).toLocaleString()}`}
                  </span>
                </div>
                <DraftSection title="Strengths" items={draft.draft_feedback.strengths} />
                <DraftSection title="Improvements" items={draft.draft_feedback.improvements} />
                <DraftSection title="Next Steps" items={draft.draft_feedback.next_steps} />
                {draft.draft_feedback.overall_feedback && (
                  <div className="mb-2">
                    <p className="text-text-secondary text-xs font-medium mb-0.5">Overall Feedback</p>
                    <p className="text-text-primary text-sm whitespace-pre-wrap">
                      {draft.draft_feedback.overall_feedback}
                    </p>
                  </div>
                )}
                <div className="flex items-center gap-3 mt-2">
                  <button
                    onClick={() => copyDraftToFeedback(draft)}
                    disabled={draftBusy}
                    className="text-sm bg-interactive text-white px-3 py-1.5 rounded hover:opacity-90 disabled:opacity-50"
                  >
                    Copy to Official Feedback
                  </button>
                  <button
                    onClick={() => discardDraft(draft.id)}
                    disabled={draftBusy}
                    className="text-sm border border-border-subtle text-text-secondary px-3 py-1.5 rounded hover:bg-surface-secondary disabled:opacity-50"
                  >
                    Discard Draft
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!published && review.rubric && (
        <div className="bg-surface border border-amber-400/30 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-medium text-text-secondary">AI Score Suggestions</h2>
            <button
              onClick={generateSuggestions}
              disabled={suggestionBusy}
              className="text-sm bg-amber-500 text-black px-3 py-1.5 rounded hover:opacity-90 disabled:opacity-50"
            >
              {suggestionBusy ? "Generating..." : "Generate Suggestions"}
            </button>
          </div>
          <p className="text-amber-300 text-xs mb-3">
            AI suggestion only — not visible to student or parent. Applying fills the reviewer score without publishing.
          </p>

          {suggestions.length === 0 && (
            <p className="text-text-tertiary text-sm">No AI score suggestions yet.</p>
          )}

          <div className="space-y-3">
            {suggestions.map((s) => (
              <div key={s.id} className="border border-border-subtle/60 rounded p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-text-primary text-sm font-medium">{s.dimension_name ?? "Dimension"}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-amber-400 text-sm font-medium">{s.suggested_rating}/5</span>
                    {s.confidence != null && (
                      <span className="text-text-tertiary text-xs">
                        {Math.round(s.confidence * 100)}% conf
                      </span>
                    )}
                  </div>
                </div>
                {s.suggested_comment && (
                  <p className="text-text-primary text-sm mb-2 whitespace-pre-wrap">{s.suggested_comment}</p>
                )}
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-text-tertiary">{s.provider}</span>
                  {s.status === "generated" && (
                    <>
                      <button onClick={() => applySuggestion(s.id)} disabled={suggestionBusy} className="text-interactive hover:underline">Apply Score</button>
                      <button onClick={() => dismissSuggestion(s.id)} disabled={suggestionBusy} className="text-text-tertiary hover:underline">Dismiss</button>
                    </>
                  )}
                  {s.status !== "generated" && (
                    <span className={`px-1.5 py-0.5 rounded text-xs ${s.status === "applied" ? "bg-success/10 text-success" : "bg-text-tertiary/10 text-text-tertiary"}`}>{s.status}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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

function DraftSection({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mb-2">
      <p className="text-text-secondary text-xs font-medium mb-0.5">{title}</p>
      <ul className="list-disc list-inside text-text-primary text-sm space-y-0.5">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
