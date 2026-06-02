"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api, type AttemptStartResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import ExamTimer from "@/components/ExamTimer";
import MCQOption from "@/components/MCQOption";

export default function ExamAttemptPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const instanceId = params.instanceId as string;
  const assignmentId = searchParams.get("assignment_id");

  const [data, setData] = useState<AttemptStartResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const questionStartTime = useRef<number>(Date.now());
  const attemptIdRef = useRef<string>("");

  const token = getAccessToken();

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }

    const startFn = assignmentId
      ? api.startAttemptWithAssignment(instanceId, assignmentId, token)
      : api.startAttempt(instanceId, token);

    startFn
      .then((d) => {
        setData(d);
        attemptIdRef.current = d.attempt_id;
      })
      .catch((e) => {
        if (e.status === 401) {
          clearTokens();
          window.location.href = "/login";
        }
        setError(e.detail ?? "Failed to start exam");
      })
      .finally(() => setLoading(false));
  }, [instanceId, token]);

  // ── Integrity event detection ─────────────────────────────────

  const sendEvent = useCallback((eventType: string) => {
    if (!attemptIdRef.current || !token) return;
    api.recordIntegrityEvent(attemptIdRef.current, eventType, token).catch(() => {});
  }, [token]);

  useEffect(() => {
    const onVisibility = () => {
      sendEvent(document.hidden ? "tab_hidden" : "tab_visible");
    };
    const onFullscreenChange = () => {
      sendEvent(document.fullscreenElement ? "fullscreen_enter" : "fullscreen_exit");
    };
    const onCopy = () => sendEvent("copy_attempt");
    const onPaste = () => sendEvent("paste_attempt");

    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("copy", onCopy);
    document.addEventListener("paste", onPaste);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("paste", onPaste);
    };
  }, [sendEvent]);

  const handleSelect = async (questionId: string, option: string) => {
    if (!data || !token) return;

    const now = Date.now();
    const timeSpent = Math.floor((now - questionStartTime.current) / 1000);
    questionStartTime.current = now;

    setAnswers((prev) => ({ ...prev, [questionId]: option }));

    try {
      await api.saveAnswer(data.attempt_id, questionId, option, token, timeSpent);
    } catch {
      // silently fail — answer won't persist on reload
    }
  };

  const handleSubmit = async () => {
    if (!data || !token) return;
    setSubmitting(true);
    setError("");

    try {
      const result = await api.submitAttempt(data.attempt_id, token);
      router.push(`/exams/attempts/${result.attempt_id}`);
    } catch (e: any) {
      setError(e.detail ?? "Failed to submit exam");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p className="p-8 text-text-secondary">Starting exam...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-error">Failed to load exam</p>;

  if (data.questions.length === 0) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <p className="text-text-secondary">This attempt has no questions or has already been completed.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-text-primary">{data.title}</h1>
        <ExamTimer expiresAt={data.expires_at} />
      </div>

      <div className="space-y-8">
        {data.questions.map((q) => (
          <div key={q.exam_instance_question_id} className="bg-surface border border-border-subtle rounded-lg p-6">
            <p className="text-text-primary font-medium mb-1">
              Question {q.order_index + 1}
              <span className="text-text-tertiary text-sm ml-2">({q.marks} mark{q.marks !== 1 ? "s" : ""})</span>
            </p>
            <p className="text-text-primary mb-4">{q.stem}</p>

            <div className="space-y-2">
              {(q.options_json || []).map((opt) => (
                <MCQOption
                  key={opt.label}
                  option={opt}
                  selected={answers[q.exam_instance_question_id] === opt.label}
                  disabled={submitting}
                  showResult={false}
                  onSelect={() => handleSelect(q.exam_instance_question_id, opt.label)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="mt-4 text-error text-sm">{error}</p>}

      <div className="mt-8 flex justify-between items-center">
        <span className="text-text-secondary text-sm">
          {Object.keys(answers).length} of {data.total_questions} answered
        </span>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-8 py-3 bg-cta text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {submitting ? "Submitting..." : "Submit Exam"}
        </button>
      </div>
    </div>
  );
}
