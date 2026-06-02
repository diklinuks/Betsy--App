import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ReactNode } from "react";
import { useReplay } from "../store";
import { kpisAt, spendSeries, supplierRowsAt, eventsUpTo } from "../selectors";
import { fmtMoney, fmtNum, fmtPct } from "../format";
import { Meter, PanelHeader } from "../components/ui";
import { EventRow } from "../components/EventRow";

export function DeckPanel() {
  const { run, cursorDay, setView } = useReplay();
  if (!run) return null;
  const k = kpisAt(run, cursorDay);
  const series = spendSeries(run, cursorDay);
  const leaders = supplierRowsAt(run, cursorDay).slice(0, 6);
  const recent = eventsUpTo(run, cursorDay)
    .filter((e) => e.kind !== "consumption" && e.kind !== "day_summary")
    .slice(-9)
    .reverse();
  const capPct = k.monthlyCap ? k.spendMtd / k.monthlyCap : 0;

  return (
    <div className="space-y-5">
      <PanelHeader
        title="Command Deck"
        subtitle={`Betsy's autonomous procurement run · everything shown as of day ${cursorDay}`}
      />

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Spend · month to date" value={fmtMoney(k.spendMtd)} accent>
          <div className="mt-2">
            <Meter value={k.spendMtd} max={k.monthlyCap} tone={capPct > 0.9 ? "#FB7185" : "#34D399"} />
            <div className="nums mt-1 flex justify-between text-[11px] text-faint">
              <span>{fmtPct(capPct)} of cap</span>
              <span>{fmtMoney(k.monthlyCap)}</span>
            </div>
          </div>
        </Tile>
        <Tile label="Total procurement" value={fmtMoney(k.spendTotal)} sub={`${k.posPlaced} POs placed`} />
        <Tile
          label="On-time delivery"
          value={k.onTimeRate == null ? "—" : fmtPct(k.onTimeRate)}
          sub={`${k.deliveries} deliveries`}
          tone={k.onTimeRate != null && k.onTimeRate < 0.9 ? "warn" : "good"}
        />
        <Tile
          label="Invoice errors caught"
          value={fmtNum(k.invoiceErrors)}
          sub="held for review"
          tone={k.invoiceErrors > 0 ? "bad" : "muted"}
        />
        <Tile label="Lessons learned" value={fmtNum(k.lessons)} sub="reflections + rejections" tone="info" />
        <Tile label="Escalations to Jenny" value={fmtNum(k.escalations)} sub={`${fmtPct(k.approvalRate ?? 1)} approved`} tone="warn" />
        <Tile label="Active suppliers" value={fmtNum(k.activeSuppliers)} sub={`of ${run.suppliers.length}`} />
        <Tile label="Stockouts" value={fmtNum(k.stockouts)} sub="recovered + relearned" tone={k.stockouts > 0 ? "bad" : "good"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* spend chart */}
        <div className="panel p-4 xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Cumulative procurement spend</h3>
            <span className="nums text-xs text-faint">to day {cursorDay}</span>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
                <defs>
                  <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34D399" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#34D399" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fill: "#5A6677", fontSize: 11 }} stroke="#1E2733" tickLine={false} />
                <YAxis
                  tick={{ fill: "#5A6677", fontSize: 11 }}
                  stroke="#1E2733"
                  tickLine={false}
                  width={48}
                  tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
                />
                <Tooltip
                  contentStyle={{ background: "#161E2B", border: "1px solid #2A3543", borderRadius: 10, fontSize: 12 }}
                  labelStyle={{ color: "#8B98A9" }}
                  formatter={(v: number) => [fmtMoney(v), "Spend"]}
                  labelFormatter={(l) => `Day ${l}`}
                />
                <Area type="monotone" dataKey="spend" stroke="#34D399" strokeWidth={2} fill="url(#spendFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* supplier leaderboard */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Supplier reliability</h3>
            <button className="text-xs text-accent hover:underline" onClick={() => setView("suppliers")}>
              all →
            </button>
          </div>
          <div className="space-y-2.5">
            {leaders.map((r) => (
              <div key={r.supplier.supplier_id} className="flex items-center gap-3">
                <span className="nums w-9 shrink-0 text-xs text-muted">{r.supplier.supplier_id}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-hairline">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.max(3, r.score * 100)}%`,
                      background: r.status === "active" ? "#34D399" : "#FB7185",
                    }}
                  />
                </div>
                <span className="nums w-10 shrink-0 text-right text-xs text-ink/80">{r.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* recent activity */}
      <div className="panel">
        <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
          <h3 className="text-sm font-semibold text-white">Latest activity</h3>
          <button className="text-xs text-accent hover:underline" onClick={() => setView("activity")}>
            full feed →
          </button>
        </div>
        <div>
          {recent.length === 0 && <p className="px-4 py-6 text-sm text-faint">Nothing yet — press play.</p>}
          {recent.map((e) => (
            <EventRow key={e.id} e={e} />
          ))}
        </div>
      </div>
    </div>
  );
}

function Tile({
  label,
  value,
  sub,
  children,
  tone = "default",
  accent = false,
}: {
  label: string;
  value: string;
  sub?: string;
  children?: ReactNode;
  tone?: "default" | "good" | "warn" | "bad" | "info" | "muted";
  accent?: boolean;
}) {
  const toneClass: Record<string, string> = {
    default: "text-white",
    good: "text-good",
    warn: "text-warn",
    bad: "text-bad",
    info: "text-info",
    muted: "text-muted",
  };
  return (
    <div className={`panel p-4 ${accent ? "ring-1 ring-accent/20" : ""}`}>
      <div className="kpi-label">{label}</div>
      <div className={`nums mt-1 text-2xl font-semibold ${toneClass[tone]}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-faint">{sub}</div>}
      {children}
    </div>
  );
}
