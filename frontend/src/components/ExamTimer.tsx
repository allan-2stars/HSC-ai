"use client";

import { useEffect, useState } from "react";

export default function ExamTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState("");

  useEffect(() => {
    const end = new Date(expiresAt).getTime();

    function tick() {
      const now = Date.now();
      const diff = Math.max(0, end - now);
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setRemaining(`${mins}:${secs.toString().padStart(2, "0")}`);
    }

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  const isLow = remaining && parseInt(remaining.split(":")[0]) < 5;

  return (
    <div className={`text-lg font-mono tabular-nums ${isLow ? "text-red-400" : "text-white"}`}>
      {remaining || "--:--"}
    </div>
  );
}
