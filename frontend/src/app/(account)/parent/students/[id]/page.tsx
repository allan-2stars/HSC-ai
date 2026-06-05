"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type StudentSummary, type TopicPerfItem, type SkillPerfItem, type RecommendationsResponse, type StudentResponse, type TrendItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import TrendChart from "@/components/TrendChart";
import RoleGuard from "@/components/RoleGuard";

export default function StudentAnalyticsPage() {
  return (
    <RoleGuard roles={["parent"]}>
      <StudentAnalytics />
    </RoleGuard>
  );
}

function StudentAnalytics() {
  const params = useParams();
  const studentId = params.id as string;

  const [student, setStudent] = useState<StudentResponse | null>(null);
  const [summary, setSummary] = useState<StudentSummary | null>(null);
  const [topics, setTopics] = useState<TopicPerfItem[]>([]);
  const [skills, setSkills] = useState<SkillPerfItem[]>([]);
  const [recs, setRecs] = useState<RecommendationsResponse | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    Promise.all([
      api.listStudents(token),
      api.getStudentSummary(studentId, token),
      api.getStudentTopics(studentId, token),
      api.getStudentSkills(studentId, token),
      api.getStudentRecommendations(studentId, token),
      api.getStudentTrend(studentId, token),
    ])
      .then(([students, sum, top, skl, rec, tr]) => {
        const s = students.find((s: StudentResponse) => s.id === studentId);
        setStudent(s || null);
        setSummary(sum);
        setTopics(top.topics);
        setSkills(skl.skills);
        setRecs(rec);
        setTrend(tr);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
        if (e.status === 403) setError("Access denied. This is not your student.");
        else setError(e.detail ?? "Failed to load analytics");
      })
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) return <p className="p-8 text-text-secondary">Loading analytics...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!summary) return <p className="p-8 text-text-secondary">No data available.</p>;

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">
        {student?.display_name ?? "Student"}
      </h1>
      <p className="text-text-secondary mb-8 text-sm">Year {student?.year_level ?? "—"}</p>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Attempts" value={summary.total_attempts} />
        <StatCard label="Avg Score" value={`${summary.average_score}%`} />
        <StatCard label="Best Score" value={`${summary.best_score}%`} />
        <StatCard label="Accuracy" value={`${summary.overall_accuracy}%`} />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-8">
        <StatCard label="Questions" value={summary.total_questions_answered} />
        <StatCard label="Correct" value={summary.total_correct_answers} />
      </div>

      {/* Recommendations */}
      {recs && recs.recommendations.length > 0 && (
        <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Recommendations</h2>
          <div className="space-y-2">
            {recs.recommendations.slice(0, 8).map((r, i) => (
              <p key={i} className="text-text-secondary text-sm bg-canvas rounded p-3 border border-border-subtle">
                {r.message}
              </p>
            ))}
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
      {recs && recs.slow_topics.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-amber-400 mb-3">Slow Topics (high effort)</h2>
          <div className="space-y-2">
            {recs.slow_topics.map((t) => (
              <div key={t.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                <span className="text-text-primary text-sm">{t.name}</span>
                <span className="text-amber-400 text-sm font-medium">{t.average_time_seconds}s avg</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strengths & Weaknesses */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-lg font-semibold text-error mb-3">Weakest Topics</h2>
          {recs?.weak_topics.length ? (
            <div className="space-y-2">
              {recs.weak_topics.slice(0, 5).map((t) => (
                <div key={t.id} className="bg-surface border border-border-subtle rounded p-3">
                  <div className="flex justify-between items-center">
                    <span className="text-text-primary text-sm">{t.name}</span>
                    <span className="text-error text-sm font-medium">{t.accuracy_rate}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-text-tertiary text-sm">No weak topics detected.</p>}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-success mb-3">Strongest Topics</h2>
          {recs?.strong_topics.length ? (
            <div className="space-y-2">
              {recs.strong_topics.slice(0, 5).map((t) => (
                <div key={t.id} className="bg-surface border border-border-subtle rounded p-3">
                  <div className="flex justify-between items-center">
                    <span className="text-text-primary text-sm">{t.name}</span>
                    <span className="text-success text-sm font-medium">{t.accuracy_rate}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-text-tertiary text-sm">No strong topics yet.</p>}
        </div>
      </div>

      {/* Topic Performance Table */}
      {topics.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Topic Performance</h2>
          <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left p-3 text-text-tertiary">Topic</th>
                  <th className="text-center p-3 text-text-tertiary">Attempts</th>
                  <th className="text-center p-3 text-text-tertiary">Correct</th>
                  <th className="text-right p-3 text-text-tertiary">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {topics.map((t) => (
                  <tr key={t.topic_id} className="border-b border-border-subtle last:border-0">
                    <td className="p-3 text-text-primary">{t.topic_name}</td>
                    <td className="p-3 text-center text-text-secondary">{t.attempts}</td>
                    <td className="p-3 text-center text-text-secondary">{t.correct_count}</td>
                    <td className={`p-3 text-right font-medium ${t.accuracy_rate < 60 ? "text-error" : t.accuracy_rate > 85 ? "text-success" : "text-text-primary"}`}>
                      {t.accuracy_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Skill Performance Table */}
      {skills.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Skill Performance</h2>
          <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left p-3 text-text-tertiary">Skill</th>
                  <th className="text-center p-3 text-text-tertiary">Attempts</th>
                  <th className="text-center p-3 text-text-tertiary">Correct</th>
                  <th className="text-right p-3 text-text-tertiary">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {skills.map((s) => (
                  <tr key={s.skill_id} className="border-b border-border-subtle last:border-0">
                    <td className="p-3 text-text-primary">{s.skill_name}</td>
                    <td className="p-3 text-center text-text-secondary">{s.attempts}</td>
                    <td className="p-3 text-center text-text-secondary">{s.correct_count}</td>
                    <td className={`p-3 text-right font-medium ${s.accuracy_rate < 60 ? "text-error" : s.accuracy_rate > 85 ? "text-success" : "text-text-primary"}`}>
                      {s.accuracy_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="space-x-4">
        <Link href="/parent" className="text-interactive hover:underline text-sm">&larr; Back to Dashboard</Link>
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
