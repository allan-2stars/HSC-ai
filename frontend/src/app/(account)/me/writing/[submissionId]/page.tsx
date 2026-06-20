"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type WritingSubmissionResponse, type WritingFeedbackView, type WritingRubricView, type DisputeItem } from "@/lib/api";

const RATING_LABELS: Record<number, string> = {
  1: "Needs Work",
  2: "Developing",
  3: "Satisfactory",
  4: "Strong",
  5: "Excellent",
};
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const AUTOSAVE_INTERVAL_MS = 5000;

export default function WritingEditorPage() {
  return (
    <RoleGuard roles={["student"]}>
      <WritingEditor />
    </RoleGuard>
  );
}

function WritingEditor() {
  const params = useParams();
  const submissionId = params.submissionId as string;
  const [sub, setSub] = useState<WritingSubmissionResponse | null>(null);
  const [content, setContent] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [feedback, setFeedback] = useState<WritingFeedbackView | null>(null);
  const [rubric, setRubric] = useState<WritingRubricView | null>(null);
  const [disputes, setDisputes] = useState<DisputeItem[]>([]);
  const [disputeReason, setDisputeReason] = useState("");
  const [showDispute, setShowDispute] = useState(false);
  const [disputeBusy, setDisputeBusy] = useState(false);
  const [disputeMsg, setDisputeMsg] = useState("");
  const [dirty, setDirty] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const contentRef = useRef(content);
  const dirtyRef = useRef(dirty);

  const token = getAccessToken();

  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  // Once submitted, try to load published feedback + rubric (404 = not yet published).
  useEffect(() => {
    if (!submitted || !token) return;
    api.getWritingFeedback(submissionId, token)
      .then(setFeedback)
      .catch(() => setFeedback(null));
    api.getSubmissionRubric(submissionId, token)
      .then(setRubric)
      .catch(() => setRubric(null));
    api.listMyWritingDisputes(submissionId, token)
      .then(setDisputes)
      .catch(() => setDisputes([]));
  }, [submitted, submissionId, token]);

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.getWritingSubmission(submissionId, token)
      .then((s) => {
        setSub(s);
        if (s.status === "submitted") {
          setSubmitted(true);
          setContent(s.content);
          setWordCount(s.word_count);
        } else {
          setContent(s.content);
          setWordCount(s.word_count);
        }
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load submission");
      })
      .finally(() => setLoading(false));

    return () => {
      if (saveTimerRef.current) clearInterval(saveTimerRef.current);
    };
  }, [submissionId, token]);

  const doSave = useCallback(async (): Promise<boolean> => {
    if (!token || submitted) return false;
    if (!dirtyRef.current) return true; // skip if unchanged
    const currentContent = contentRef.current;
    const wc = currentContent.trim() ? currentContent.trim().split(/\s+/).length : 0;
    setWordCount(wc);
    try {
      setSaving(true);
      setSaveError("");
      await api.saveWriting(submissionId, currentContent, wc, token);
      setLastSaved(new Date());
      setDirty(false);
      return true;
    } catch (e: any) {
      if (e.status === 401) { clearTokens(); window.location.href = "/login"; return false; }
      setSaveError("Could not save your latest changes. Please check your connection and try again before submitting.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [submissionId, token, submitted]);

  useEffect(() => {
    if (submitted || loading) return;
    saveTimerRef.current = setInterval(() => { doSave(); }, AUTOSAVE_INTERVAL_MS);
    return () => {
      if (saveTimerRef.current) clearInterval(saveTimerRef.current);
    };
  }, [doSave, submitted, loading]);

  async function handleSubmit() {
    if (!token || submitted) return;
    setError("");
    dirtyRef.current = true; // force save even if autosave already ran
    const saved = await doSave();
    if (!saved) return; // saveError is already displayed
    try {
      const updated = await api.submitWriting(submissionId, token);
      setSub(updated);
      setSubmitted(true);
    } catch (e: any) {
      setError(e.detail ?? "Failed to submit");
    }
  }

  async function createDispute() {
    if (!token || !disputeReason.trim()) return;
    setDisputeBusy(true);
    setDisputeMsg("");
    try {
      await api.createWritingDispute(submissionId, disputeReason, token);
      setDisputeReason("");
      setDisputeMsg("Your review request has been submitted.");
      const list = await api.listMyWritingDisputes(submissionId, token);
      setDisputes(list);
    } catch (e: any) {
      setDisputeMsg(e.detail ?? "Failed to submit request");
    } finally {
      setDisputeBusy(false);
    }
  }

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!sub) return <p className="p-8 text-text-secondary">Submission not found</p>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Writing Editor</h1>
          <p className="text-text-secondary text-sm mt-1">Submission ID: {submissionId.slice(0, 8)}...</p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-text-tertiary">
            Words: <span className="text-text-primary font-medium">{wordCount}</span>
          </span>
          {dirty && !saving && <span className="text-xs text-amber-400">Unsaved</span>}
          {saving && <span className="text-xs text-amber-400">Saving...</span>}
          {lastSaved && !saving && !dirty && (
            <span className="text-xs text-text-tertiary">
              Saved {lastSaved.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {saveError && <p className="text-amber-400 text-sm mb-2">{saveError}</p>}

      {submitted ? (
        <div className="bg-surface border border-border-subtle rounded-lg p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-success font-semibold">Submitted</span>
            {sub.submitted_at && (
              <span className="text-text-tertiary text-sm">
                on {new Date(sub.submitted_at).toLocaleString()}
              </span>
            )}
          </div>
          <div className="bg-surface-secondary rounded p-4 whitespace-pre-wrap text-text-primary text-sm leading-relaxed">
            {content || "(No content)"}
          </div>

          {feedback ? (
            <div className="mt-6">
              <h2 className="text-success font-semibold mb-2">Reviewer Feedback</h2>
              <div className="bg-surface-secondary rounded p-4 whitespace-pre-wrap text-text-primary text-sm leading-relaxed">
                {feedback.overall_comment}
              </div>
              {feedback.dimensions && feedback.dimensions.length > 0 && (
                <div className="mt-3 space-y-2">
                  {feedback.dimensions.map((d, i) => (
                    <div key={i} className="text-sm">
                      <span className="text-text-secondary font-medium">{d.name}: </span>
                      <span className="text-text-primary">{d.comment}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-4 bg-amber-400/5 border border-amber-400/20 rounded p-3">
                <p className="text-amber-400 text-xs">{feedback.disclaimer}</p>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-text-tertiary text-sm">
              Your response is awaiting review. Feedback will appear here once published.
            </p>
          )}

          {rubric && (
            <div className="mt-6">
              <h2 className="text-success font-semibold mb-2">Rubric Assessment</h2>
              <p className="text-text-tertiary text-xs mb-3">{rubric.rubric_title}</p>
              <div className="space-y-3">
                {rubric.scores.map((s) => (
                  <div key={s.dimension_id} className="bg-surface-secondary rounded p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-text-primary text-sm font-medium">{s.name}</span>
                      <span className="text-success text-sm">
                        {s.rating}/5 {s.rating ? `— ${RATING_LABELS[s.rating]}` : ""}
                      </span>
                    </div>
                    {s.comment && <p className="text-text-primary text-sm whitespace-pre-wrap">{s.comment}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Dispute / Request Review */}
          <div className="mt-4 border-t border-border-subtle pt-4">
            <button onClick={() => setShowDispute(!showDispute)} className="text-sm text-interactive hover:underline">
              {showDispute ? "Cancel" : "Request a review of this feedback"}
            </button>
            {showDispute && (
              <div className="mt-3 bg-surface-secondary rounded p-3">
                <p className="text-text-secondary text-xs mb-2">Explain why you believe this feedback should be reviewed.</p>
                <textarea className="w-full h-20 bg-surface border border-border-subtle rounded p-2 text-text-primary text-sm resize-y" value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} placeholder="Describe your concern..." />
                <div className="flex items-center gap-3 mt-2">
                  <button onClick={createDispute} disabled={disputeBusy || !disputeReason.trim()} className="text-sm bg-interactive text-white px-3 py-1.5 rounded hover:opacity-90 disabled:opacity-50">
                    {disputeBusy ? "Submitting..." : "Submit Request"}
                  </button>
                  {disputeMsg && <span className={`text-xs ${disputeMsg.includes("submitted") ? "text-success" : "text-error"}`}>{disputeMsg}</span>}
                </div>
              </div>
            )}
            {disputes.length > 0 && (
              <div className="mt-2 space-y-1">
                {disputes.map((d) => (
                  <div key={d.id} className="text-xs text-text-tertiary flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${d.status === "open" ? "bg-amber-400" : d.status === "accepted" ? "bg-interactive" : d.status === "rejected" ? "bg-error" : "bg-success"}`} />
                    <span className="capitalize">{d.status}</span>
                    {d.admin_response && <span>— {d.admin_response.slice(0, 60)}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-4">
            <Link href="/me/writing" className="text-interactive hover:underline text-sm">
              Back to Writing Tasks
            </Link>
          </div>
        </div>
      ) : (
        <>
          <textarea
            className="w-full h-96 bg-surface border border-border-subtle rounded-lg p-4 text-text-primary text-sm leading-relaxed resize-y focus:outline-none focus:border-interactive"
            value={content}
            onChange={(e) => { setContent(e.target.value); setDirty(true); }}
            placeholder="Start writing your response here..."
          />

          <div className="flex items-center justify-between mt-4">
            <Link href="/me/writing" className="text-interactive hover:underline text-sm">
              Back
            </Link>
            <div className="flex items-center gap-3">
              <button
                onClick={() => doSave()}
                className="text-sm text-text-secondary hover:text-text-primary px-3 py-1 border border-border-subtle rounded"
              >
                Save Draft
              </button>
              <button
                onClick={handleSubmit}
                disabled={!content.trim()}
                className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Submit Response
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
