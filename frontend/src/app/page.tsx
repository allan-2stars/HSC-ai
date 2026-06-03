import Link from "next/link";
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

        <div className="flex items-center justify-center gap-4 pt-6">
          <Link
            href="/login"
            className="px-6 py-2 bg-cta text-white rounded-md hover:opacity-90 transition-opacity"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="px-6 py-2 bg-surface border border-border-subtle text-text-primary rounded-md hover:border-cta transition-colors"
          >
            Register
          </Link>
        </div>

        <p className="text-text-tertiary text-xs pt-8">
          HSC AI Platform — Development
        </p>
      </div>
    </main>
  );
}
