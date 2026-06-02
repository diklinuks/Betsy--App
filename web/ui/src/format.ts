import type { Severity } from "./types";

export const fmtMoney = (n: number | null | undefined, dp = 0): string =>
  n == null ? "—" : "$" + n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const fmtNum = (n: number | null | undefined, dp = 0): string =>
  n == null ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const fmtPct = (n: number | null | undefined, dp = 0): string =>
  n == null ? "—" : (n * 100).toFixed(dp) + "%";

// Tailwind text colour per severity
export const sevText: Record<Severity, string> = {
  info: "text-info",
  good: "text-good",
  action: "text-accent",
  warn: "text-warn",
  bad: "text-bad",
};

// Dot / accent background per severity
export const sevDot: Record<Severity, string> = {
  info: "bg-info",
  good: "bg-good",
  action: "bg-accent",
  warn: "bg-warn",
  bad: "bg-bad",
};

export const sevBorder: Record<Severity, string> = {
  info: "border-info/30",
  good: "border-good/30",
  action: "border-accent/30",
  warn: "border-warn/40",
  bad: "border-bad/40",
};

// Human label per event kind
export const kindLabel: Record<string, string> = {
  consumption: "Consumption",
  day_summary: "Day summary",
  reorder: "Reorder",
  proposal: "Proposal",
  po: "Purchase order",
  shipment: "Shipment",
  delivery: "Delivery",
  score: "Score update",
  lesson: "Lesson",
  escalation: "Escalation",
  approval: "Approval",
  rejection: "Rejection",
  invoice: "Invoice",
  invoice_held: "Invoice held",
  scenario: "Scenario",
  stockout: "Stockout",
};

export const statusTone = (status: string): string => {
  switch (status) {
    case "active":
      return "text-good";
    case "inactive":
      return "text-bad";
    default:
      return "text-muted";
  }
};
