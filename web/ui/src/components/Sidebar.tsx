import {
  Activity, BarChart3, Boxes, Building2, ClipboardCheck, FlaskConical,
  LayoutDashboard, Lightbulb, ReceiptText, Truck,
} from "lucide-react";
import { useReplay } from "../store";
import type { ViewId } from "../types";

const NAV: { id: ViewId; label: string; Icon: typeof Activity }[] = [
  { id: "deck", label: "Command Deck", Icon: LayoutDashboard },
  { id: "activity", label: "Activity", Icon: Activity },
  { id: "suppliers", label: "Suppliers", Icon: Building2 },
  { id: "inventory", label: "Inventory", Icon: Boxes },
  { id: "decisions", label: "Decisions", Icon: ClipboardCheck },
  { id: "deliveries", label: "Deliveries", Icon: Truck },
  { id: "invoices", label: "Invoices", Icon: ReceiptText },
  { id: "lessons", label: "Lessons", Icon: Lightbulb },
  { id: "scenarios", label: "Scenarios", Icon: FlaskConical },
  { id: "report", label: "Report", Icon: BarChart3 },
];

export function Sidebar() {
  const view = useReplay((s) => s.view);
  const setView = useReplay((s) => s.setView);

  return (
    <aside className="flex w-16 shrink-0 flex-col items-center gap-1 border-r border-hairline bg-panel/60 py-3">
      <div className="mb-2 grid h-10 w-10 place-items-center rounded-xl bg-accent/15 text-accent shadow-glow">
        <span className="font-mono text-lg font-bold">B</span>
      </div>
      <nav className="flex flex-col items-center gap-1">
        {NAV.map(({ id, label, Icon }) => (
          <button
            key={id}
            title={label}
            onClick={() => setView(id)}
            className={`nav-item group ${view === id ? "nav-item-active" : ""}`}
          >
            {view === id && (
              <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-accent" />
            )}
            <Icon size={18} strokeWidth={1.8} />
            <span className="pointer-events-none absolute left-12 z-30 whitespace-nowrap rounded-md border border-hairline-strong bg-raised px-2 py-1 text-xs text-ink opacity-0 shadow-panel transition group-hover:opacity-100">
              {label}
            </span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
