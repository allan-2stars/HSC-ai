"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type WritingSubmissionResponse } from "@/lib/api";
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
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState("");
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
      setSaveError(e.detail ?? "Save failed");
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
    const saved = await doSave();
    if (!saved) {
      setError("Could not save before submitting — check your connection and try again.");
      return;
    }
    try {
      const updated = await api.submitWriting(submissionId, token);
      setSub(updated);
      setSubmitted(true);
    } catch (e: any) {
      setError(e.detail ?? "Failed to submit");
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
          <div className="mt-4 bg-amber-400/5 border border-amber-400/20 rounded p-3">
            <p className="text-amber-400 text-xs">
              Writing feedback is educational guidance and does not represent official Selective School marking.
            </p>
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
