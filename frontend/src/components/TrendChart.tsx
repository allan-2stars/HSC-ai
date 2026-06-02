"use client";

interface Point {
  label: string;
  value: number;
}

export default function TrendChart({ data }: { data: Point[] }) {
  if (data.length === 0) return <p className="text-text-tertiary text-sm">No trend data yet.</p>;

  const width = 400;
  const height = 80;
  const padding = 8;
  const maxVal = Math.max(...data.map((d) => d.value), 1);
  const minVal = Math.min(...data.map((d) => d.value), 0);

  const scaleY = (v: number) =>
    padding + ((maxVal - v) / Math.max(maxVal - minVal, 1)) * (height - 2 * padding);

  const points = data
    .map((d, i) => {
      const x = padding + (i / Math.max(data.length - 1, 1)) * (width - 2 * padding);
      return `${x},${scaleY(d.value)}`;
    })
    .join(" ");

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-20">
        {/* Grid line at 50% */}
        <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2}
          stroke="#353535" strokeWidth="0.5" strokeDasharray="2 4" />
        <polyline points={points} fill="none" stroke="#f36458" strokeWidth="1.5" />
        {/* Dots */}
        {data.map((d, i) => {
          const x = padding + (i / Math.max(data.length - 1, 1)) * (width - 2 * padding);
          return (
            <circle key={i} cx={x} cy={scaleY(d.value)} r="2.5" fill="#f36458" />
          );
        })}
      </svg>
    </div>
  );
}
