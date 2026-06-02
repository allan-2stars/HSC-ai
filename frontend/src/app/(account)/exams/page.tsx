"use client";

import { useEffect, useState } from "react";
import { api, type ExamAvailable } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import Link from "next/link";

export default function ExamsPage() {
  const [exams, setExams] = useState<ExamAvailable[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      window.location.href = "/login";
      return;
    }

    api.listAvailableExams(token)
      .then(setExams)
      .catch((e) => {
        if (e.status === 401) {
          clearTokens();
          window.location.href = "/login";
        }
        setError(e.detail ?? "Failed to load exams");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-8 text-text-secondary">Loading exams...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">Available Exams</h1>

      {exams.length === 0 ? (
        <p className="text-text-secondary">No exams available right now.</p>
      ) : (
        <div className="space-y-4">
          {exams.map((exam) => (
            <div key={exam.id} className="bg-surface border border-border-subtle rounded-lg p-6">
              <h2 className="text-lg font-semibold text-text-primary">{exam.title}</h2>
              <div className="text-text-secondary text-sm mt-2 space-y-1">
                <p>{exam.question_count} questions &middot; {exam.total_marks} marks</p>
                <p>{exam.duration_minutes} minutes</p>
              </div>
              <Link
                href={`/exams/${exam.id}`}
                className="inline-block mt-4 px-6 py-2 bg-cta text-white rounded-md hover:opacity-90 transition-opacity"
              >
                Start Exam
              </Link>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8">
        <Link href="/me" className="text-interactive hover:underline text-sm">
          &larr; Back to Account
        </Link>
      </div>
    </div>
  );
}
