"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type SystemDashboard } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function SystemDashboardPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <SystemDashboard />
    </RoleGuard>
  );
}

function SystemDashboard() {
  const [data, setData] = useState<SystemDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }

    api.getSystemDashboard(token)
      .then(setData)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load system dashboard");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-text-secondary">No data</p>;

  const failedCount = data.failed_jobs?.length ?? 0;
  const stuckCount = data.stuck_jobs?.length ?? 0;

  const jobsHealthy = !data.jobs || (
    (data.jobs.ocr_jobs?.failed ?? 0) === 0 &&
    (data.jobs.ai_jobs?.failed ?? 0) === 0 &&
    (data.jobs.import_jobs?.failed ?? 0) === 0 &&
    stuckCount === 0
  );

  return (
    <div className="max-w-6xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">System Dashboard</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Platform Health &amp; Operations</p>

      {/* Health Section */}
      <Section title="Service Health">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatusCard label="Database" status={data.database_status} />
          <StatusCard label="Redis" status={data.redis_status} />
          <StatusCard label="Storage" status={data.storage_status} />
          <StatCard label="Uptime" value={fmtUptime(data.uptime_seconds)} />
          <StatCard label="Memory" value={`${data.memory_usage_mb.toFixed(1)} MB`} />
          <StatCard label="Migration" value={data.migration_version.slice(0, 12)} />
        </div>
      </Section>

      {/* Activity Section */}
      <Section title="Users">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Total Users" value={data.total_users} />
          <StatCard label="Active (24h)" value={data.active_users_24h} />
          <StatCard label="Active Parents" value={data.active_parents_24h} />
          <StatCard label="Active Students" value={data.active_students_24h} />
          <StatCard label="Active Admins" value={data.active_admins_24h} />
        </div>
      </Section>

      {/* Content Section */}
      <Section title="Content">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Questions" value={data.total_questions} />
          <StatCard label="Published" value={data.published_questions} />
          <StatCard label="Exams" value={data.total_exams} />
          <StatCard label="Assignments" value={data.total_assignments} />
        </div>
      </Section>

      {/* Jobs Section */}
      <Section title="Jobs">
        {data.jobs ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <JobCard title="OCR" counts={data.jobs.ocr_jobs} />
            <JobCard title="AI Generation" counts={data.jobs.ai_jobs} />
            <JobCard title="Import" counts={data.jobs.import_jobs} />
          </div>
        ) : (
          <p className="text-text-tertiary text-sm">No job data</p>
        )}

        {/* Failed Jobs */}
        {failedCount > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-error mb-2">
              Failed Jobs ({failedCount})
            </h3>
            <div className="space-y-1 max-h-60 overflow-y-auto">
              {data.failed_jobs.map((j, i) => (
                <div key={i} className="bg-surface border border-border-subtle rounded p-2 text-xs text-text-secondary">
                  <span className="font-mono text-text-tertiary">{j.type}</span>{" "}
                  <span className="font-mono">{j.id.slice(0, 8)}...</span>{" "}
                  {j.error && <span className="text-error">— {j.error.slice(0, 80)}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stuck Jobs */}
        {stuckCount > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-amber-400 mb-2">
              Stuck Jobs ({stuckCount})
            </h3>
            <div className="space-y-1 max-h-60 overflow-y-auto">
              {data.stuck_jobs.map((j, i) => (
                <div key={i} className="bg-surface border border-border-subtle rounded p-2 text-xs text-text-secondary">
                  <span className="font-mono text-text-tertiary">{j.type}</span>{" "}
                  <span className="font-mono">{j.id.slice(0, 8)}...</span>{" "}
                  <span>{j.duration_minutes} min</span>
                  {j.filename && <span className="text-text-tertiary"> — {j.filename}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {!jobsHealthy && (
          <p className="text-amber-400 text-sm mt-2">
            Some jobs require attention — check failed or stuck entries above.
          </p>
        )}
      </Section>

      {/* Database Section */}
      <Section title="Database Tables">
        {data.table_counts ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {Object.entries(data.table_counts).map(([table, count]) => (
              <div key={table} className="bg-surface border border-border-subtle rounded p-3">
                <p className="text-lg font-bold text-text-primary">{count}</p>
                <p className="text-text-tertiary text-xs">{table}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-text-tertiary text-sm">No table data</p>
        )}
      </Section>

      <div className="mt-8 space-x-4">
        <Link href="/admin/curriculum" className="text-interactive hover:underline text-sm">Curriculum Dashboard</Link>
        <Link href="/admin/content/review" className="text-interactive hover:underline text-sm">Content Review</Link>
        <Link href="/admin/content/quality" className="text-interactive hover:underline text-sm">Content Quality</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}


function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-text-primary mb-3">{title}</h2>
      {children}
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

function StatusCard({ label, status }: { label: string; status: string }) {
  const color = status === "ok" ? "text-success" : "text-error";
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{status === "ok" ? "OK" : "ERR"}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}

function JobCard({ title, counts }: { title: string; counts: { total: number; active: number; completed: number; failed: number } | undefined }) {
  if (!counts) return null;
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4">
      <h3 className="text-sm font-semibold text-text-primary mb-2">{title}</h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div><span className="text-text-tertiary">Total:</span> <span className="text-text-primary font-medium">{counts.total}</span></div>
        <div><span className="text-text-tertiary">Active:</span> <span className="text-text-primary font-medium">{counts.active}</span></div>
        <div><span className="text-text-tertiary">Done:</span> <span className="text-success font-medium">{counts.completed}</span></div>
        <div><span className="text-text-tertiary">Failed:</span> <span className={counts.failed > 0 ? "text-error font-medium" : "text-text-primary font-medium"}>{counts.failed}</span></div>
      </div>
    </div>
  );
}

function fmtUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
