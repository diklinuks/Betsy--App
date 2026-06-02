import { useReplay } from "../store";
import { decisionsUpTo } from "../selectors";
import { PanelHeader } from "../components/ui";

const actionTone: Record<string, string> = {
  po_generated: "bg-good/10 text-good",
  rejected: "bg-bad/15 text-bad",
  escalated: "bg-warn/15 text-warn",
  awaiting_approval: "bg-warn/15 text-warn",
  invoice_held: "bg-bad/15 text-bad",
};

export function DecisionsPanel() {
  const { run, cursorDay, selectDecision } = useReplay();
  if (!run) return null;
  const rows = decisionsUpTo(run, cursorDay).slice().reverse();

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Decision audit log"
        subtitle={`Append-only · ${rows.length} decisions through day ${cursorDay} · click a row for full reasoning`}
      />
      <div className="panel overflow-hidden">
        <div className="max-h-[calc(100vh-240px)] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-raised text-left text-xs text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">Day</th>
                <th className="px-3 py-2 font-medium">Trigger</th>
                <th className="px-3 py-2 font-medium">Product</th>
                <th className="px-3 py-2 font-medium">Chosen</th>
                <th className="px-3 py-2 font-medium">Action</th>
                <th className="px-3 py-2 font-medium">By</th>
                <th className="hidden px-3 py-2 font-medium lg:table-cell">Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr
                  key={d.decision_id}
                  onClick={() => selectDecision(d.decision_id)}
                  className="cursor-pointer border-t border-hairline/70 align-top hover:bg-raised/60"
                >
                  <td className="nums px-3 py-2 text-muted">{d.sim_day}</td>
                  <td className="px-3 py-2 text-ink/80">{d.trigger_type}</td>
                  <td className="nums px-3 py-2 text-ink/80">{d.product_id ?? "—"}</td>
                  <td className="nums px-3 py-2 whitespace-nowrap text-white">
                    {d.chosen_supplier ?? "—"}
                    {d.chosen_quantity ? <span className="text-faint"> ×{d.chosen_quantity}</span> : null}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`chip ${actionTone[d.action] ?? "bg-raised text-muted"}`}>{d.action}</span>
                    {d.urgent && <span className="chip ml-1 bg-warn/15 text-warn">urgent</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-faint">{d.attribution}</td>
                  <td className="hidden max-w-md px-3 py-2 text-xs text-muted lg:table-cell">
                    <span className="line-clamp-2">{d.reasoning}</span>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-faint">
                    No decisions yet — press play.
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
