import { useEffect } from "react";
import { useReplay } from "./store";
import { Sidebar } from "./components/Sidebar";
import { TransportBar } from "./components/TransportBar";
import { DecisionDrawer } from "./components/DecisionDrawer";
import { DeckPanel } from "./panels/DeckPanel";
import { ActivityPanel } from "./panels/ActivityPanel";
import { SuppliersPanel } from "./panels/SuppliersPanel";
import { InventoryPanel } from "./panels/InventoryPanel";
import { DecisionsPanel } from "./panels/DecisionsPanel";
import { DeliveriesPanel } from "./panels/DeliveriesPanel";
import { InvoicesPanel } from "./panels/InvoicesPanel";
import { LessonsPanel } from "./panels/LessonsPanel";
import { ScenariosPanel } from "./panels/ScenariosPanel";
import { ReportPanel } from "./panels/ReportPanel";
import type { FC } from "react";
import type { ViewId } from "./types";

const PANELS: Record<ViewId, FC> = {
  deck: DeckPanel,
  activity: ActivityPanel,
  suppliers: SuppliersPanel,
  inventory: InventoryPanel,
  decisions: DecisionsPanel,
  deliveries: DeliveriesPanel,
  invoices: InvoicesPanel,
  lessons: LessonsPanel,
  scenarios: ScenariosPanel,
  report: ReportPanel,
};

export default function App() {
  const { run, loading, error, view, playing, speed, tick, load } = useReplay();

  useEffect(() => {
    load();
  }, [load]);

  // playback engine: advance the cursor while playing
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => tick(), Math.max(120, 700 / speed));
    return () => window.clearInterval(id);
  }, [playing, speed, tick]);

  if (loading) {
    return (
      <div className="grid h-full place-items-center text-muted">
        <div className="flex items-center gap-3">
          <span className="h-2.5 w-2.5 animate-pulseDot rounded-full bg-accent" />
          Loading run…
        </div>
      </div>
    );
  }
  if (error || !run) {
    return (
      <div className="grid h-full place-items-center px-6 text-center">
        <div className="panel max-w-md p-6">
          <p className="mb-2 font-semibold text-bad">Couldn't load the simulation</p>
          <p className="text-sm text-muted">
            {error ?? "run.json missing"}. Generate it with{" "}
            <code className="font-mono text-accent">python -m app.main export</code>.
          </p>
        </div>
      </div>
    );
  }

  const Panel = PANELS[view];

  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TransportBar />
        <main className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="mx-auto max-w-[1400px]">
            <Panel />
          </div>
        </main>
      </div>
      <DecisionDrawer />
    </div>
  );
}
