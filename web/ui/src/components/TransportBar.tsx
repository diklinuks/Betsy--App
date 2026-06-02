import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from "lucide-react";
import { useReplay } from "../store";

const SPEEDS = [1, 2, 4];
const SCEN_TONE: Record<string, string> = {
  bad: "#FB7185", warn: "#FBBF24", good: "#34D399", info: "#38BDF8", action: "#34D399",
};

export function TransportBar() {
  const { run, cursorDay, playing, speed, play, pause, step, setCursor, restart, setSpeed } =
    useReplay();
  if (!run) return null;
  const max = run.meta.sim_days;
  const snap = run.days[cursorDay - 1];
  const atEnd = cursorDay >= max;

  const summary =
    run.events.find((e) => e.kind === "day_summary" && e.sim_day === cursorDay)?.title?.replace(
      /^Day \d+ complete — /,
      "",
    ) ?? "—";

  const statusLabel = playing ? "REPLAYING" : atEnd ? "COMPLETE" : "PAUSED";
  const statusTone = playing ? "text-accent" : atEnd ? "text-info" : "text-muted";

  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-panel/85 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${playing ? "animate-pulseDot bg-accent" : atEnd ? "bg-info" : "bg-muted"}`}
            />
            <span className="text-sm font-semibold tracking-tight text-white">
              Betsy <span className="text-faint">· Control Room</span>
            </span>
          </div>
          <span className={`chip border border-hairline-strong bg-raised ${statusTone}`}>
            {statusLabel}
          </span>
          <p className="hidden min-w-0 truncate text-sm text-muted md:block" title={summary}>
            {summary}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="nums text-sm font-semibold text-white">
              Day {cursorDay} <span className="text-faint">/ {max}</span>
            </div>
            <div className="nums text-[11px] text-faint">{snap?.date}</div>
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <div className="flex items-center gap-1">
          <button className="btn px-2" title="Restart from day 1" onClick={restart}>
            <RotateCcw size={15} />
          </button>
          <button className="btn px-2" title="Step back" onClick={() => step(-1)} disabled={cursorDay <= 1}>
            <ChevronLeft size={16} />
          </button>
          <button
            className="btn btn-accent px-3"
            title={playing ? "Pause" : "Play"}
            onClick={() => (playing ? pause() : play())}
          >
            {playing ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button className="btn px-2" title="Step forward" onClick={() => step(1)} disabled={atEnd}>
            <ChevronRight size={16} />
          </button>
        </div>

        {/* scrubber + scenario markers */}
        <div className="relative flex-1">
          <div className="pointer-events-none absolute -top-1.5 left-0 right-0 h-2">
            {run.scenarios
              .filter((sc) => sc.trigger_sim_day)
              .map((sc) => {
                const ev = run.events.find((e) => e.detail && (e.detail as any).scenario === sc.id);
                const tone = SCEN_TONE[ev?.severity ?? "warn"] ?? "#FBBF24";
                return (
                  <span
                    key={sc.id}
                    title={`Day ${sc.trigger_sim_day} · ${sc.description}`}
                    className="absolute top-0 h-2 w-[2px] rounded"
                    style={{ left: `${((sc.trigger_sim_day! - 1) / (max - 1)) * 100}%`, background: tone, opacity: 0.8 }}
                  />
                );
              })}
          </div>
          <input
            type="range"
            className="scrubber w-full"
            min={1}
            max={max}
            value={cursorDay}
            onChange={(e) => setCursor(Number(e.target.value))}
          />
        </div>

        <div className="flex items-center gap-1 rounded-lg border border-hairline bg-raised p-0.5">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={`nums rounded-md px-2 py-1 text-xs font-medium transition ${
                speed === s ? "bg-accent/15 text-accent" : "text-muted hover:text-ink"
              }`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
