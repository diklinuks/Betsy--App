import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useReplay } from "../store";
import { fmtMoney, fmtNum } from "../format";

export function DecisionDrawer() {
  const run = useReplay((s) => s.run);
  const id = useReplay((s) => s.selectedDecisionId);
  const select = useReplay((s) => s.selectDecision);
  const d = run?.decisions.find((x) => x.decision_id === id) ?? null;

  return (
    <AnimatePresence>
      {d && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => select(null)}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-hairline bg-panel shadow-panel"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
          >
            <div className="flex items-start justify-between border-b border-hairline px-5 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-white">{d.product_id ?? "—"}</h2>
                  <span className="chip bg-raised text-muted">{d.trigger_type}</span>
                  {d.urgent && <span className="chip bg-warn/15 text-warn">urgent</span>}
                </div>
                <p className="nums mt-0.5 text-xs text-faint">
                  Day {d.sim_day} · {d.attribution} · cfg v{d.config_version} · {d.decision_id}
                </p>
              </div>
              <button className="nav-item" onClick={() => select(null)} title="Close">
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
              <div className="grid grid-cols-3 gap-2">
                <Stat label="Chosen" value={d.chosen_supplier ?? "—"} />
                <Stat label="Quantity" value={d.chosen_quantity != null ? fmtNum(d.chosen_quantity) : "—"} />
                <Stat label="Confidence" value={d.confidence != null ? d.confidence.toFixed(2) : "—"} />
              </div>

              <Section title="Reasoning">
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink/90">
                  {d.reasoning || "—"}
                </p>
              </Section>

              {d.candidates.length > 0 && (
                <Section title="Candidates scored">
                  <div className="overflow-hidden rounded-lg border border-hairline">
                    <table className="w-full text-sm">
                      <thead className="bg-raised text-left text-xs text-faint">
                        <tr>
                          <th className="px-3 py-1.5 font-medium">Supplier</th>
                          <th className="px-3 py-1.5 font-medium">Score</th>
                          <th className="px-3 py-1.5 font-medium">$/unit</th>
                          <th className="px-3 py-1.5 font-medium">Lead</th>
                        </tr>
                      </thead>
                      <tbody className="nums">
                        {d.candidates.map((c) => {
                          const chosen = c.supplier_id === d.chosen_supplier;
                          return (
                            <tr
                              key={c.supplier_id}
                              className={`border-t border-hairline ${chosen ? "bg-accent/5 text-accent" : "text-ink/80"}`}
                            >
                              <td className="px-3 py-1.5 font-medium">
                                {c.supplier_id} {chosen && <span className="text-[10px]">●</span>}
                              </td>
                              <td className="px-3 py-1.5">{c.score?.toFixed?.(3) ?? c.score}</td>
                              <td className="px-3 py-1.5">{fmtMoney(c.unit_price, 2)}</td>
                              <td className="px-3 py-1.5">{c.lead}d</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Section>
              )}

              {d.alternatives.length > 0 && (
                <Section title="Alternatives considered">
                  <div className="flex flex-wrap gap-1.5">
                    {d.alternatives.map((a) => (
                      <span key={a} className="chip bg-raised text-muted">
                        {a}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {d.outcome && (
                <Section title="Outcome">
                  <pre className="overflow-x-auto rounded-lg border border-hairline bg-raised px-3 py-2 text-xs text-ink/80">
                    {JSON.stringify(d.outcome, null, 2)}
                  </pre>
                </Section>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel-raised px-3 py-2">
      <div className="kpi-label">{label}</div>
      <div className="nums mt-0.5 truncate text-sm font-semibold text-white">{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">{title}</h3>
      {children}
    </div>
  );
}
