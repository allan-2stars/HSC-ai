"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

interface PreviewData {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  valid: PreviewRow[];
  invalid: { row: number; errors: string[] }[];
  duplicates: { row: number; question_text: string }[];
}

interface PreviewRow {
  row: number;
  stem: string;
  correct_answer: string;
  difficulty: string;
  subject_id: string;
  exam_type_id: string;
  topic_name: string;
  outcome_code: string;
  explanation: string;
  source_type: string;
}

interface ImportResult {
  job_id: string;
  filename: string;
  format: string;
  status: string;
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  duplicate_count: number;
  mapping_count: number;
}

export default function ContentImportPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <ContentImport />
    </RoleGuard>
  );
}

function ContentImport() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [skipDups, setSkipDups] = useState(true);
  const [dragActive, setDragActive] = useState(false);

  const token = getAccessToken();

  const handleFile = useCallback(async (f: File) => {
    if (!token) return;
    setFile(f);
    setPreview(null);
    setResult(null);
    setError("");

    if (!f.name.match(/\.(csv|xlsx|json)$/i)) {
      setError("Unsupported format. Use .csv, .xlsx, or .json");
      return;
    }

    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", f);
      form.append("skip_duplicates", String(skipDups));
      const data = await api.previewImport(form, token);
      setPreview(data);
    } catch (e: any) {
      setError(e.detail ?? "Preview failed");
    } finally {
      setLoading(false);
    }
  }, [token, skipDups]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleImport = async () => {
    if (!file || !token) return;
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("skip_duplicates", String(skipDups));
      const data = await api.executeImport(form, token);
      setResult(data);
    } catch (e: any) {
      setError(e.detail ?? "Import failed");
    } finally {
      setLoading(false);
    }
  };

  const downloadTemplate = async (fmt: string) => {
    if (!token) return;
    try {
      const blob = await api.downloadTemplate(fmt, token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `import_template.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silent
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Bulk Content Import</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Import questions from CSV, XLSX, or JSON</p>

      {/* Templates */}
      <div className="flex items-center gap-3 mb-6">
        <span className="text-text-tertiary text-sm">Download template:</span>
        {["csv", "xlsx", "json"].map((fmt) => (
          <button
            key={fmt}
            onClick={() => downloadTemplate(fmt)}
            className="px-3 py-1 text-xs bg-surface border border-border-subtle text-interactive rounded hover:border-cta transition-colors"
          >
            .{fmt}
          </button>
        ))}
      </div>

      {/* Upload area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors mb-6 ${
          dragActive ? "border-cta bg-cta/5" : "border-border-subtle"
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,.json"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          className="hidden"
        />
        <p className="text-text-secondary mb-3">Drag and drop a file here, or</p>
        <button
          onClick={() => fileRef.current?.click()}
          className="px-6 py-2 bg-cta text-white rounded-md hover:opacity-90 transition-opacity"
        >
          Choose File
        </button>
        <p className="text-text-tertiary text-xs mt-3">.csv, .xlsx, or .json (UTF-8)</p>
        {file && (
          <p className="text-text-primary text-sm mt-3 font-medium">
            Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
          </p>
        )}
      </div>

      {/* Duplicate handling */}
      <label className="flex items-center gap-2 mb-6 text-sm text-text-secondary cursor-pointer">
        <input
          type="checkbox"
          checked={skipDups}
          onChange={(e) => setSkipDups(e.target.checked)}
          className="rounded"
        />
        Skip duplicate questions (same text, subject, exam type)
      </label>

      {error && <p className="mb-4 text-error text-sm">{error}</p>}

      {loading && !preview && !result && (
        <p className="text-text-secondary">Processing file…</p>
      )}

      {/* Preview */}
      {preview && !result && (
        <div className="mb-8">
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <StatCard label="Total" value={preview.total_rows} />
            <StatCard label="Valid" value={preview.valid_count} color="text-success" />
            <StatCard label="Invalid" value={preview.invalid_count} color={preview.invalid_count > 0 ? "text-error" : "text-text-tertiary"} />
            <StatCard label="Duplicates" value={preview.duplicate_count} color={preview.duplicate_count > 0 ? "text-amber-400" : "text-text-tertiary"} />
          </div>

          {/* Valid rows preview */}
          {preview.valid.length > 0 && (
            <div className="mb-6">
              <h3 className="text-text-primary font-semibold mb-2">
                Preview ({Math.min(preview.valid.length, 20)} of {preview.valid.length} valid rows)
              </h3>
              <div className="bg-surface border border-border-subtle rounded-lg overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="text-left p-2 text-text-tertiary">Row</th>
                      <th className="text-left p-2 text-text-tertiary">Question</th>
                      <th className="text-left p-2 text-text-tertiary">Answer</th>
                      <th className="text-left p-2 text-text-tertiary">Subject</th>
                      <th className="text-left p-2 text-text-tertiary">Exam</th>
                      <th className="text-left p-2 text-text-tertiary">Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.valid.slice(0, 20).map((r, i) => (
                      <tr key={i} className="border-b border-border-subtle last:border-0">
                        <td className="p-2 text-text-tertiary">{r.row}</td>
                        <td className="p-2 text-text-primary max-w-xs truncate">{r.stem}</td>
                        <td className="p-2 text-text-secondary">{r.correct_answer}</td>
                        <td className="p-2 text-text-secondary">{r.subject_id}</td>
                        <td className="p-2 text-text-secondary">{r.exam_type_id}</td>
                        <td className="p-2 text-text-secondary">{r.outcome_code || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Invalid rows */}
          {preview.invalid.length > 0 && (
            <div className="mb-6">
              <h3 className="text-error font-semibold mb-2">
                Errors ({preview.invalid.length} rows)
              </h3>
              <div className="bg-surface border border-error/30 rounded-lg p-4 max-h-48 overflow-y-auto">
                {preview.invalid.slice(0, 30).map((e, i) => (
                  <div key={i} className="text-error text-xs py-1">
                    Row {e.row}: {e.errors.join("; ")}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Duplicates */}
          {preview.duplicates.length > 0 && (
            <div className="mb-6">
              <h3 className="text-amber-400 font-semibold mb-2">
                Duplicates ({preview.duplicates.length} rows)
              </h3>
              <div className="bg-surface border border-amber-400/30 rounded-lg p-4 max-h-48 overflow-y-auto">
                {preview.duplicates.slice(0, 20).map((d, i) => (
                  <div key={i} className="text-amber-400 text-xs py-1">
                    Row {d.row}: "{d.question_text.slice(0, 80)}…"
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Import button */}
          {preview.valid_count > 0 && (
            <button
              onClick={handleImport}
              disabled={loading}
              className="px-8 py-3 bg-green-700 text-white rounded-md hover:bg-green-600 disabled:opacity-50 transition-colors font-medium"
            >
              {loading ? "Importing…" : `Import ${preview.valid_count} Questions`}
            </button>
          )}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Import Complete</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <ResultCard label="Imported" value={result.imported_count} color="text-success" />
            <ResultCard label="Skipped" value={result.skipped_count} color="text-text-tertiary" />
            <ResultCard label="Failed" value={result.failed_count} color="text-error" />
            <ResultCard label="Duplicates" value={result.duplicate_count} color="text-amber-400" />
            <ResultCard label="Mappings" value={result.mapping_count} color="text-blue-400" />
          </div>
          <p className="text-text-secondary text-sm mt-4">
            All imported questions are in <strong>Draft</strong> status.
            Review them in the Content Review queue before publication.
          </p>
          <div className="mt-4 space-x-3">
            <Link href="/admin/content/review" className="text-interactive text-sm hover:underline">
              Go to Review Queue →
            </Link>
            <button
              onClick={() => { setResult(null); setPreview(null); setFile(null); }}
              className="text-interactive text-sm hover:underline"
            >
              Import Another File
            </button>
          </div>
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

function StatCard({ label, value, color = "text-text-primary" }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-canvas rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}

function ResultCard({ label, value, color = "text-text-primary" }: { label: string; value: number; color?: string }) {
  return (
    <div className="text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}
