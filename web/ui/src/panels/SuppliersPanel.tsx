import { useReplay } from "../store";
import { supplierRowsAt } from "../selectors";
import { PanelHeader, Sparkline, StatusChip } from "../components/ui";

export function SuppliersPanel() {
  const { run, cursorDay } = useReplay();
  if (!run) return null;
  const rows = supplierRowsAt(run, cursorDay);

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Supplier scoreboard"
        subtitle={`Reliability scores Betsy ranks on, as of day ${cursorDay} — recomputed after every delivery`}
      />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map(({ supplier, score, status, spark }) => {
          const tone = status === "active" ? "#34D399" : "#FB7185";
          const delta = spark.length > 1 ? score - spark[0] : 0;
          return (
            <div key={supplier.supplier_id} className="panel p-4">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="nums text-sm font-semibold text-white">{supplier.supplier_id}</span>
                    <span className="truncate text-sm text-muted">{supplier.name}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-faint">
                    <span className="chip bg-raised text-muted">{supplier.price_tier}</span>
                    <span className="nums">{supplier.base_lead_time_days}d lead</span>
                  </div>
                </div>
                <StatusChip status={status} />
              </div>

              <div className="mt-3 flex items-end justify-between">
                <div className="nums text-2xl font-semibold text-white">{score.toFixed(3)}</div>
                <Sparkline data={spark} stroke={tone} fill={`${tone}22`} />
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-hairline">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(3, score * 100)}%`, background: tone, boxShadow: `0 0 10px -2px ${tone}` }}
                />
              </div>
              {delta !== 0 && (
                <div className={`nums mt-1 text-[11px] ${delta > 0 ? "text-good" : "text-bad"}`}>
                  {delta > 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(3)} since start
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
