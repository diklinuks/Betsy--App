import { Check, X } from "lucide-react";
import { useReplay } from "../store";
import { fmtPct } from "../format";
import { PanelHeader } from "../components/ui";

const CRIT_LABEL: Record<string, string> = {
  prevent_2_stockouts: "Prevent ≥2 stockouts",
  catch_1_invoice_error: "Catch ≥1 invoice error",
  approval_rate_95pct: "Maintain ≥95% approval rate",
};

export function ReportPanel() {
  const run = useReplay((s) => s.run);
  if (!run) return null;
  const rep = run.report;
  const isRate = (k: string) => k === "approval_rate_95pct";

  return (
    <div className="space-y-5">
      <PanelHeader
        title="Success-criteria report"
        subtitle="Final scorecard for the 90-day run, measured against the project targets"
        right={
          <span className={`chip ${rep.all_criteria_pass ? "bg-good/10 text-good" : "bg-bad/15 text-bad"}`}>
            {rep.all_criteria_pass ? "all criteria met" : "criteria unmet"}
          </span>
        }
      />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {Object.entries(rep.success_criteria).map(([key, c]) => (
          <div key={key} className={`panel p-5 ${c.pass ? "ring-1 ring-good/20" : "ring-1 ring-bad/20"}`}>
            <p className="text-sm text-muted">{CRIT_LABEL[key] ?? key}</p>
            <p className="nums mt-1 text-3xl font-semibold text-white">
              {isRate(key) ? fmtPct(c.actual) : c.actual}
              <span className="ml-1 text-sm text-faint">
                / target {isRate(key) ? fmtPct(c.target) : c.target}
              </span>
            </p>
            <p className={`mt-2 flex items-center gap-1 text-sm font-medium ${c.pass ? "text-good" : "text-bad"}`}>
              {c.pass ? <Check size={15} /> : <X size={15} />} {c.pass ? "pass" : "not met"}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <h3 className="mb-3 text-sm font-semibold text-white">Operations summary</h3>
          <ul className="nums space-y-2 text-sm text-ink/85">
            <li className="flex justify-between border-b border-hairline/60 pb-2">
              <span className="text-muted">Decisions made</span>
              <span>
                <b className="text-white">{rep.decisions.total}</b> ({rep.decisions.pos_generated} POs ·{" "}
                {rep.decisions.escalated} escalated)
              </span>
            </li>
            <li className="flex justify-between border-b border-hairline/60 pb-2">
              <span className="text-muted">Approvals</span>
              <span>
                <b className="text-white">{rep.approvals.approved}</b> approved / {rep.approvals.rejected} rejected (
                {fmtPct(rep.approvals.rate)})
              </span>
            </li>
            <li className="flex justify-between border-b border-hairline/60 pb-2">
              <span className="text-muted">Invoice errors caught</span>
              <b className="text-white">{rep.invoice_errors_caught}</b>
            </li>
            <li className="flex justify-between">
              <span className="text-muted">Stockouts</span>
              <span>
                {rep.stockouts.occurred} occurred · <b className="text-good">{rep.stockouts.prevented}</b> prevented
              </span>
            </li>
          </ul>
        </div>

        <div className="panel p-5">
          <h3 className="mb-1 text-sm font-semibold text-white">Scenario coverage</h3>
          <p className="mb-3 text-xs text-faint">
            {rep.scenario_coverage.fired.length} / {Object.keys(rep.scenario_coverage.detail).length} injected scenarios fired
          </p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(rep.scenario_coverage.detail).map(([sid, ok]) => (
              <span key={sid} className={`nums chip ${ok ? "bg-good/10 text-good" : "bg-raised text-faint"}`}>
                {sid}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="panel p-5">
        <h3 className="mb-3 text-sm font-semibold text-white">Final supplier scores</h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3 lg:grid-cols-4">
          {Object.entries(rep.final_supplier_scores).map(([sid, sc]) => (
            <div key={sid} className="nums flex justify-between border-b border-hairline/50 py-1 text-sm">
              <span className="text-muted">{sid}</span>
              <b className="text-ink/90">{sc}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
