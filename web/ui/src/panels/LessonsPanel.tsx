import { useReplay } from "../store";
import { lessonsUpTo } from "../selectors";
import { Empty, PanelHeader } from "../components/ui";

export function LessonsPanel() {
  const { run, cursorDay } = useReplay();
  if (!run) return null;
  const rows = lessonsUpTo(run, cursorDay).slice().reverse();

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Lessons learned"
        subtitle={`Reflections after poor outcomes and operator rejections, as of day ${cursorDay} — recalled on similar future decisions`}
      />
      {rows.length === 0 ? (
        <Empty>No lessons yet — they appear after a late, defective, or short delivery.</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {rows.map((l, i) => {
            const rejection = l.kind === "rejection";
            return (
              <div
                key={i}
                className={`panel border-l-2 p-4 ${rejection ? "border-l-bad" : "border-l-accent"}`}
              >
                <div className="flex items-center justify-between">
                  <span className={`chip ${rejection ? "bg-bad/15 text-bad" : "bg-accent/10 text-accent"}`}>
                    {l.kind}
                  </span>
                  <span className="nums text-[11px] text-faint">
                    day {l.sim_day} · {l.product_id ?? ""} {l.supplier_id ?? ""}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-ink/90">{l.text}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
