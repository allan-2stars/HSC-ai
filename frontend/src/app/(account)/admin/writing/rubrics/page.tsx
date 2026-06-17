"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingRubric } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function AdminRubricsPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AdminRubrics />
    </RoleGuard>
  );
}

function AdminRubrics() {
  const [rubrics, setRubrics] = useState<WritingRubric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const token = getAccessToken();

  function load() {
    if (!token) return;
    api.listRubrics(token)
      .then(setRubrics)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load rubrics");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Writing Rubrics</h1>
          <p className="text-text-secondary text-sm">Admin · Rubric templates &amp; dimensions</p>
        </div>
        <div className="flex gap-3">
          <Link href="/admin/writing" className="text-sm text-interactive hover:underline">Writing Tasks</Link>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90"
          >
            {showCreate ? "Cancel" : "Create Rubric"}
          </button>
        </div>
      </div>

      {showCreate && (
        <CreateRubricForm token={token!} onCreated={() => { setShowCreate(false); load(); }} />
      )}

      {rubrics.length === 0 ? (
        <p className="text-text-tertiary">No rubrics yet.</p>
      ) : (
        <div className="space-y-3">
          {rubrics.map((r) => (
            <div key={r.id} className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-text-primary font-medium">{r.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  r.active ? "bg-success/10 text-success" : "bg-text-tertiary/10 text-text-tertiary"
                }`}>{r.active ? "active" : "inactive"}</span>
              </div>
              <div className="text-xs text-text-tertiary">
                {r.dimensions.length} dimension{r.dimensions.length === 1 ? "" : "s"}:{" "}
                {r.dimensions.map((d) => d.name).join(", ")}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8">
        <Link href="/admin/writing/reviews" className="text-interactive hover:underline text-sm">Review Queue</Link>
      </div>
    </div>
  );
}

function CreateRubricForm({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [dimensions, setDimensions] = useState<{ name: string; description: string }[]>([
    { name: "", description: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  async function handleCreate() {
    const dims = dimensions.filter((d) => d.name.trim());
    if (!title.trim() || dims.length === 0) {
      setErr("Title and at least one dimension are required.");
      return;
    }
    setSubmitting(true);
    setErr("");
    try {
      await api.createRubric({
        title,
        dimensions: dims.map((d, i) => ({ name: d.name, description: d.description || null, display_order: i + 1 })),
      }, token);
      onCreated();
    } catch (e: any) {
      setErr(e.detail ?? "Failed to create rubric");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6 space-y-3">
      <h3 className="text-text-primary font-medium">New Rubric</h3>
      <input
        className="w-full bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary"
        placeholder="Rubric title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className="space-y-2">
        {dimensions.map((d, i) => (
          <div key={i} className="flex gap-2">
            <input
              className="flex-1 bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary"
              placeholder={`Dimension ${i + 1} name`}
              value={d.name}
              onChange={(e) => setDimensions((prev) => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
            />
            <input
              className="flex-1 bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary"
              placeholder="Description (optional)"
              value={d.description}
              onChange={(e) => setDimensions((prev) => prev.map((x, j) => j === i ? { ...x, description: e.target.value } : x))}
            />
          </div>
        ))}
        <button
          onClick={() => setDimensions((prev) => [...prev, { name: "", description: "" }])}
          className="text-interactive hover:underline text-xs"
        >
          + Add dimension
        </button>
      </div>
      {err && <p className="text-error text-sm">{err}</p>}
      <button
        onClick={handleCreate}
        disabled={submitting}
        className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90 disabled:opacity-50"
      >
        {submitting ? "Creating..." : "Create Rubric"}
      </button>
    </div>
  );
}
