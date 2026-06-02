// Shape of web/ui/public/run.json — produced by `python -m app.main export`.

export type Severity = "info" | "good" | "action" | "warn" | "bad";

export interface RunEvent {
  id: number;
  sim_day: number;
  abs_day: number;
  kind: string;
  severity: Severity;
  title: string;
  detail: Record<string, unknown>;
  product_id: string | null;
  supplier_id: string | null;
  po_id: string | null;
  decision_id: string | null;
}

export interface InventoryRow {
  product_id: string;
  stock: number;
  reorder_point: number;
  safety_stock: number;
  daily_usage: number;
  days_cover: number | null;
  below_reorder: boolean;
}

export interface DaySnapshot {
  sim_day: number;
  abs_day: number;
  date: string;
  inventory: InventoryRow[];
  supplier_scores: Record<string, number>;
  supplier_status: Record<string, string>;
  spend_to_date: number;
  spend_mtd: number;
  monthly_cap: number;
}

export interface Supplier {
  supplier_id: string;
  name: string;
  price_tier: string;
  base_lead_time_days: number;
  payment_terms: string;
  category_focus: string;
  final_score: number;
  status: string;
  score_history: { sim_day: number; score: number }[];
}

export interface Product {
  product_id: string;
  name: string;
  category: string;
  abc_class: string;
  unit: string;
  daily_usage: number;
  reorder_point: number;
  safety_stock: number;
  base_unit_price: number;
  stock_history: { sim_day: number; stock: number }[];
}

export interface Candidate {
  supplier_id: string;
  score: number;
  unit_price: number;
  lead: number;
}

export interface Decision {
  decision_id: string;
  sim_day: number;
  trigger_type: string;
  product_id: string | null;
  candidates: Candidate[];
  chosen_supplier: string | null;
  chosen_quantity: number | null;
  reasoning: string;
  alternatives: string[];
  confidence: number | null;
  action: string;
  escalated: boolean;
  urgent: boolean;
  attribution: string;
  config_version: number;
  outcome: Record<string, unknown> | null;
}

export interface Approval {
  decision_id: string;
  sim_day: number;
  product_id: string;
  proposal: Record<string, unknown>;
  reason_needed: string;
  status: string;
  jenny_reason: string;
}

export interface Delivery {
  delivery_id: string;
  po_id: string;
  supplier_id: string;
  product_id: string;
  sim_day: number;
  expected_sim_day: number;
  quantity_ordered: number;
  quantity_received: number;
  on_time: boolean;
  quality_pass: boolean;
  defects_count: number;
  notes: string;
}

export interface Invoice {
  invoice_id: string;
  invoice_number: string;
  po_id: string;
  supplier_id: string;
  sim_day: number;
  amount: number;
  po_amount: number;
  matches_po: boolean;
  is_duplicate: boolean;
  payment_status: string;
  anomaly_flag: string;
}

export interface Lesson {
  sim_day: number;
  supplier_id: string | null;
  product_id: string | null;
  decision_id: string | null;
  kind: string;
  text: string;
}

export interface Scenario {
  id: string;
  type: string;
  trigger_sim_day: number | null;
  description: string;
  fired: boolean;
}

export interface Criterion {
  target: number;
  actual: number;
  pass: boolean;
}

export interface Report {
  success_criteria: Record<string, Criterion>;
  all_criteria_pass: boolean;
  approvals: { approved: number; rejected: number; rate: number };
  invoice_errors_caught: number;
  stockouts: { occurred: number; prevented: number };
  decisions: { total: number; pos_generated: number; escalated: number };
  scenario_coverage: { fired: string[]; missing: string[]; detail: Record<string, boolean> };
  final_supplier_scores: Record<string, number>;
}

export interface RunBundle {
  meta: {
    generated_at: string;
    sim_days: number;
    start_date: string;
    seed: number;
    agent_mode: string;
    used_llm: boolean;
    per_po_cap: number;
    monthly_cap: number;
    weights: Record<string, number>;
    counts: Record<string, number>;
  };
  suppliers: Supplier[];
  products: Product[];
  days: DaySnapshot[];
  events: RunEvent[];
  decisions: Decision[];
  approvals: Approval[];
  deliveries: Delivery[];
  invoices: Invoice[];
  lessons: Lesson[];
  scenarios: Scenario[];
  report: Report;
}

export type ViewId =
  | "deck"
  | "activity"
  | "suppliers"
  | "inventory"
  | "decisions"
  | "deliveries"
  | "invoices"
  | "lessons"
  | "scenarios"
  | "report";
