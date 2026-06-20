"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type WritingAnalytics } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";
import { WritingAnalyticsSummary } from "@/components/WritingAnalyticsSummary";

export default function ParentChildAnalyticsPage() {
  return (
    <RoleGuard roles={["parent"]}>
      <ChildAnalyticsView />
    </RoleGuard>
  );
}

function ChildAnalyticsView() {
  const params = useParams();
  const studentId = params.studentId as string;
  const [data, setData] = useState<WritingAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.getStudentWritingAnalytics(studentId, token)
      .then(setData)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load analytics");
      })
      .finally(() => setLoading(false));
  }, [studentId, token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-text-secondary">No data</p>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Writing Analytics</h1>
      <p className="text-text-secondary text-sm mb-8">Your child&apos;s writing performance</p>

      <WritingAnalyticsSummary data={data} />

      <div className="mt-8 space-x-4">
        <Link href="/parent/writing" className="text-interactive hover:underline text-sm">Student Writing</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}
