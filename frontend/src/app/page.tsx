import { StatusBadge } from "@/components/StatusBadge";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="max-w-lg w-full text-center space-y-6">
        <h1 className="text-4xl font-light tracking-tight text-white">
          HSC AI Platform
        </h1>
        <p className="text-text-secondary text-base">
          NSW exam preparation for OC and Selective School
        </p>
        <div className="flex items-center justify-center gap-3 pt-4">
          <span className="text-text-tertiary text-sm">Platform status</span>
          <StatusBadge status="ok" />
        </div>
        <p className="text-text-tertiary text-xs pt-8">
          Milestone 0 — Project Bootstrap
        </p>
      </div>
    </main>
  );
}
