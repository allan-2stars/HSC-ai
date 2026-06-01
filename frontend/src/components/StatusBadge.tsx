"use client";

export type StatusValue = "ok" | "degraded" | "error";

interface StatusBadgeProps {
  status: StatusValue;
}

const statusStyles: Record<StatusValue, string> = {
  ok: "bg-green-900 text-green-300 border-green-700",
  degraded: "bg-yellow-900 text-yellow-300 border-yellow-700",
  error: "bg-red-900 text-red-300 border-red-700",
};

const statusLabels: Record<StatusValue, string> = {
  ok: "Operational",
  degraded: "Degraded",
  error: "Error",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      data-testid="status-badge"
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border ${statusStyles[status]}`}
    >
      <span
        data-testid="status-dot"
        className={`w-1.5 h-1.5 rounded-full ${
          status === "ok"
            ? "bg-green-400"
            : status === "degraded"
              ? "bg-yellow-400"
              : "bg-red-400"
        }`}
      />
      {statusLabels[status]}
    </span>
  );
}
