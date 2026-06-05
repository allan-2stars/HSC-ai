"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

interface SelectOption {
  id: string;
  code: string;
  name: string;
}

interface OCRJob {
  id: string;
  filename: string;
  file_format: string;
  status: string;
  questions_detected: number;
  questions_created: number;
  raw_text: string;
  pages: { page_number: number; extracted_text: string; confidence: number }[];
  questions: {
    stem: string;
    correct_answer: string;
    explanation: string;
    options_json: { label: string; text: string; is_correct: boolean; explanation?: string }[] | null;
    confidence: number;
  }[];
  error_message: string | null;
}

export default function OcrPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <OCRImport />
    </RoleGuard>
  );
}

function OCRImport() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [job, setJob] = useState<OCRJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [examTypeId, setExamTypeId] = useState("");
  const [result, setResult] = useState<number | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [subjects, setSubjects] = useState<SelectOption[]>([]);
  const [examTypes, setExamTypes] = useState<SelectOption[]>([]);

  const token = getAccessToken();

  useEffect(() => {
    if (!token) return;
    Promise.all([
      api.listSubjects(token).catch(() => [] as SelectOption[]),
      api.listExamTypes(token).catch(() => [] as SelectOption[]),
    ]).then(([subs, exams]) => {
      setSubjects(subs);
      setExamTypes(exams);
      if (subs.length > 0) setSubjectId(subs[0].id);
      if (exams.length > 0) setExamTypeId(exams[0].id);
    });
  }, [token]);

  const handleUpload = async (fileList: FileList | File) => {
    if (!token) return;
    setJob(null);
    setResult(null);
    setError("");
    setLoading(true);
    setPageIndex(0);

    try {
      const files = fileList instanceof FileList ? Array.from(fileList) : [fileList];
      if (files.length === 0) return;

      const form = new FormData();
      if (files.length > 1) {
        files.forEach((f) => form.append("files", f));
        const data = await api.uploadOcrBulk(form, token);
        setJob(data.jobs?.[0] || null);
      } else {
        form.append("file", files[0]);
        const data = await api.uploadOcrFile(form, token);
        setJob(data);
      }
    } catch (e: any) {
      setError(e.detail ?? "OCR upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleBulkUpload = (fileList: FileList) => {
    if (fileList.length > 1) {
      handleUpload(fileList);
    } else if (fileList.length === 1) {
      handleUpload(fileList[0]);
    }
  };

  const handleCreateDrafts = async () => {
    if (!job || !token || !subjectId || !examTypeId) {
      setError("Please select a Subject and Exam Type before creating drafts.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const data = await api.createOcrDrafts(job.id, subjectId, examTypeId, token);
      setJob(data);
      setResult(data.questions_created);
    } catch (e: any) {
      setError(e.detail ?? "Draft creation failed");
    } finally {
      setCreating(false);
    }
  };

  const currentPage = job?.pages?.[pageIndex];

  return (
    <div className="max-w-6xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">OCR Import</h1>
      <p className="text-text-secondary text-sm mb-8">
        Admin · Extract questions from PDF and image files using OCR
      </p>

      {/* Upload */}
      <div className="border-2 border-dashed border-border-subtle rounded-lg p-12 text-center mb-6">
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp"
          multiple
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              e.target.files.length > 1
                ? handleBulkUpload(e.target.files)
                : handleUpload(e.target.files[0]);
            }
          }}
          className="hidden"
        />
        <p className="text-text-secondary mb-3">
          Upload PDFs or images for OCR extraction
        </p>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={loading}
          className="px-6 py-2 bg-cta text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {loading ? "Processing..." : "Upload Files"}
        </button>
        <p className="text-text-tertiary text-xs mt-3">
          .pdf, .png, .jpg, .jpeg, .webp — select multiple for bulk processing
        </p>
      </div>

      {error && <p className="mb-4 text-error text-sm">{error}</p>}

      {/* Processing state */}
      {loading && (
        <div className="bg-surface border border-border-subtle rounded-lg p-12 text-center mb-6">
          <p className="text-text-secondary">Extracting text and detecting questions...</p>
        </div>
      )}

      {/* OCR Results */}
      {job && !loading && (
        <div className="mb-8">
          {/* Summary */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <StatCard label="Status" value={job.status} />
            <StatCard label="Questions Detected" value={job.questions_detected} />
            <StatCard
              label="Questions Created"
              value={job.questions_created}
              color={job.questions_created > 0 ? "text-success" : "text-text-tertiary"}
            />
          </div>

          {/* Side-by-side: Extracted text + detected questions */}
          <div className="grid md:grid-cols-2 gap-6 mb-6">
            {/* Left: Extracted text with page selector */}
            <div>
              <h3 className="text-text-primary font-semibold mb-2">
                Extracted Text
                {job.pages.length > 1 && (
                  <span className="text-text-tertiary text-sm ml-2 font-normal">
                    Page {pageIndex + 1} of {job.pages.length}
                  </span>
                )}
              </h3>
              {job.pages.length > 1 && (
                <div className="flex gap-2 mb-3">
                  <button
                    onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                    disabled={pageIndex === 0}
                    className="px-2 py-1 text-xs bg-canvas border border-border-subtle text-text-secondary rounded disabled:opacity-30"
                  >
                    Prev
                  </button>
                  <button
                    onClick={() => setPageIndex((p) => Math.min(job.pages.length - 1, p + 1))}
                    disabled={pageIndex >= job.pages.length - 1}
                    className="px-2 py-1 text-xs bg-canvas border border-border-subtle text-text-secondary rounded disabled:opacity-30"
                  >
                    Next
                  </button>
                  <span className="text-xs text-text-tertiary ml-auto self-center">
                    Confidence: {currentPage ? (currentPage.confidence * 100).toFixed(0) : 0}%
                  </span>
                </div>
              )}
              <div className="bg-surface border border-border-subtle rounded-lg p-4 h-96 overflow-y-auto">
                <pre className="text-text-secondary text-sm whitespace-pre-wrap font-sans">
                  {currentPage?.extracted_text || job.raw_text.slice(0, 3000) || "(No text extracted)"}
                </pre>
              </div>
            </div>

            {/* Right: Detected Questions */}
            <div>
              <h3 className="text-text-primary font-semibold mb-2">
                Detected Questions ({job.questions.length})
              </h3>
              <div className="h-96 overflow-y-auto space-y-3">
                {job.questions.length === 0 ? (
                  <p className="text-text-tertiary text-sm">
                    No structured questions detected. Review the extracted text.
                  </p>
                ) : (
                  job.questions.map((q, i) => (
                    <div key={i} className="bg-surface border border-border-subtle rounded-lg p-3">
                      <div className="flex justify-between items-start mb-1">
                        <span className="text-text-tertiary text-xs font-mono">
                          Q{i + 1} · {(q.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                      <p className="text-text-primary text-sm mb-2">{q.stem}</p>
                      {q.options_json && q.options_json.length > 0 && (
                        <div className="grid grid-cols-2 gap-1">
                          {q.options_json.map((opt) => (
                            <div
                              key={opt.label}
                              className={`text-xs p-1.5 rounded ${
                                opt.is_correct
                                  ? "bg-success/10 border border-success/30 text-success"
                                  : "bg-canvas border border-border-subtle text-text-secondary"
                              }`}
                            >
                              <span className="font-medium">{opt.label}.</span> {opt.text}
                            </div>
                          ))}
                        </div>
                      )}
                      {q.explanation && (
                        <p className="text-text-tertiary text-xs mt-1 truncate">
                          {q.explanation.slice(0, 100)}
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Create Drafts */}
          {job.questions_detected > 0 && job.questions_created === 0 && job.status === "completed" && (
            <div className="bg-surface border border-cta rounded-lg p-6 mb-6">
              <h3 className="text-text-primary font-semibold mb-4">Create Draft Questions</h3>
              <p className="text-text-secondary text-sm mb-4">
                Assign a subject and exam type, then create draft questions for review.
              </p>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Subject</label>
                  <select
                    value={subjectId}
                    onChange={(e) => setSubjectId(e.target.value)}
                    className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm"
                  >
                    <option value="">Select subject...</option>
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Exam Type</label>
                  <select
                    value={examTypeId}
                    onChange={(e) => setExamTypeId(e.target.value)}
                    className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-text-primary text-sm"
                  >
                    <option value="">Select exam type...</option>
                    {examTypes.map((e) => (
                      <option key={e.id} value={e.id}>{e.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button
                onClick={handleCreateDrafts}
                disabled={creating || result !== null}
                className="px-6 py-2 bg-green-700 text-white rounded-md hover:bg-green-600 disabled:opacity-50 transition-colors"
              >
                {creating
                  ? "Creating..."
                  : result !== null
                  ? `${result} Drafts Created`
                  : `Create ${job.questions_detected} Draft Questions`}
              </button>
            </div>
          )}

          {/* Success */}
          {result !== null && result > 0 && (
            <div className="bg-success/10 border border-success/30 rounded-lg p-6 mb-6">
              <p className="text-success font-medium">{result} draft questions created.</p>
              <p className="text-text-secondary text-sm mt-2">
                Status: <strong>draft</strong> · Source: <strong>ocr</strong>.
                Review and publish them in the Content Review queue.
              </p>
              <Link
                href="/admin/content/review?source_type=ocr"
                className="inline-block mt-3 text-interactive text-sm hover:underline"
              >
                Go to Review Queue (filtered by OCR) →
              </Link>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/admin/content/review" className="text-interactive hover:underline text-sm">Content Review</Link>
        <Link href="/admin/content/import" className="text-interactive hover:underline text-sm">Bulk Import</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "text-text-primary" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}
