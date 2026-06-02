"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type StudentProgressResponse, type ExamHistoryItem, type TrendItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import TrendChart from "@/components/TrendChart";

export default function StudentProgressPage() {
  const [progress, setProgress] = useState<StudentProgressResponse | null>(null);
  const [history, setHistory] = useState<ExamHistoryItem[]>([]);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    Promise.all([
      api.getMyProgress(token),
      api.getMyHistory(token),
      api.getMyTrend(token),
    ])
      .then(([prog, hist, tr]) => {
        setProgress(prog);
        setHistory(hist);
        setTrend(tr);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
        setError(e.detail ?? "Failed to load progress");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-8 text-text-secondary">Loading your progress...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!progress) return <p className="p-8 text-text-secondary">No data available.</p>;

  const { summary } = progress;

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">My Progress</h1>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Exams Taken" value={summary.total_attempts} />
        <StatCard label="Average" value={`${summary.average_score}%`} />
        <StatCard label="Best" value={`${summary.best_score}%`} />
        <StatCard label="Accuracy" value={`${summary.overall_accuracy}%`} />
      </div>

      {/* Recent History */}
      {history.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Recent Exams</h2>
          <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left p-3 text-text-tertiary">Exam</th>
                  <th className="text-center p-3 text-text-tertiary">Score</th>
                  <th className="text-center p-3 text-text-tertiary">Correct</th>
                  <th className="text-right p-3 text-text-tertiary">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.attempt_id} className="border-b border-border-subtle last:border-0">
                    <td className="p-3 text-text-primary">
                      <Link href={`/exams/attempts/${h.attempt_id}`} className="hover:text-cta transition-colors">
                        {h.exam_title}
                      </Link>
                    </td>
                    <td className={`p-3 text-center font-medium ${(h.score_percent ?? 0) >= 70 ? "text-success" : (h.score_percent ?? 0) >= 50 ? "text-text-primary" : "text-error"}`}>
                      {h.score_percent ?? "—"}%
                    </td>
                    <td className="p-3 text-center text-text-secondary">{h.correct_count}/{h.total_questions}</td>
                    <td className="p-3 text-right text-text-tertiary">
                      {h.completed_at ? new Date(h.completed_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trend Chart */}
      {trend.length > 0 && (
        <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Score Trend</h2>
          <TrendChart
            data={trend.map((t) => ({
              label: new Date(t.completed_at).toLocaleDateString(),
              value: t.score_percent,
            }))}
          />
        </div>
      )}

      {/* Slow Topics */}
      {progress.slow_topics && progress.slow_topics.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-amber-400 mb-3">Slow Topics (high effort)</h2>
          <div className="space-y-2">
            {progress.slow_topics.map((t) => (
              <div key={t.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                <span className="text-text-primary text-sm">{t.name}</span>
                <span className="text-amber-400 text-sm font-medium">{t.average_time_seconds}s avg</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strengths */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-lg font-semibold text-success mb-3">Strengths</h2>
          {progress.strong_topics.length > 0 || progress.strong_skills.length > 0 ? (
            <div className="space-y-2">
              {progress.strong_topics.slice(0, 3).map((t) => (
                <div key={t.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                  <span className="text-text-primary text-sm">{t.name}</span>
                  <span className="text-success text-sm font-medium">{t.accuracy_rate}%</span>
                </div>
              ))}
              {progress.strong_skills.slice(0, 3).map((s) => (
                <div key={s.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                  <span className="text-text-primary text-sm">{s.name}</span>
                  <span className="text-success text-sm font-medium">{s.accuracy_rate}%</span>
                </div>
              ))}
            </div>
          ) : <p className="text-text-tertiary text-sm">Keep practicing to build strengths.</p>}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-error mb-3">Areas to Improve</h2>
          {progress.weak_topics.length > 0 || progress.weak_skills.length > 0 ? (
            <div className="space-y-2">
              {progress.weak_topics.slice(0, 3).map((t) => (
                <div key={t.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                  <span className="text-text-primary text-sm">{t.name}</span>
                  <span className="text-error text-sm font-medium">{t.accuracy_rate}%</span>
                </div>
              ))}
              {progress.weak_skills.slice(0, 3).map((s) => (
                <div key={s.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                  <span className="text-text-primary text-sm">{s.name}</span>
                  <span className="text-error text-sm font-medium">{s.accuracy_rate}%</span>
                </div>
              ))}
            </div>
          ) : <p className="text-text-tertiary text-sm">Not enough data to identify areas to improve.</p>}
        </div>
      </div>

      <div className="space-x-4">
        <Link href="/exams" className="text-interactive hover:underline text-sm">Available Exams</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className="text-2xl font-bold text-text-primary">{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}
