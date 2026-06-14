"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

interface Dashboard {
  total_reviews: number;
  unique_questions_reviewed: number;
  average_scores: { correctness: number; outcome_alignment: number; difficulty: number; explanation: number; overall: number };
  needs_revision_count: number;
}

interface SourceItem { source: string; reviewed_count: number; average_score: number }
interface ProviderItem { provider: string; saved_count: number; rejected_count: number; rejection_rate: number; publication_rate: number }
interface OutcomeItem { outcome_code: string; outcome_title: string; total_questions: number; reviewed_count: number; average_quality: number; needs_regeneration: number }
interface RegenItem { question_id: string; review_id: string; overall_score: number; source_type: string; question_status: string; notes: string | null }

export default function QualityDashboardPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <QualityDashboard />
    </RoleGuard>
  );
}

function QualityDashboard() {
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [outcomes, setOutcomes] = useState<OutcomeItem[]>([]);
  const [regen, setRegen] = useState<RegenItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }

    Promise.all([
      api.getQualityDashboard(token),
      api.getQualityByProvider(token),
      api.getQualityByOutcome(token),
      api.getRegenerationCandidates(token),
    ])
      .then(([d, s, o, r]) => {
        setDash(d);
        setSources(s.source || []);
        setProviders(s.providers || []);
        setOutcomes(o);
        setRegen(r);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
        setError(e.detail ?? "Failed to load quality data");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Content Quality</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Quality Review Analytics</p>

      {/* Summary Cards */}
      {dash && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <StatCard label="Reviews" value={dash.total_reviews} />
          <StatCard label="Questions Reviewed" value={dash.unique_questions_reviewed} />
          <StatCard label="Avg Overall" value={dash.average_scores.overall.toFixed(1)} />
          <StatCard label="Needs Revision" value={dash.needs_revision_count} color={dash.needs_revision_count > 0 ? "text-error" : "text-success"} />
          <StatCard label="Avg Correctness" value={dash.average_scores.correctness.toFixed(1)} />
        </div>
      )}

      {/* Source Comparison */}
      {sources.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Source Quality Comparison</h2>
          <Table>
            <thead><tr><Th>Source</Th><Th>Reviewed</Th><Th>Avg Score</Th></tr></thead>
            <tbody>
              {[...sources].sort((a, b) => b.average_score - a.average_score).map((s) => (
                <Tr key={s.source}>
                  <Td className="font-medium">{s.source}</Td>
                  <Td>{s.reviewed_count}</Td>
                  <Td className={s.average_score < 3 ? "text-error" : s.average_score >= 4 ? "text-success" : "text-text-primary"}>{s.average_score.toFixed(1)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      {/* Provider Comparison */}
      {providers.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Provider Performance</h2>
          <Table>
            <thead><tr><Th>Provider</Th><Th>Saved</Th><Th>Rejected</Th><Th>Rejection %</Th><Th>Publication %</Th></tr></thead>
            <tbody>
              {[...providers].sort((a, b) => b.publication_rate - a.publication_rate).map((p) => (
                <Tr key={p.provider}>
                  <Td className="font-medium">{p.provider}</Td>
                  <Td>{p.saved_count}</Td>
                  <Td>{p.rejected_count}</Td>
                  <Td className={p.rejection_rate > 20 ? "text-error" : "text-text-secondary"}>{p.rejection_rate}%</Td>
                  <Td className={p.publication_rate > 80 ? "text-success" : "text-text-primary"}>{p.publication_rate}%</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      {/* Outcome Quality */}
      {outcomes.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Outcome Quality</h2>
          <Table>
            <thead><tr><Th>Outcome</Th><Th>Questions</Th><Th>Reviewed</Th><Th>Avg Quality</Th><Th>Needs Regen</Th></tr></thead>
            <tbody>
              {outcomes.map((o) => (
                <Tr key={o.outcome_code}>
                  <Td className="font-medium text-sm">
                    <span className="text-text-tertiary font-mono text-xs mr-2">{o.outcome_code}</span>
                    {o.outcome_title?.slice(0, 50)}
                  </Td>
                  <Td>{o.total_questions}</Td>
                  <Td>{o.reviewed_count}</Td>
                  <Td className={o.average_quality < 3 ? "text-error" : o.average_quality >= 4 ? "text-success" : "text-text-primary"}>{o.average_quality.toFixed(1)}</Td>
                  <Td className={o.needs_regeneration > 0 ? "text-amber-400 font-medium" : "text-text-tertiary"}>{o.needs_regeneration}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      {/* Regeneration Candidates */}
      {regen.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-error mb-3">Regeneration Candidates</h2>
          <Table>
            <thead><tr><Th>Question ID</Th><Th>Source</Th><Th>Status</Th><Th>Score</Th><Th>Notes</Th></tr></thead>
            <tbody>
              {regen.slice(0, 20).map((r) => (
                <Tr key={r.review_id}>
                  <Td className="font-mono text-xs text-text-tertiary">{r.question_id.slice(0, 12)}...</Td>
                  <Td>{r.source_type}</Td>
                  <Td>{r.question_status}</Td>
                  <Td className="text-error font-medium">{r.overall_score}</Td>
                  <Td className="text-text-secondary text-xs">{r.notes?.slice(0, 80) ?? "—"}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/admin/content/review" className="text-interactive hover:underline text-sm">Content Review</Link>
        <Link href="/admin/curriculum" className="text-interactive hover:underline text-sm">Curriculum Dashboard</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "text-text-primary" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}

function Table({ children }: { children: React.ReactNode }) {
  return <div className="bg-surface border border-border-subtle rounded-lg overflow-x-auto"><table className="w-full text-sm">{children}</table></div>;
}
function Th({ children }: { children: React.ReactNode }) {
  return <th className="text-left p-3 text-text-tertiary text-xs">{children}</th>;
}
function Tr({ children, className }: { children: React.ReactNode; className?: string }) {
  return <tr className={`border-b border-border-subtle last:border-0 ${className ?? ""}`}>{children}</tr>;
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={`p-3 text-text-secondary ${className ?? ""}`}>{children}</td>;
}
