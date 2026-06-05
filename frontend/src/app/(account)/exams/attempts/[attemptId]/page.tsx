"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type AttemptResultResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import MCQOption from "@/components/MCQOption";
import RoleGuard from "@/components/RoleGuard";

export default function ExamResultPage() {
  return (
    <RoleGuard roles={["student"]}>
      <ExamResult />
    </RoleGuard>
  );
}

function ExamResult() {
  const params = useParams();
  const attemptId = params.attemptId as string;

  const [data, setData] = useState<AttemptResultResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      window.location.href = "/login";
      return;
    }

    api.getAttemptResult(attemptId, token)
      .then(setData)
      .catch((e) => {
        if (e.status === 401) {
          clearTokens();
          window.location.href = "/login";
        }
        setError(e.detail ?? "Failed to load result");
      })
      .finally(() => setLoading(false));
  }, [attemptId]);

  if (loading) return <p className="p-8 text-text-secondary">Loading result...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-error">Failed to load result</p>;

  const isExpired = data.status === "expired";

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-text-primary">{data.title}</h1>
        <p className="text-text-secondary mt-1">Exam Result</p>
        {isExpired && (
          <p className="text-yellow-400 mt-2 text-sm">This exam was submitted after the time limit.</p>
        )}
      </div>

      <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-8">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-3xl font-bold text-cta">{data.score_percent}%</p>
            <p className="text-text-tertiary text-sm mt-1">Score</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-text-primary">{data.correct_count}/{data.total_questions}</p>
            <p className="text-text-tertiary text-sm mt-1">Correct</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-text-primary">{data.score_raw}</p>
            <p className="text-text-tertiary text-sm mt-1">Marks</p>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-text-primary">Review</h2>
        {data.questions.map((q) => (
          <div
            key={q.exam_instance_question_id}
            className={`bg-surface border rounded-lg p-6 ${
              q.is_correct ? "border-success" : "border-error"
            }`}
          >
            <div className="flex justify-between items-start mb-2">
              <p className="text-text-primary font-medium">Question {q.order_index + 1}</p>
              <span className={`text-sm font-medium ${q.is_correct ? "text-success" : "text-error"}`}>
                {q.is_correct ? "Correct" : q.selected_option ? "Incorrect" : "Unanswered"}
                {" "}({q.marks_awarded}/{q.marks} mark{q.marks !== 1 ? "s" : ""})
              </span>
            </div>
            <p className="text-text-primary mb-4">{q.stem}</p>

            <div className="space-y-2">
              {(q.options_json || []).map((opt) => (
                <MCQOption
                  key={opt.label}
                  option={opt}
                  selected={q.selected_option === opt.label}
                  disabled={true}
                  showResult={true}
                  onSelect={() => {}}
                />
              ))}
            </div>

            {q.full_explanation && (
              <div className="mt-4 p-3 bg-canvas rounded border border-border-subtle">
                <p className="text-text-secondary text-sm">{q.full_explanation}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-8 space-x-4">
        <Link href="/exams" className="text-interactive hover:underline text-sm">
          &larr; Back to Exams
        </Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">
          Account
        </Link>
      </div>
    </div>
  );
}
