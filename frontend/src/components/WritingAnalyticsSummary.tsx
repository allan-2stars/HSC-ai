"use client";

import type { WritingAnalytics } from "@/lib/api";

function Card({ label, value, color = "text-text-primary" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}

function BarChart({ items, maxValue = 5, valueKey = "average_rating", colorClass = "bg-interactive" }: {
  items: Record<string, any>[];
  maxValue?: number;
  valueKey?: string;
  colorClass?: string;
}) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const val = parseFloat(item[valueKey] as string) || 0;
        const pct = Math.min((val / maxValue) * 100, 100);
        return (
          <div key={i}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-text-secondary">{item.dimension_name ?? item.task_title ?? ""}</span>
              <span className="text-text-tertiary">{val.toFixed(1)}{valueKey === "average_rating" ? " / 5" : ""}</span>
            </div>
            <div className="h-3 bg-surface-secondary rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${colorClass}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-8 text-center">
      <p className="text-text-tertiary text-sm">{message}</p>
    </div>
  );
}

export { Card, BarChart, EmptyState };

export function WritingAnalyticsSummary({ data }: { data: WritingAnalytics }) {
  const s = data.summary;

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <Card label="Reviews" value={s.published_reviews} />
        <Card label="Avg Rating" value={s.average_rating?.toFixed(1) ?? "—"} />
        <Card label="Avg Words" value={s.average_word_count?.toFixed(0) ?? "—"} />
        <Card label="Disputes" value={s.disputes_count} color={s.disputes_count > 0 ? "text-amber-400" : "text-text-primary"} />
        <Card label="Reopened" value={s.reopened_count} />
      </div>

      {s.published_reviews === 0 && (
        <EmptyState message="No published reviews yet. Complete a writing task to see your analytics here." />
      )}

      {data.dimension_averages.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Dimension Breakdown</h2>
          <BarChart items={data.dimension_averages} maxValue={5} valueKey="average_rating" colorClass="bg-interactive" />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {data.strengths.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-success mb-3">Strengths</h2>
            <BarChart items={data.strengths} maxValue={5} valueKey="average_rating" colorClass="bg-success" />
          </div>
        )}
        {data.weaknesses.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-error mb-3">Areas to Improve</h2>
            <BarChart items={data.weaknesses} maxValue={5} valueKey="average_rating" colorClass="bg-amber-400" />
          </div>
        )}
      </div>

      {data.progress_over_time.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Progress Over Time</h2>
          <div className="space-y-2">
            {data.progress_over_time.map((p, i) => (
              <div key={i} className="bg-surface border border-border-subtle rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="text-text-primary text-sm font-medium">{p.task_title}</p>
                  {p.published_at && <p className="text-text-tertiary text-xs">{new Date(p.published_at).toLocaleDateString()}</p>}
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-text-secondary">{p.word_count} words</span>
                  <span className="text-interactive font-medium">{p.average_rating?.toFixed(1) ?? "—"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.latest_feedback && (
        <div className="mb-8 bg-surface border border-border-subtle rounded-lg p-4">
          <h2 className="text-lg font-semibold text-text-primary mb-2">Latest Feedback</h2>
          <p className="text-text-tertiary text-xs mb-2">
            {data.latest_feedback.task_title}
            {data.latest_feedback.published_at && ` — ${new Date(data.latest_feedback.published_at).toLocaleDateString()}`}
          </p>
          <p className="text-text-primary text-sm whitespace-pre-wrap">{data.latest_feedback.overall_comment}</p>
        </div>
      )}
    </>
  );
}
