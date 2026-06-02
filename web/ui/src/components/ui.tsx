import type { ReactNode } from "react";

export function PanelHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="panel grid place-items-center px-6 py-12 text-center text-sm text-faint">
      {children}
    </div>
  );
}

/** Inline SVG sparkline. */
export function Sparkline({
  data,
  width = 88,
  height = 26,
  stroke = "#34D399",
  fill = "rgba(52,211,153,0.12)",
}: {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
}) {
  if (!data.length) return <svg width={width} height={height} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pad = 2;
  const stepX = data.length > 1 ? (width - pad * 2) / (data.length - 1) : 0;
  const pts = data.map((v, i) => {
    const x = pad + i * stepX;
    const y = height - pad - ((v - min) / span) * (height - pad * 2);
    return [x, y] as const;
  });
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad},${height - pad} ${line} ${(pad + (data.length - 1) * stepX).toFixed(1)},${height - pad}`;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polygon points={area} fill={fill} />
      <polyline points={line} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      {pts.length > 0 && (
        <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={2} fill={stroke} />
      )}
    </svg>
  );
}

/** A labelled horizontal meter (value / max) with a tone. */
export function Meter({
  value,
  max,
  tone = "#34D399",
  height = 6,
}: {
  value: number;
  max: number;
  tone?: string;
  height?: number;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-full overflow-hidden rounded-full bg-hairline" style={{ height }}>
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, background: tone, boxShadow: `0 0 12px -2px ${tone}` }}
      />
    </div>
  );
}

export function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "bg-good/10 text-good",
    inactive: "bg-bad/10 text-bad",
  };
  return (
    <span className={`chip ${map[status] ?? "bg-raised text-muted"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${status === "active" ? "bg-good" : status === "inactive" ? "bg-bad" : "bg-muted"}`} />
      {status}
    </span>
  );
}

export function AbcBadge({ cls }: { cls: string }) {
  const tone: Record<string, string> = {
    A: "bg-accent/15 text-accent",
    B: "bg-info/15 text-info",
    C: "bg-raised text-muted",
  };
  return <span className={`chip ${tone[cls] ?? "bg-raised text-muted"}`}>{cls}</span>;
}
