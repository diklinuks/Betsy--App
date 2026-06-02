import { useReplay } from "../store";
import { deliveriesUpTo } from "../selectors";
import { PanelHeader } from "../components/ui";

export function DeliveriesPanel() {
  const { run, cursorDay } = useReplay();
  if (!run) return null;
  const rows = deliveriesUpTo(run, cursorDay).slice().reverse();

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Deliveries"
        subtitle={`What actually arrived, as of day ${cursorDay} — problem deliveries are highlighted`}
      />
      <div className="panel overflow-hidden">
        <div className="max-h-[calc(100vh-240px)] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-raised text-left text-xs text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">Day</th>
                <th className="px-3 py-2 font-medium">PO</th>
                <th className="px-3 py-2 font-medium">Supplier</th>
                <th className="px-3 py-2 font-medium">Product</th>
                <th className="px-3 py-2 font-medium">Qty</th>
                <th className="px-3 py-2 font-medium">On time</th>
                <th className="px-3 py-2 font-medium">Quality</th>
                <th className="px-3 py-2 font-medium">Defects</th>
              </tr>
            </thead>
            <tbody className="nums">
              {rows.map((d) => {
                const bad = !d.on_time || !d.quality_pass || d.defects_count > 0 || d.quantity_received < d.quantity_ordered;
                return (
                  <tr key={d.delivery_id} className={`border-t border-hairline/70 ${bad ? "bg-bad/[0.04]" : ""}`}>
                    <td className="px-3 py-2 text-muted">{d.sim_day}</td>
                    <td className="px-3 py-2 text-ink/70">{d.po_id}</td>
                    <td className="px-3 py-2 text-ink/80">{d.supplier_id}</td>
                    <td className="px-3 py-2 text-ink/80">{d.product_id}</td>
                    <td className="px-3 py-2 text-ink/80">
                      {d.quantity_received}
                      <span className="text-faint">/{d.quantity_ordered}</span>
                    </td>
                    <td className={`px-3 py-2 ${d.on_time ? "text-good" : "text-bad"}`}>
                      {d.on_time ? "on time" : "late"}
                    </td>
                    <td className={`px-3 py-2 ${d.quality_pass ? "text-good" : "text-bad"}`}>
                      {d.quality_pass ? "pass" : "REJECTED"}
                    </td>
                    <td className={`px-3 py-2 ${d.defects_count > 0 ? "text-warn" : "text-faint"}`}>
                      {d.defects_count}
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-sm text-faint">
                    No deliveries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
