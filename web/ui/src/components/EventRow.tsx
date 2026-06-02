import { ArrowUpRight } from "lucide-react";
import type { RunEvent } from "../types";
import { kindLabel, sevDot, sevText } from "../format";
import { useReplay } from "../store";

export function EventRow({ e, dense = false }: { e: RunEvent; dense?: boolean }) {
  const select = useReplay((s) => s.selectDecision);
  const clickable = Boolean(e.decision_id);
  return (
    <div
      className={`group flex items-start gap-3 border-b border-hairline/60 px-3 ${dense ? "py-1.5" : "py-2.5"} ${
        clickable ? "cursor-pointer hover:bg-raised/60" : ""
      }`}
      onClick={() => clickable && select(e.decision_id)}
    >
      <div className="mt-1 flex flex-col items-center">
        <span className={`h-2 w-2 rounded-full ${sevDot[e.severity]}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="nums text-[11px] text-faint">D{e.sim_day}</span>
          <span className={`text-[11px] font-medium ${sevText[e.severity]}`}>
            {kindLabel[e.kind] ?? e.kind}
          </span>
          {clickable && (
            <ArrowUpRight
              size={12}
              className="ml-auto text-faint opacity-0 transition group-hover:opacity-100"
            />
          )}
        </div>
        <p className={`mt-0.5 ${dense ? "text-xs" : "text-sm"} leading-snug text-ink/90`}>{e.title}</p>
        {!dense && e.kind === "proposal" && typeof e.detail.reasoning === "string" && (
          <p className="mt-1 line-clamp-2 text-xs italic text-muted">“{e.detail.reasoning as string}”</p>
        )}
        {!dense && e.kind === "lesson" && typeof e.detail.lesson === "string" && (
          <p className="mt-1 text-xs text-muted">{e.detail.lesson as string}</p>
        )}
      </div>
    </div>
  );
}
