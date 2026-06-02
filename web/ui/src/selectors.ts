import type {
  Decision, DaySnapshot, Delivery, Invoice, Lesson, RunBundle, RunEvent, Supplier,
} from "./types";

/** Day snapshot at or before `day` (snapshots are 1-indexed by sim_day). */
export function snapshotAt(run: RunBundle, day: number): DaySnapshot | undefined {
  return run.days[Math.min(run.days.length, day) - 1];
}

export const eventsUpTo = (run: RunBundle, day: number): RunEvent[] =>
  run.events.filter((e) => e.sim_day <= day);

export const eventsOnDay = (run: RunBundle, day: number): RunEvent[] =>
  run.events.filter((e) => e.sim_day === day);

export const decisionsUpTo = (run: RunBundle, day: number): Decision[] =>
  run.decisions.filter((d) => d.sim_day <= day);

export const deliveriesUpTo = (run: RunBundle, day: number): Delivery[] =>
  run.deliveries.filter((d) => d.sim_day <= day);

export const invoicesUpTo = (run: RunBundle, day: number): Invoice[] =>
  run.invoices.filter((v) => v.sim_day <= day);

export const lessonsUpTo = (run: RunBundle, day: number): Lesson[] =>
  run.lessons.filter((l) => l.sim_day <= day);

export interface Kpis {
  spendMtd: number;
  spendTotal: number;
  monthlyCap: number;
  posPlaced: number;
  onTimeRate: number | null;
  deliveries: number;
  invoiceErrors: number;
  lessons: number;
  escalations: number;
  approvalRate: number | null;
  stockouts: number;
  activeSuppliers: number;
}

/** KPIs computed strictly from what's known up to `day`. */
export function kpisAt(run: RunBundle, day: number): Kpis {
  const snap = snapshotAt(run, day);
  const evs = eventsUpTo(run, day);
  const dels = deliveriesUpTo(run, day);
  const onTime = dels.filter((d) => d.on_time).length;
  const approvals = evs.filter((e) => e.kind === "approval").length;
  const rejections = evs.filter((e) => e.kind === "rejection").length;
  const resolved = approvals + rejections;
  const statuses = snap?.supplier_status ?? {};
  return {
    spendMtd: snap?.spend_mtd ?? 0,
    spendTotal: snap?.spend_to_date ?? 0,
    monthlyCap: snap?.monthly_cap ?? run.meta.monthly_cap,
    posPlaced: evs.filter((e) => e.kind === "po" && e.severity === "good").length,
    onTimeRate: dels.length ? onTime / dels.length : null,
    deliveries: dels.length,
    invoiceErrors: evs.filter((e) => e.kind === "invoice_held").length,
    lessons: evs.filter((e) => e.kind === "lesson").length,
    escalations: evs.filter((e) => e.kind === "escalation").length,
    approvalRate: resolved ? approvals / resolved : null,
    stockouts: evs.filter((e) => e.kind === "stockout").length,
    activeSuppliers: Object.values(statuses).filter((s) => s === "active").length,
  };
}

export interface SupplierRow {
  supplier: Supplier;
  score: number;
  status: string;
  spark: number[];
}

/** Supplier rows as of `day`, sorted by current score desc. */
export function supplierRowsAt(run: RunBundle, day: number): SupplierRow[] {
  const snap = snapshotAt(run, day);
  return run.suppliers
    .map((supplier) => ({
      supplier,
      score: snap?.supplier_scores[supplier.supplier_id] ?? supplier.final_score,
      status: snap?.supplier_status[supplier.supplier_id] ?? supplier.status,
      spark: supplier.score_history.filter((h) => h.sim_day <= day).map((h) => h.score),
    }))
    .sort((a, b) => b.score - a.score);
}

/** Cumulative spend series up to `day` for the deck area chart. */
export function spendSeries(run: RunBundle, day: number): { day: number; spend: number }[] {
  return run.days
    .filter((d) => d.sim_day <= day)
    .map((d) => ({ day: d.sim_day, spend: d.spend_to_date }));
}
