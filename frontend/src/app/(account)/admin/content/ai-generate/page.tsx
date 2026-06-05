"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

interface SelectOption { id: string; code: string; name: string }
interface OutcomeOption extends SelectOption { framework_id: string }

interface AIQuestion {
  question_text: string;
  options: { label: string; text: string; is_correct: boolean }[];
  correct_answer: string;
  explanation: string;
  difficulty: string;
  curriculum_outcome_code: string;
  provider: string;
  valid: boolean;
  errors: string[];
}

interface PreviewResponse {
  questions: AIQuestion[];
  summary: { total: number; valid: number; invalid: number };
}

interface ExecuteResponse {
  job_id: string;
  saved_count: number;
  rejected_count: number;
}

export default function AIGeneratePage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AIGenerate />
    </RoleGuard>
  );
}

function AIGenerate() {
  const sp = useSearchParams();
  const [frameworks, setFrameworks] = useState<SelectOption[]>([]);
  const [outcomes, setOutcomes] = useState<OutcomeOption[]>([]);
  const [subjects, setSubjects] = useState<SelectOption[]>([]);
  const [examTypes, setExamTypes] = useState<SelectOption[]>([]);

  const [frameworkId, setFrameworkId] = useState("");
  const [outcomeId, setOutcomeId] = useState(sp.get("outcome_id") ?? "");
  const [subjectId, setSubjectId] = useState("");
  const [examTypeId, setExamTypeId] = useState("");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState({ easy: 33, medium: 34, hard: 33 });
  const [provider, setProvider] = useState("mock");

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [result, setResult] = useState<ExecuteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const token = getAccessToken();

  useEffect(() => {
    if (!token) return;
    Promise.all([
      api.listFrameworks(token).catch(() => []),
      api.listSubjects(token).catch(() => []),
      api.listExamTypes(token).catch(() => []),
    ]).then(([fw, subs, exams]) => {
      setFrameworks(fw);
      setSubjects(subs);
      setExamTypes(exams);
      if (subs.length > 0 && !subjectId) setSubjectId(subs[0].id);
      if (exams.length > 0 && !examTypeId) setExamTypeId(exams[0].id);
    });
  }, [token]);

  // When framework changes, load its outcomes
  useEffect(() => {
    if (!frameworkId || !token) return;
    api.listOutcomes(token, frameworkId)
      .then((list) => setOutcomes(list.map((o: any) => ({ ...o, framework_id: o.framework_id }))))
      .catch(() => setOutcomes([]));
  }, [frameworkId, token]);

  const handlePreview = async () => {
    if (!outcomeId || !subjectId || !examTypeId) {
      setError("Please select an outcome, subject, and exam type.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.previewAIGenerate({
        outcome_id: outcomeId,
        subject_id: subjectId,
        exam_type_id: examTypeId,
        count,
        difficulty_mix: difficulty,
        provider,
      }, token);
      setPreview(data);
    } catch (e: any) {
      setError(e.detail ?? "Preview failed");
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!outcomeId || !subjectId || !examTypeId) return;
    setSaving(true);
    setError("");
    try {
      const data = await api.executeAIGenerate({
        outcome_id: outcomeId,
        framework_id: frameworkId || undefined,
        subject_id: subjectId,
        exam_type_id: examTypeId,
        count,
        difficulty_mix: difficulty,
        provider,
      }, token);
      setResult(data);
    } catch (e: any) {
      setError(e.detail ?? "Generation failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">AI Question Generation</h1>
      <p className="text-text-secondary text-sm mb-8">
        Admin · Generate draft questions targeting curriculum gaps
      </p>

      {/* Config */}
      <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-6">
        <h3 className="text-text-primary font-semibold mb-4">Generation Settings</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Framework</label>
            <select value={frameworkId} onChange={(e) => { setFrameworkId(e.target.value); setOutcomeId(""); }}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm">
              <option value="">All frameworks</option>
              {frameworks.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Outcome *</label>
            <select value={outcomeId} onChange={(e) => setOutcomeId(e.target.value)}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm">
              <option value="">Select outcome...</option>
              {outcomes.map((o) => <option key={o.id} value={o.id}>{o.code} — {o.title.slice(0, 40)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Subject *</label>
            <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm">
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Exam Type *</label>
            <select value={examTypeId} onChange={(e) => setExamTypeId(e.target.value)}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm">
              {examTypes.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Count</label>
            <input type="number" min={1} max={50} value={count} onChange={(e) => setCount(Number(e.target.value))}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm" />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Provider</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm">
              <option value="mock">Mock (Development)</option>
              <option value="openai">OpenAI (GPT-4o-mini)</option>
              <option value="claude">Claude (Sonnet 4)</option>
              <option value="deepseek">DeepSeek</option>
              <option value="ollama">Ollama (Local)</option>
            </select>
          </div>
        </div>

        {/* Difficulty */}
        <div className="flex items-center gap-4 mb-4">
          <span className="text-sm text-text-secondary">Difficulty mix:</span>
          {(["easy", "medium", "hard"] as const).map((d) => (
            <label key={d} className="flex items-center gap-1 text-sm text-text-secondary">
              {d}
              <input type="number" min={0} max={100} value={difficulty[d]}
                onChange={(e) => setDifficulty((prev) => ({ ...prev, [d]: Number(e.target.value) }))}
                className="w-16 bg-canvas border border-border-subtle rounded px-2 py-1 text-text-primary text-sm" />
              %
            </label>
          ))}
        </div>

        <div className="flex gap-3">
          <button onClick={handlePreview} disabled={loading}
            className="px-6 py-2 bg-cta text-white rounded-md hover:opacity-90 disabled:opacity-50 transition-opacity">
            {loading ? "Generating..." : "Preview"}
          </button>
        </div>
      </div>

      {error && <p className="mb-4 text-error text-sm">{error}</p>}

      {/* Preview */}
      {preview && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-primary">
              Preview ({preview.summary.valid} valid, {preview.summary.invalid} invalid)
            </h2>
            {preview.summary.valid > 0 && (
              <button onClick={handleExecute} disabled={saving || result !== null}
                className="px-6 py-2 bg-green-700 text-white rounded-md hover:bg-green-600 disabled:opacity-50 transition-colors">
                {saving ? "Saving..." : result ? `${result.saved_count} Saved` : `Save ${preview.summary.valid} Drafts`}
              </button>
            )}
          </div>

          <div className="space-y-4">
            {preview.questions.map((q, i) => (
              <div key={i}
                className={`bg-surface border rounded-lg p-4 ${q.valid ? "border-border-subtle" : "border-error/30"}`}>
                <div className="flex justify-between items-start mb-2">
                  <span className="text-text-tertiary text-xs font-mono">
                    #{i + 1} · {q.difficulty} · {q.provider}
                  </span>
                  {!q.valid && (
                    <span className="text-error text-xs">
                      {q.errors.join("; ")}
                    </span>
                  )}
                </div>
                <p className="text-text-primary font-medium mb-2">{q.question_text}</p>
                <div className="grid grid-cols-2 gap-1 mb-2">
                  {q.options.map((opt) => (
                    <div key={opt.label}
                      className={`text-xs p-1.5 rounded ${opt.is_correct ? "bg-success/10 border border-success/30 text-success" : "bg-canvas border border-border-subtle text-text-secondary"}`}>
                      <span className="font-medium">{opt.label}.</span> {opt.text}
                    </div>
                  ))}
                </div>
                <p className="text-text-tertiary text-xs">{q.explanation.slice(0, 150)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-success/10 border border-success/30 rounded-lg p-6 mb-6">
          <p className="text-success font-medium">
            {result.saved_count} draft questions created ({result.rejected_count} rejected).
          </p>
          <p className="text-text-secondary text-sm mt-2">
            Status: <strong>draft</strong> · Source: <strong>ai</strong>.
            Review and publish them in the Content Review queue.
          </p>
          <Link href="/admin/content/review?source_type=ai"
            className="inline-block mt-3 text-interactive text-sm hover:underline">
            Go to Review Queue (filtered by AI) →
          </Link>
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
