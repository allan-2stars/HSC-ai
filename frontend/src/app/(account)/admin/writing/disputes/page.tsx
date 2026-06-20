"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type DisputeListItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function AdminDisputesPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AdminDisputes />
    </RoleGuard>
  );
}

function AdminDisputes() {
  const [disputes, setDisputes] = useState<DisputeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reply, setReply] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const token = getAccessToken();

  function load() {
    if (!token) return;
    api.listAllDisputes(token)
      .then(setDisputes)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load disputes");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    load();
  }, [token]);

  async function handleAccept(disputeId: string) {
    if (!token) return;
    setBusy(true);
    try { await api.acceptDispute(disputeId, token); load(); } catch (e: any) { setError(e.detail ?? "Failed"); }
    finally { setBusy(false); }
  }

  async function handleReject(disputeId: string) {
    if (!token || !reply[disputeId]?.trim()) return;
    setBusy(true);
    try { await api.rejectDispute(disputeId, reply[disputeId], token); load(); } catch (e: any) { setError(e.detail ?? "Failed"); }
    finally { setBusy(false); }
  }

  async function handleResolve(disputeId: string) {
    if (!token) return;
    setBusy(true);
    try { await api.resolveDispute(disputeId, token); load(); } catch (e: any) { setError(e.detail ?? "Failed"); }
    finally { setBusy(false); }
  }

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  const open = disputes.filter(d => d.status === "open");
  const resolved = disputes.filter(d => d.status !== "open");

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Disputes</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Manage review disputes ({open.length} open)</p>

      {disputes.length === 0 ? (
        <p className="text-text-tertiary">No disputes yet.</p>
      ) : (
        <div className="space-y-3">
          {disputes.map((d) => (
            <div key={d.id} className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-text-primary font-medium">{d.student_name}</span>
                  <span className="text-text-tertiary text-sm ml-2">— {d.task_title}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  d.status === "open" ? "bg-amber-400/10 text-amber-400" :
                  d.status === "accepted" ? "bg-interactive/10 text-interactive" :
                  d.status === "rejected" ? "bg-error/10 text-error" : "bg-success/10 text-success"
                }`}>{d.status}</span>
              </div>
              <div className="flex gap-3 text-xs text-text-tertiary mb-2">
                <span>Raised by: {d.raised_by_role}</span>
                {d.created_at && <span>{new Date(d.created_at).toLocaleString()}</span>}
              </div>
              <p className="text-text-primary text-sm mb-2 whitespace-pre-wrap">{d.reason}</p>
              {d.admin_response && <p className="text-text-secondary text-xs italic mb-2">Response: {d.admin_response}</p>}

              {d.status === "open" && (
                <div className="flex items-center gap-3 mt-2">
                  <button onClick={() => handleAccept(d.id)} disabled={busy} className="text-sm bg-interactive text-white px-3 py-1 rounded hover:opacity-90 disabled:opacity-50">Accept</button>
                  <div className="flex items-center gap-2">
                    <input className="bg-surface-secondary border border-border-subtle rounded p-1 text-sm text-text-primary w-48" placeholder="Rejection reason..." value={reply[d.id] || ""} onChange={(e) => setReply(p => ({ ...p, [d.id]: e.target.value }))} />
                    <button onClick={() => handleReject(d.id)} disabled={busy || !reply[d.id]?.trim()} className="text-sm border border-border-subtle text-text-secondary px-3 py-1 rounded hover:bg-surface-secondary disabled:opacity-50">Reject</button>
                  </div>
                </div>
              )}

              {d.status === "accepted" && (
                <button onClick={() => handleResolve(d.id)} disabled={busy} className="text-sm bg-success text-white px-3 py-1 rounded hover:opacity-90 disabled:opacity-50 mt-2">Resolve</button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-8">
        <Link href="/admin/writing/reviews" className="text-interactive hover:underline text-sm">Review Queue</Link>
        <span className="mx-2 text-text-tertiary">|</span>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}
