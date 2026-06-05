"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  type CurriculumDashboard,
  type CoverageReport,
  type FrameworkSummaryItem,
  type OutcomeCoverageItem,
} from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const STATUS_BG = { red: "bg-red-900/30", amber: "bg-amber-900/30", green: "bg-green-900/30" };
const STATUS_BAR = { red: "bg-red-500", amber: "bg-amber-500", green: "bg-green-500" };
const STATUS_TEXT = { red: "text-red-400", amber: "text-amber-400", green: "text-green-400" };

export default function CurriculumDashboardPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <CurriculumDashboard />
    </RoleGuard>
  );
}

function CurriculumDashboard() {
  const [dash, setDash] = useState<CurriculumDashboard | null>(null);
  const [selectedFw, setSelectedFw] = useState<string | null>(null);
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    api.getCurriculumDashboard(token)
      .then(setDash)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
        if (e.status === 403) setError("Unable to load curriculum data.");
        else setError(e.detail ?? "Failed to load dashboard");
      })
      .finally(() => setLoading(false));
  }, []);

  async function selectFramework(id: string) {
    const token = getAccessToken();
    if (!token) return;
    setSelectedFw(id);
    try {
      const rep = await api.getFrameworkCoverage(id, token);
      setCoverage(rep);
    } catch {
      setCoverage(null);
    }
  }

  if (loading) return <p className="p-8 text-text-secondary">Loading curriculum dashboard...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!dash) return <p className="p-8 text-text-secondary">No data available.</p>;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Curriculum Coverage Dashboard</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Content Seeding</p>

      {/* ── Summary Cards ───────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Frameworks" value={dash.total_frameworks} />
        <StatCard label="Outcomes" value={dash.total_outcomes} />
        <StatCard
          label="Coverage"
          value={`${dash.overall_coverage_pct}%`}
          color={dash.overall_coverage_pct < 25 ? "text-error" : dash.overall_coverage_pct < 60 ? "text-amber-400" : "text-success"}
        />
        <StatCard label="Unmapped Qs" value={dash.unmapped_question_count} />
      </div>

      {/* ── Framework Summary Table ─────────────────────────────── */}
      <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden mb-8">
        <h2 className="p-4 text-lg font-semibold text-text-primary border-b border-border-subtle">
          Frameworks
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="text-left p-3 text-text-tertiary">Framework</th>
                <th className="text-center p-3 text-text-tertiary">Outcomes</th>
                <th className="text-center p-3 text-text-tertiary">Coverage</th>
                <th className="text-center p-3 text-text-tertiary">R / A / G</th>
              </tr>
            </thead>
            <tbody>
              {dash.frameworks.map((fw) => (
                <tr
                  key={fw.framework_id}
                  onClick={() => selectFramework(fw.framework_id)}
                  className={`border-b border-border-subtle last:border-0 cursor-pointer hover:bg-white/5 transition-colors ${
                    selectedFw === fw.framework_id ? "bg-white/10" : ""
                  }`}
                >
                  <td className="p-3 text-text-primary font-medium">{fw.framework_name}</td>
                  <td className="p-3 text-center text-text-secondary">{fw.total_outcomes}</td>
                  <td className="p-3 text-center">
                    <span
                      className={
                        fw.coverage_percentage < 25
                          ? "text-error"
                          : fw.coverage_percentage < 60
                          ? "text-amber-400"
                          : "text-success"
                      }
                    >
                      {fw.coverage_percentage}%
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex justify-center gap-1">
                      <span className="text-red-400 text-xs font-medium w-6 text-center">{fw.red_count}</span>
                      <span className="text-amber-400 text-xs font-medium w-6 text-center">{fw.amber_count}</span>
                      <span className="text-green-400 text-xs font-medium w-6 text-center">{fw.green_count}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Selected Framework Detail ───────────────────────────── */}
      {selectedFw && coverage && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">
            {coverage.framework_name} — Outcomes
          </h2>

          {/* Coverage bar */}
          <div className="h-3 bg-canvas rounded-full mb-4 overflow-hidden flex">
            {coverage.red_count > 0 && (
              <div
                className="h-full bg-red-500"
                style={{ width: `${(coverage.red_count / coverage.total_outcomes) * 100}%` }}
              />
            )}
            {coverage.amber_count > 0 && (
              <div
                className="h-full bg-amber-500"
                style={{ width: `${(coverage.amber_count / coverage.total_outcomes) * 100}%` }}
              />
            )}
            {coverage.green_count > 0 && (
              <div
                className="h-full bg-green-500"
                style={{ width: `${(coverage.green_count / coverage.total_outcomes) * 100}%` }}
              />
            )}
          </div>
          <div className="flex gap-4 text-xs text-text-tertiary mb-4">
            <span><span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1" /> Red ({coverage.red_count})</span>
            <span><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1" /> Amber ({coverage.amber_count})</span>
            <span><span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1" /> Green ({coverage.green_count})</span>
          </div>

          <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left p-3 text-text-tertiary">Code</th>
                  <th className="text-left p-3 text-text-tertiary">Title</th>
                  <th className="text-center p-3 text-text-tertiary">Approved</th>
                  <th className="text-center p-3 text-text-tertiary">Draft</th>
                  <th className="text-center p-3 text-text-tertiary">Status</th>
                </tr>
              </thead>
              <tbody>
                {coverage.outcomes.map((o) => (
                  <tr key={o.outcome_id} className={`border-b border-border-subtle last:border-0 ${STATUS_BG[o.coverage_status]}`}>
                    <td className="p-3 text-text-primary font-mono text-xs">{o.code}</td>
                    <td className="p-3 text-text-primary">{o.title}</td>
                    <td className="p-3 text-center text-text-secondary">{o.approved_question_count}</td>
                    <td className="p-3 text-center text-text-secondary">{o.draft_question_count}</td>
                    <td className={`p-3 text-center text-xs font-medium capitalize ${STATUS_TEXT[o.coverage_status]}`}>
                      <span className={`inline-block w-2 h-2 rounded-full ${STATUS_BAR[o.coverage_status]} mr-1`} />
                      {o.coverage_status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Top Content Gaps ────────────────────────────────────── */}
      {dash.top_gaps.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-error mb-3">
            Top Content Gaps
            <span className="text-text-tertiary text-sm ml-2 font-normal">(outcomes with zero questions)</span>
          </h2>
          <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left p-3 text-text-tertiary">Framework</th>
                  <th className="text-left p-3 text-text-tertiary">Code</th>
                  <th className="text-left p-3 text-text-tertiary">Title</th>
                </tr>
              </thead>
              <tbody>
                {dash.top_gaps.slice(0, 15).map((g, i) => (
                  <tr key={i} className="border-b border-border-subtle last:border-0 bg-red-900/10">
                    <td className="p-3 text-text-secondary">{g.framework_name}</td>
                    <td className="p-3 text-text-primary font-mono text-xs">{g.outcome_code}</td>
                    <td className="p-3 text-text-primary">{g.outcome_title}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Footer links ────────────────────────────────────────── */}
      <div className="space-x-4">
        <Link href="/me" className="text-interactive hover:underline text-sm">
          Account
        </Link>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color = "text-text-primary",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}
