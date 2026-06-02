import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useReplay } from "../store";
import { eventsUpTo } from "../selectors";
import { kindLabel } from "../format";
import { EventRow } from "../components/EventRow";
import { PanelHeader } from "../components/ui";

const SEV_FILTERS: { id: string; label: string; tone: string }[] = [
  { id: "all", label: "All", tone: "text-ink" },
  { id: "action", label: "Actions", tone: "text-accent" },
  { id: "good", label: "Good", tone: "text-good" },
  { id: "warn", label: "Warnings", tone: "text-warn" },
  { id: "bad", label: "Problems", tone: "text-bad" },
];

export function ActivityPanel() {
  const { run, cursorDay } = useReplay();
  const [sev, setSev] = useState("all");
  const [q, setQ] = useState("");
  const [hideRoutine, setHideRoutine] = useState(true);

  const events = useMemo(() => {
    if (!run) return [];
    let evs = eventsUpTo(run, cursorDay);
    if (hideRoutine) evs = evs.filter((e) => e.kind !== "consumption" && e.kind !== "day_summary");
    if (sev !== "all") evs = evs.filter((e) => e.severity === sev);
    if (q.trim()) {
      const t = q.toLowerCase();
      evs = evs.filter(
        (e) =>
          e.title.toLowerCase().includes(t) ||
          (kindLabel[e.kind] ?? e.kind).toLowerCase().includes(t) ||
          (e.supplier_id ?? "").toLowerCase().includes(t) ||
          (e.product_id ?? "").toLowerCase().includes(t),
      );
    }
    return evs.reverse();
  }, [run, cursorDay, sev, q, hideRoutine]);

  if (!run) return null;

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Activity timeline"
        subtitle={`Every step Betsy takes — ${events.length} events through day ${cursorDay}`}
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-lg border border-hairline bg-raised p-0.5">
          {SEV_FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setSev(f.id)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                sev === f.id ? `bg-panel ${f.tone}` : "text-muted hover:text-ink"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
          <input
            type="checkbox"
            checked={hideRoutine}
            onChange={(e) => setHideRoutine(e.target.checked)}
            className="accent-accent"
          />
          hide routine
        </label>
        <div className="relative ml-auto">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="filter…"
            className="w-44 rounded-lg border border-hairline bg-raised py-1.5 pl-8 pr-3 text-sm text-ink placeholder:text-faint focus:border-accent/50 focus:outline-none"
          />
        </div>
      </div>

      <div className="panel max-h-[calc(100vh-260px)] overflow-y-auto">
        {events.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-faint">No matching events yet.</p>
        ) : (
          events.map((e) => <EventRow key={e.id} e={e} />)
        )}
      </div>
    </div>
  );
}
