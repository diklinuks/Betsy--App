import { Check } from "lucide-react";
import { useReplay } from "../store";
import { PanelHeader } from "../components/ui";

export function ScenariosPanel() {
  const { run, cursorDay } = useReplay();
  if (!run) return null;
  const firedNow = run.scenarios.filter((s) => s.fired && (s.trigger_sim_day ?? 999) <= cursorDay).length;

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Injected scenarios"
        subtitle={`The 10 stress tests scripted into the world · ${firedNow} fired through day ${cursorDay}`}
      />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {run.scenarios.map((sc) => {
          const triggered = sc.fired && (sc.trigger_sim_day ?? 999) <= cursorDay;
          const upcoming = (sc.trigger_sim_day ?? 0) > cursorDay;
          return (
            <div
              key={sc.id}
              className={`panel p-4 transition ${triggered ? "ring-1 ring-accent/25" : upcoming ? "opacity-60" : ""}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="nums chip bg-raised text-muted">{sc.id}</span>
                  <span className="text-xs text-faint">{sc.type.replace(/_/g, " ")}</span>
                </div>
                {triggered ? (
                  <span className="chip bg-accent/10 text-accent">
                    <Check size={12} /> fired
                  </span>
                ) : upcoming ? (
                  <span className="nums chip bg-raised text-faint">day {sc.trigger_sim_day}</span>
                ) : (
                  <span className="chip bg-raised text-faint">pending</span>
                )}
              </div>
              <p className="mt-2 text-sm leading-snug text-ink/90">{sc.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
