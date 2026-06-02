import { useReplay } from "../store";
import { snapshotAt } from "../selectors";
import { AbcBadge, PanelHeader } from "../components/ui";

export function InventoryPanel() {
  const { run, cursorDay } = useReplay();
  if (!run) return null;
  const snap = snapshotAt(run, cursorDay);
  if (!snap) return null;
  const byId = Object.fromEntries(run.products.map((p) => [p.product_id, p]));
  const rows = [...snap.inventory].sort((a, b) => {
    const oa = a.stock === 0 ? 0 : a.below_reorder ? 1 : 2;
    const ob = b.stock === 0 ? 0 : b.below_reorder ? 1 : 2;
    return oa - ob || (a.days_cover ?? 999) - (b.days_cover ?? 999);
  });

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Inventory"
        subtitle={`Stock vs reorder point and safety stock, as of day ${cursorDay}`}
      />
      <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-2">
        {rows.map((r) => {
          const p = byId[r.product_id];
          const scale = Math.max(r.stock, r.reorder_point, r.safety_stock) * 1.25 || 1;
          const tone = r.stock === 0 ? "#FB7185" : r.below_reorder ? "#FBBF24" : "#34D399";
          const label = r.stock === 0 ? "stockout" : r.below_reorder ? "reorder" : "ok";
          const labelTone =
            r.stock === 0 ? "bg-bad/15 text-bad" : r.below_reorder ? "bg-warn/15 text-warn" : "bg-good/10 text-good";
          return (
            <div key={r.product_id} className="panel p-3.5">
              <div className="flex items-center justify-between">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="nums text-sm font-semibold text-white">{r.product_id}</span>
                  <span className="truncate text-sm text-muted">{p?.name}</span>
                  {p && <AbcBadge cls={p.abc_class} />}
                </div>
                <span className={`chip ${labelTone}`}>{label}</span>
              </div>

              <div className="relative mt-3 h-3 overflow-hidden rounded-full bg-hairline">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, (r.stock / scale) * 100)}%`, background: tone }}
                />
                {/* reorder point marker */}
                <span
                  className="absolute top-0 h-3 w-[2px] bg-warn/80"
                  style={{ left: `${Math.min(100, (r.reorder_point / scale) * 100)}%` }}
                  title={`reorder point ${r.reorder_point}`}
                />
                {/* safety stock marker */}
                <span
                  className="absolute top-0 h-3 w-[2px] bg-bad/70"
                  style={{ left: `${Math.min(100, (r.safety_stock / scale) * 100)}%` }}
                  title={`safety stock ${r.safety_stock}`}
                />
              </div>

              <div className="nums mt-2 flex items-center justify-between text-[11px] text-faint">
                <span className="text-ink/80">
                  stock <b className="text-white">{r.stock}</b>
                </span>
                <span>ROP {r.reorder_point}</span>
                <span>safety {r.safety_stock}</span>
                <span>{r.days_cover != null ? `${r.days_cover}d cover` : "—"}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
