const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw { status: res.status, detail: body.detail ?? "Request failed" };
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  refresh_token: string;
}

export interface MeResponse {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface StudentResponse {
  id: string;
  display_name: string;
  year_level: number | null;
  first_login_completed: boolean;
  login_email?: string;
  temp_password?: string;
}

// ── Exam Engine Types ────────────────────────────────────────

export interface ExamAvailable {
  id: string;
  title: string;
  duration_minutes: number;
  question_count: number;
  total_marks: number;
}

export interface AttemptQuestion {
  exam_instance_question_id: string;
  question_id: string;
  question_version_id: string;
  stem: string;
  correct_answer: string | null;
  full_explanation: string;
  marks: number;
  options_json: { label: string; text: string; is_correct: boolean; explanation?: string }[] | null;
  order_index: number;
}

export interface AttemptStartResponse {
  attempt_id: string;
  exam_instance_id: string;
  title: string;
  duration_minutes: number;
  started_at: string;
  expires_at: string;
  total_questions: number;
  questions: AttemptQuestion[];
}

export interface AttemptAnswerResponse {
  id: string;
  exam_instance_question_id: string;
  selected_option: string | null;
  is_correct: boolean | null;
  answered_at: string;
}

export interface AttemptSubmitResponse {
  attempt_id: string;
  status: string;
  score_raw: number;
  score_percent: number;
  total_questions: number;
  correct_count: number;
  submitted_at: string;
}

export interface AttemptResultQuestion {
  exam_instance_question_id: string;
  question_id: string;
  stem: string;
  correct_answer: string | null;
  full_explanation: string;
  marks: number;
  options_json: { label: string; text: string; is_correct: boolean; explanation?: string }[] | null;
  order_index: number;
  selected_option: string | null;
  is_correct: boolean | null;
  marks_awarded: number;
}

export interface AttemptResultResponse {
  attempt_id: string;
  exam_instance_id: string;
  title: string;
  status: string;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  score_raw: number | null;
  score_percent: number | null;
  total_questions: number;
  correct_count: number | null;
  questions: AttemptResultQuestion[];
}

export interface AttemptListEntry {
  id: string;
  exam_instance_id: string;
  exam_title: string;
  status: string;
  started_at: string;
  submitted_at: string | null;
  score_percent: number | null;
  total_questions: number;
  correct_count: number | null;
}

export interface StudentSummary {
  total_attempts: number;
  average_score: number;
  best_score: number;
  latest_score: number;
  total_questions_answered: number;
  total_correct_answers: number;
  overall_accuracy: number;
}

export interface TopicPerfItem {
  topic_id: string;
  topic_name: string;
  attempts: number;
  correct_count: number;
  accuracy_rate: number;
}

export interface SkillPerfItem {
  skill_id: string;
  skill_name: string;
  attempts: number;
  correct_count: number;
  accuracy_rate: number;
}

export interface WeakStrongItem {
  id: string;
  name: string;
  accuracy_rate: number;
  attempts: number;
}

export interface RecommendationItem {
  type: string;
  target_id: string;
  target_name: string;
  message: string;
}

export interface SlowTopicItem {
  id: string;
  name: string;
  average_time_seconds: number;
  attempts: number;
}

export interface RecommendationsResponse {
  weak_topics: WeakStrongItem[];
  strong_topics: WeakStrongItem[];
  weak_skills: WeakStrongItem[];
  strong_skills: WeakStrongItem[];
  slow_topics: SlowTopicItem[];
  recommendations: RecommendationItem[];
}

export interface StudentProgressResponse {
  summary: StudentSummary;
  weak_topics: WeakStrongItem[];
  strong_topics: WeakStrongItem[];
  weak_skills: WeakStrongItem[];
  strong_skills: WeakStrongItem[];
  slow_topics: SlowTopicItem[];
}

export interface TrendItem {
  completed_at: string;
  score_percent: number;
  exam_title: string;
}

export interface AssignmentItem {
  id: string;
  student_id: string;
  exam_instance_id: string;
  title_snapshot: string;
  due_at: string | null;
  status: "assigned" | "started" | "completed" | "overdue" | "cancelled";
  student_name?: string | null;
  created_at: string;
}

export interface AssignmentSummary {
  assigned: number;
  started: number;
  completed: number;
  overdue: number;
  cancelled: number;
}

export interface CurriculumFramework {
  id: string;
  name: string;
  description: string | null;
  exam_type_id: string | null;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CurriculumOutcome {
  id: string;
  framework_id: string;
  code: string;
  title: string;
  description: string | null;
  sort_order: number;
  created_at: string;
}

export interface OutcomeCoverageItem {
  outcome_id: string;
  code: string;
  title: string;
  approved_question_count: number;
  draft_question_count: number;
  total_question_count: number;
  coverage_status: "red" | "amber" | "green";
}

export interface CoverageReport {
  framework_id: string;
  framework_name: string;
  total_outcomes: number;
  mapped_outcomes: number;
  covered_outcomes: number;
  coverage_percentage: number;
  red_count: number;
  amber_count: number;
  green_count: number;
  outcomes: OutcomeCoverageItem[];
}

export interface FrameworkSummaryItem {
  framework_id: string;
  framework_name: string;
  total_outcomes: number;
  mapped_outcomes: number;
  covered_outcomes: number;
  coverage_percentage: number;
  red_count: number;
  amber_count: number;
  green_count: number;
}

export interface TopGapItem {
  framework_name: string;
  outcome_code: string;
  outcome_title: string;
  outcome_id: string;
}

export interface CurriculumDashboard {
  overall_coverage_pct: number;
  total_frameworks: number;
  total_outcomes: number;
  total_mapped: number;
  total_covered: number;
  unmapped_question_count: number;
  all_red_outcome_count: number;
  frameworks: FrameworkSummaryItem[];
  top_gaps: TopGapItem[];
}

export interface QuestionItem {
  id: string;
  subject_id: string;
  exam_type_id: string;
  year_level: number;
  difficulty: string;
  question_type: string;
  status: string;
  source_type: string;
  content_ownership: string;
  quality_score: number | null;
  review_notes: string | null;
  current_version: { id: string; stem: string; version_number: number } | null;
  created_at: string;
  updated_at: string;
}

export interface ContentStats {
  total: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
  published_this_week: number;
  published_this_month: number;
}

export interface ExamHistoryItem {
  attempt_id: string;
  exam_title: string;
  status: string;
  score_percent: number | null;
  total_questions: number;
  correct_count: number | null;
  completed_at: string | null;
}

export const api = {
  register: (email: string, password: string, display_name: string) =>
    request<TokenResponse>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: (refresh_token: string, token: string) =>
    request<void>("/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    }, token),

  me: (token: string) => request<MeResponse>("/v1/me", {}, token),

  listStudents: (token: string) =>
    request<StudentResponse[]>("/v1/parents/students", {}, token),

  createStudent: (
    display_name: string,
    year_level: number | null,
    token: string,
  ) =>
    request<StudentResponse>("/v1/parents/students", {
      method: "POST",
      body: JSON.stringify({ display_name, year_level }),
    }, token),

  // ── Exam Engine ────────────────────────────────────────────

  listAvailableExams: (token: string) =>
    request<ExamAvailable[]>("/v1/exams/available", {}, token),

  startAttempt: (instanceId: string, token: string) =>
    request<AttemptStartResponse>(`/v1/exams/${instanceId}/attempts/start`, {
      method: "POST",
    }, token),

  getAttempt: (attemptId: string, token: string) =>
    request<AttemptStartResponse>(`/v1/attempts/${attemptId}`, {}, token),

  saveAnswer: (
    attemptId: string,
    examInstanceQuestionId: string,
    selectedOption: string | null,
    token: string,
    timeSpentSeconds: number = 0,
  ) =>
    request<AttemptAnswerResponse>(`/v1/attempts/${attemptId}/answers`, {
      method: "PATCH",
      body: JSON.stringify({
        exam_instance_question_id: examInstanceQuestionId,
        selected_option: selectedOption,
        time_spent_seconds: timeSpentSeconds,
      }),
    }, token),

  submitAttempt: (attemptId: string, token: string) =>
    request<AttemptSubmitResponse>(`/v1/attempts/${attemptId}/submit`, {
      method: "POST",
    }, token),

  getAttemptResult: (attemptId: string, token: string) =>
    request<AttemptResultResponse>(`/v1/attempts/${attemptId}/result`, {}, token),

  listMyAttempts: (token: string) =>
    request<AttemptListEntry[]>(`/v1/students/me/attempts`, {}, token),

  // ── Analytics ─────────────────────────────────────────────────

  getStudentSummary: (studentId: string, token: string) =>
    request<StudentSummary>(`/v1/parents/students/${studentId}/analytics/summary`, {}, token),

  getStudentTopics: (studentId: string, token: string) =>
    request<{ topics: TopicPerfItem[] }>(`/v1/parents/students/${studentId}/analytics/topics`, {}, token),

  getStudentSkills: (studentId: string, token: string) =>
    request<{ skills: SkillPerfItem[] }>(`/v1/parents/students/${studentId}/analytics/skills`, {}, token),

  getStudentRecommendations: (studentId: string, token: string) =>
    request<RecommendationsResponse>(`/v1/parents/students/${studentId}/analytics/recommendations`, {}, token),

  getStudentTrend: (studentId: string, token: string, limit: number = 20) =>
    request<TrendItem[]>(`/v1/parents/students/${studentId}/analytics/trend?limit=${limit}`, {}, token),

  getMyProgress: (token: string) =>
    request<StudentProgressResponse>("/v1/students/me/progress", {}, token),

  getMyTrend: (token: string, limit: number = 20) =>
    request<TrendItem[]>(`/v1/students/me/trend?limit=${limit}`, {}, token),

  getMyHistory: (token: string) =>
    request<ExamHistoryItem[]>("/v1/students/me/history", {}, token),

  // ── Assignments ───────────────────────────────────────────────

  createAssignment: (studentId: string, examInstanceId: string, dueAt: string | null, token: string) =>
    request<AssignmentItem>(`/v1/parents/students/${studentId}/assignments`, {
      method: "POST",
      body: JSON.stringify({ exam_instance_id: examInstanceId, due_at: dueAt }),
    }, token),

  listStudentAssignments: (studentId: string, token: string) =>
    request<AssignmentItem[]>(`/v1/parents/students/${studentId}/assignments`, {}, token),

  listAllAssignments: (token: string) =>
    request<AssignmentItem[]>(`/v1/parents/assignments`, {}, token),

  updateAssignment: (assignmentId: string, data: { due_at?: string | null; status?: string }, token: string) =>
    request<AssignmentItem>(`/v1/assignments/${assignmentId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }, token),

  getAssignmentSummary: (studentId: string, token: string) =>
    request<AssignmentSummary>(`/v1/parents/students/${studentId}/assignment-summary`, {}, token),

  getMyAssignments: (token: string) =>
    request<AssignmentItem[]>("/v1/students/me/assignments", {}, token),

  getMyAssignment: (assignmentId: string, token: string) =>
    request<AssignmentItem>(`/v1/students/me/assignments/${assignmentId}`, {}, token),

  startAttemptWithAssignment: (instanceId: string, assignmentId: string, token: string) =>
    request<AttemptStartResponse>(`/v1/exams/${instanceId}/attempts/start?assignment_id=${assignmentId}`, {
      method: "POST",
    }, token),

  // ── Curriculum ───────────────────────────────────────────────

  getCurriculumDashboard: (token: string) =>
    request<CurriculumDashboard>("/v1/curriculum/dashboard", {}, token),

  listFrameworks: (token: string) =>
    request<CurriculumFramework[]>("/v1/curriculum/frameworks", {}, token),

  getFrameworkCoverage: (frameworkId: string, token: string) =>
    request<CoverageReport>(`/v1/curriculum/coverage/${frameworkId}`, {}, token),

  getUnmappedQuestions: (token: string) =>
    request<{ question_id: string; stem: string; status: string; subject_name: string | null }[]>(
      "/v1/curriculum/unmapped-questions", {}, token
    ),

  // ── Integrity ────────────────────────────────────────────────

  recordIntegrityEvent: (attemptId: string, eventType: string, token: string) =>
    request<void>(`/v1/attempts/${attemptId}/integrity-event`, {
      method: "POST",
      body: JSON.stringify({ event_type: eventType }),
    }, token),

  // ── Content Review ─────────────────────────────────────────────

  listReviewQueue: (filters: Record<string, string | undefined>, token: string) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    const qs = params.toString();
    return request<QuestionItem[]>(`/v1/admin/content/review${qs ? `?${qs}` : ""}`, {}, token);
  },

  submitForReview: (questionId: string, token: string, qualityScore?: number, reviewNotes?: string) =>
    request<QuestionItem>(`/v1/admin/content/questions/${questionId}/submit-review`, {
      method: "POST",
      body: JSON.stringify({ quality_score: qualityScore, review_notes: reviewNotes }),
    }, token),

  approveQuestion: (questionId: string, token: string) =>
    request<QuestionItem>(`/v1/admin/content/questions/${questionId}/approve`, {
      method: "POST",
    }, token),

  publishQuestion: (questionId: string, token: string) =>
    request<QuestionItem>(`/v1/admin/content/questions/${questionId}/publish`, {
      method: "POST",
    }, token),

  archiveQuestion: (questionId: string, token: string) =>
    request<QuestionItem>(`/v1/admin/content/questions/${questionId}/archive`, {
      method: "POST",
    }, token),

  bulkAction: (questionIds: string[], action: string, token: string) =>
    request<{ action: string; affected: number }>(`/v1/admin/content/bulk-action`, {
      method: "POST",
      body: JSON.stringify({ question_ids: questionIds, action }),
    }, token),

  getContentStats: (token: string) =>
    request<ContentStats>(`/v1/admin/content/stats`, {}, token),

  // ── OCR Import ────────────────────────────────────────────────

  listSubjects: (token: string) =>
    request<{ id: string; code: string; name: string }[]>("/v1/admin/subjects", {}, token),

  listExamTypes: (token: string) =>
    request<{ id: string; code: string; name: string }[]>("/v1/admin/exam-types", {}, token),

  async uploadOcrFile(formData: FormData, token: string) {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    const res = await fetch(`${API_BASE}/v1/admin/content/ocr/upload`, { method: "POST", headers, body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw { status: res.status, detail: body.detail ?? "OCR upload failed" };
    }
    return res.json();
  },

  async uploadOcrBulk(formData: FormData, token: string) {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    const res = await fetch(`${API_BASE}/v1/admin/content/ocr/upload-bulk`, { method: "POST", headers, body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw { status: res.status, detail: body.detail ?? "Bulk OCR upload failed" };
    }
    return res.json();
  },

  async createOcrDrafts(jobId: string, subjectId: string, examTypeId: string, token: string) {
    const headers: Record<string, string> = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
    const res = await fetch(`${API_BASE}/v1/admin/content/ocr/${jobId}/create-drafts`, {
      method: "POST",
      headers,
      body: JSON.stringify({ subject_id: subjectId, exam_type_id: examTypeId }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw { status: res.status, detail: body.detail ?? "Draft creation failed" };
    }
    return res.json();
  },

  // ── Quality Review ─────────────────────────────────────────────

  createQualityReview: (body: { question_id: string; correctness_score?: number; outcome_alignment_score?: number; difficulty_score?: number; explanation_score?: number; overall_score?: number; notes?: string | null }, token: string) =>
    request<any>(`/v1/admin/content/quality-review`, { method: "POST", body: JSON.stringify(body) }, token),

  getQualityDashboard: (token: string) =>
    request<any>(`/v1/admin/content/quality-dashboard`, {}, token),

  getQualityByProvider: (token: string) =>
    request<{ source: { source: string; reviewed_count: number; average_score: number }[]; providers: { provider: string; saved_count: number; rejected_count: number; rejection_rate: number; publication_rate: number }[] }>(`/v1/admin/content/quality-by-provider`, {}, token),

  getQualityByOutcome: (token: string) =>
    request<{ outcome_code: string; outcome_title: string; total_questions: number; reviewed_count: number; average_quality: number; needs_regeneration: number }[]>(`/v1/admin/content/quality-by-outcome`, {}, token),

  getRegenerationCandidates: (token: string) =>
    request<{ question_id: string; review_id: string; overall_score: number; source_type: string; question_status: string; notes: string | null }[]>(`/v1/admin/content/quality-regeneration-candidates`, {}, token),

  // ── AI Generation ──────────────────────────────────────────────

  listOutcomes: (token: string, frameworkId?: string) => {
    const qs = frameworkId ? `?framework_id=${frameworkId}` : "";
    return request<{ id: string; framework_id: string; code: string; title: string }[]>(`/v1/curriculum/outcomes${qs}`, {}, token);
  },

  previewAIGenerate: (body: { outcome_id: string; subject_id: string; exam_type_id: string; count: number; difficulty_mix: Record<string, number>; provider: string }, token: string) =>
    request<{ questions: any[]; summary: { total: number; valid: number; invalid: number } }>(`/v1/admin/content/ai-generate/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }, token),

  executeAIGenerate: (body: { outcome_id: string; framework_id?: string; subject_id: string; exam_type_id: string; count: number; difficulty_mix: Record<string, number>; provider: string }, token: string) =>
    request<{ job_id: string; saved_count: number; rejected_count: number }>(`/v1/admin/content/ai-generate/execute`, {
      method: "POST",
      body: JSON.stringify(body),
    }, token),

  // ── Bulk Import ───────────────────────────────────────────────

  async previewImport(formData: FormData, token: string) {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    const res = await fetch(`${API_BASE}/v1/admin/content/import/preview`, { method: "POST", headers, body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw { status: res.status, detail: body.detail ?? "Preview failed" };
    }
    return res.json();
  },

  async executeImport(formData: FormData, token: string) {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    const res = await fetch(`${API_BASE}/v1/admin/content/import/execute`, { method: "POST", headers, body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw { status: res.status, detail: body.detail ?? "Import failed" };
    }
    return res.json();
  },

  async downloadTemplate(format: string, token: string): Promise<Blob> {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    const res = await fetch(`${API_BASE}/v1/admin/content/import/templates/${format}`, { method: "GET", headers });
    if (!res.ok) throw { status: res.status, detail: "Download failed" };
    return res.blob();
  },

  // ── System Dashboard ──────────────────────────────────────────

  getSystemDashboard: (token: string) =>
    request<SystemDashboard>(`/v1/admin/system`, {}, token),

  // ── Writing Mode ─────────────────────────────────────────────

  // Student
  listWritingTasks: (token: string) =>
    request<WritingTaskItem[]>(`/v1/writing/tasks`, {}, token),

  startWriting: (taskId: string, token: string) =>
    request<WritingSubmissionResponse>(`/v1/writing/tasks/${taskId}/start`, { method: "POST" }, token),

  saveWriting: (submissionId: string, content: string, wordCount: number, token: string) =>
    request<WritingSubmissionResponse>(`/v1/writing/submissions/${submissionId}/save`, {
      method: "PATCH",
      body: JSON.stringify({ content, word_count: wordCount }),
    }, token),

  submitWriting: (submissionId: string, token: string) =>
    request<WritingSubmissionResponse>(`/v1/writing/submissions/${submissionId}/submit`, { method: "POST" }, token),

  getWritingSubmission: (submissionId: string, token: string) =>
    request<WritingSubmissionResponse>(`/v1/writing/submissions/${submissionId}`, {}, token),

  listMyWritingSubmissions: (token: string) =>
    request<WritingSubmissionListItem[]>(`/v1/writing/submissions`, {}, token),

  // Parent
  listStudentWriting: (studentId: string, token: string) =>
    request<WritingSubmissionListItem[]>(`/v1/parents/students/${studentId}/writing`, {}, token),

  // Admin
  createWritingTask: (body: WritingTaskCreateBody, token: string) =>
    request<WritingTaskResponse>(`/v1/admin/writing/tasks`, {
      method: "POST",
      body: JSON.stringify(body),
    }, token),

  listAdminWritingTasks: (token: string, status?: string) =>
    request<WritingTaskResponse[]>(`/v1/admin/writing/tasks${status ? `?status=${status}` : ""}`, {}, token),

  publishWritingTask: (taskId: string, token: string) =>
    request<WritingTaskResponse>(`/v1/admin/writing/tasks/${taskId}/publish`, { method: "PATCH" }, token),

  archiveWritingTask: (taskId: string, token: string) =>
    request<WritingTaskResponse>(`/v1/admin/writing/tasks/${taskId}/archive`, { method: "PATCH" }, token),

  listAllWritingSubmissions: (token: string, taskId?: string) =>
    request<WritingSubmissionListItem[]>(`/v1/admin/writing/submissions${taskId ? `?task_id=${taskId}` : ""}`, {}, token),
};

export interface SystemDashboard {
  database_status: string;
  redis_status: string;
  storage_status: string;
  migration_version: string;
  uptime_seconds: number;
  memory_usage_mb: number;
  total_users: number;
  active_users_24h: number;
  active_parents_24h: number;
  active_students_24h: number;
  active_admins_24h: number;
  total_questions: number;
  published_questions: number;
  total_exams: number;
  total_assignments: number;
  jobs: {
    ocr_jobs: JobCounts;
    ai_jobs: JobCounts;
    import_jobs: JobCounts;
  };
  failed_jobs: FailedJob[];
  stuck_jobs: StuckJob[];
  table_counts: Record<string, number>;
}

export interface JobCounts {
  total: number;
  active: number;
  completed: number;
  failed: number;
}

export interface FailedJob {
  type: string;
  id: string;
  status: string;
  error: string | null;
  created_at: string;
  filename?: string;
  provider?: string;
}

export interface StuckJob {
  type: string;
  id: string;
  status: string;
  duration_minutes: number;
  started_at?: string;
  created_at?: string;
  filename?: string;
  provider?: string;
}

// ── Writing Mode ───────────────────────────────────────────────

export interface WritingTaskItem {
  id: string;
  title: string;
  prompt: string;
  instructions: string | null;
  word_limit: number | null;
  recommended_time_minutes: number | null;
  subject_id: string;
  exam_type_id: string;
  status: string;
  created_at: string | null;
  submission: { id: string; status: string; word_count: number; started_at: string | null; submitted_at: string | null } | null;
}

export interface WritingTaskResponse {
  id: string;
  title: string;
  prompt: string;
  instructions: string | null;
  word_limit: number | null;
  recommended_time_minutes: number | null;
  subject_id: string;
  exam_type_id: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface WritingTaskCreateBody {
  title: string;
  prompt: string;
  instructions?: string | null;
  word_limit?: number | null;
  recommended_time_minutes?: number | null;
  subject_id: string;
  exam_type_id: string;
}

export interface WritingSubmissionResponse {
  id: string;
  writing_task_id: string;
  student_id: string;
  content: string;
  word_count: number;
  status: string;
  started_at: string | null;
  submitted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface WritingSubmissionListItem {
  id: string;
  writing_task_id: string;
  task_title: string;
  student_id: string;
  student_name?: string | null;
  word_count: number;
  status: string;
  started_at: string | null;
  submitted_at: string | null;
  content?: string;
}
