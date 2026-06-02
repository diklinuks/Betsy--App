import { useReplay } from "../store";
import { invoicesUpTo } from "../selectors";
import { fmtMoney } from "../format";
import { PanelHeader } from "../components/ui";

export function InvoicesPanel() {
  const { run, cursorDay } = useReplay();
  if (!run) return null;
  const rows = invoicesUpTo(run, cursorDay).slice().reverse();
  const held = rows.filter((v) => v.payment_status === "held").length;

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Invoices"
        subtitle={`Three-way matched vs PO & delivery, as of day ${cursorDay} — ${held} held for review`}
      />
      <div className="panel overflow-hidden">
        <div className="max-h-[calc(100vh-240px)] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-raised text-left text-xs text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">Day</th>
                <th className="px-3 py-2 font-medium">Invoice</th>
                <th className="px-3 py-2 font-medium">Supplier</th>
                <th className="px-3 py-2 font-medium">PO</th>
                <th className="px-3 py-2 font-medium">Amount</th>
                <th className="px-3 py-2 font-medium">PO amount</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Flag</th>
              </tr>
            </thead>
            <tbody className="nums">
              {rows.map((v) => {
                const heldRow = v.payment_status === "held";
                return (
                  <tr key={v.invoice_id} className={`border-t border-hairline/70 ${heldRow ? "bg-bad/[0.05]" : ""}`}>
                    <td className="px-3 py-2 text-muted">{v.sim_day}</td>
                    <td className="px-3 py-2 text-ink/70">
                      {v.invoice_number}
                      {v.is_duplicate && <span className="ml-1 text-bad">(dup)</span>}
                    </td>
                    <td className="px-3 py-2 text-ink/80">{v.supplier_id}</td>
                    <td className="px-3 py-2 text-ink/70">{v.po_id}</td>
                    <td className={`px-3 py-2 ${!v.matches_po ? "font-semibold text-bad" : "text-ink/80"}`}>
                      {fmtMoney(v.amount, 2)}
                    </td>
                    <td className="px-3 py-2 text-faint">{fmtMoney(v.po_amount, 2)}</td>
                    <td className="px-3 py-2">
                      <span className={`chip ${heldRow ? "bg-bad/15 text-bad" : "bg-good/10 text-good"}`}>
                        {v.payment_status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-bad">{v.anomaly_flag}</td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-sm text-faint">
                    No invoices yet.
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
