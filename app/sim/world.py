"""The world-simulator: the environment Betsy acts in during the live run.

Given the supplier Betsy ACTUALLY chose, it produces realistic delivery/invoice
outcomes from that supplier's intrinsic quality, and injects the scripted scenarios
on schedule (Scenarios.md). Deterministic given the seed (LLM choices aside).
"""
from __future__ import annotations

import random

from sqlalchemy import select

from app.db.models import Invoice, Product, PurchaseOrder, Supplier
from app.sim.scenarios import (
    active_invoice_override, world_scenarios_for_day,
)
from app.tools.functions import _next_id
from app.util import day_to_date, phase_of, sim_day as to_sim_day


class SimWorld:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.fired: set[str] = set()
        self.pending_deliveries: list[dict] = []   # {po_id, outcome, day} (handles lateness)
        self.pending_remainders: list[dict] = []   # partial-delivery remainders
        self.pending_invoices: list[dict] = []      # {po_id, day}
        self.events: list[str] = []                 # human-readable log for the day

    # --------------------------- availability events --------------------------- #
    def apply_availability_events(self, session, abs_day: int) -> None:
        sd = to_sim_day(abs_day)
        # restore any supplier shortage that has expired
        from app.sim.scenarios import SCENARIOS
        for sc in SCENARIOS:
            if sc["type"] == "supplier_shortage":
                sup = session.get(Supplier, sc["supplier"])
                if sup is None:
                    continue
                if sc["sim_day"] == sd and sup.status == "active":
                    sup.status = "inactive"
                    self.fired.add(sc["id"])
                    self.events.append(f"scenario {sc['id']}: {sc['supplier']} in shortage")
                elif sc.get("until_sim_day") == sd and sup.status == "inactive":
                    sup.status = "active"
                    self.events.append(f"{sc['supplier']} shortage cleared")

        # bankruptcy: flip inactive + cancel open POs
        for sc in world_scenarios_for_day(sd):
            if sc["type"] == "bankruptcy":
                sup = session.get(Supplier, sc["supplier"])
                if sup:
                    sup.status = "inactive"
                for po in session.execute(
                    select(PurchaseOrder).where(
                        PurchaseOrder.supplier_id == sc["supplier"],
                        PurchaseOrder.status == "open")
                ).scalars():
                    po.status = "cancelled"
                    po.notes = (po.notes + f" | cancelled: {sc['supplier']} bankrupt").strip(" |")
                self.fired.add(sc["id"])
                self.events.append(f"scenario {sc['id']}: {sc['supplier']} bankrupt, open POs cancelled")
        session.flush()

    # --------------------------- consumption --------------------------- #
    def apply_consumption(self, session, abs_day: int) -> list[str]:
        sd = to_sim_day(abs_day)
        spikes, forced = {}, set()
        for sc in world_scenarios_for_day(sd):
            if sc["type"] == "demand_spike":
                spikes[sc["product"]] = sc["extra"]
                self.fired.add(sc["id"])
            elif sc["type"] == "force_stockout":
                forced.add(sc["product"])
                self.fired.add(sc["id"])

        stockouts = []
        for p in session.execute(select(Product)).scalars():
            extra = spikes.get(p.product_id, 0)
            p.current_stock = max(0, p.current_stock - (p.daily_usage_rate + extra))
            if p.product_id in forced:
                p.current_stock = 0
                self.events.append(f"scenario forced stockout on {p.product_id}")
            if p.current_stock == 0:
                stockouts.append(p.product_id)
        session.flush()
        return stockouts

    # --------------------------- delivery outcomes --------------------------- #
    def outcome_for_po(self, po: PurchaseOrder, sup: Supplier, abs_day: int) -> dict:
        """Decide a delivery outcome for a PO (supplier quality + scenario override)."""
        from app.sim.scenarios import active_delivery_override

        sd = to_sim_day(po.expected_delivery_day)
        q = sup.quality_score if sup else 0.85
        late = self.rng.choice([1, 1, 2, 2, 3]) if self.rng.random() < (1 - q) * 0.6 else 0
        defect_rate = self.rng.uniform(0.01, 0.05) if self.rng.random() < (1 - q) * 0.25 else 0.0
        defects = int(round(po.quantity * defect_rate))
        short = 0
        partial = None
        note = ""

        ov = active_delivery_override(sd, self.fired)
        if ov:
            if ov["type"] == "late_delivery":
                late = max(late, ov["delay_days"])
            elif ov["type"] == "wrong_quantity":
                short = ov["short"]
            elif ov["type"] == "defect":
                defects = ov["defect_units"]
            elif ov["type"] == "partial_delivery":
                partial = ov
            self.fired.add(ov["id"])
            note = f"scenario {ov['id']}"
            self.events.append(f"scenario {ov['id']}: {ov['type']} on {po.po_id}")

        actual_day = po.expected_delivery_day + late
        if partial:
            first = int(round(po.quantity * partial["first_fraction"]))
            self.pending_remainders.append(
                {"po_id": po.po_id, "qty": po.quantity - first,
                 "day": actual_day + partial["remainder_delay"]})
            return {"actual_day": actual_day, "qty_received": first, "on_time": late == 0,
                    "quality_pass": True, "defects": 0, "note": note + " (partial)"}

        quality_pass = defects <= po.quantity * 0.04
        qty_received = 0 if not quality_pass else (po.quantity - short - defects)
        return {"actual_day": actual_day, "qty_received": qty_received,
                "on_time": late == 0, "quality_pass": quality_pass,
                "defects": defects, "note": note}

    def schedule_delivery(self, po_id: str, outcome: dict) -> None:
        self.pending_deliveries.append({"po_id": po_id, "outcome": outcome,
                                        "day": outcome["actual_day"]})

    def due_deliveries(self, abs_day: int) -> list[dict]:
        due = [d for d in self.pending_deliveries if d["day"] == abs_day]
        self.pending_deliveries = [d for d in self.pending_deliveries if d["day"] != abs_day]
        return due

    def due_remainders(self, abs_day: int) -> list[dict]:
        due = [r for r in self.pending_remainders if r["day"] == abs_day]
        self.pending_remainders = [r for r in self.pending_remainders if r["day"] != abs_day]
        return due

    # --------------------------- invoices --------------------------- #
    def schedule_invoice(self, po_id: str, after_day: int) -> None:
        self.pending_invoices.append({"po_id": po_id, "day": after_day + self.rng.randint(1, 3)})

    def make_due_invoices(self, session, abs_day: int) -> list[str]:
        """Create invoice rows due today (with scenario overrides). Returns invoice_ids."""
        sd = to_sim_day(abs_day)
        due = [iv for iv in self.pending_invoices if iv["day"] == abs_day]
        self.pending_invoices = [iv for iv in self.pending_invoices if iv["day"] != abs_day]
        created = []
        for iv in due:
            po = session.get(PurchaseOrder, iv["po_id"])
            if not po or po.status in ("cancelled",):
                continue
            amount = po.total_amount
            ov = active_invoice_override(sd, self.fired)
            inv_no = f"INV-{po.supplier_id}-{abs(hash(po.po_id)) % 10000:04d}"
            make_dup = False
            if ov and ov["type"] == "invoice_mismatch":
                amount = round(po.total_amount * (1 + ov["extra_pct"]), 2)
                self.fired.add(ov["id"]); self.events.append(f"scenario {ov['id']}: invoice mismatch")
            elif ov and ov["type"] == "duplicate_invoice":
                make_dup = True
                self.fired.add(ov["id"]); self.events.append(f"scenario {ov['id']}: duplicate invoice")

            created.append(self._insert_invoice(session, po, amount, inv_no, abs_day, sd))
            if make_dup:  # second row, same invoice_number -> caught by invoice_match
                created.append(self._insert_invoice(session, po, amount, inv_no, abs_day, sd))
        return created

    def _insert_invoice(self, session, po, amount, inv_no, abs_day, sd) -> str:
        inv_id = _next_id(session, Invoice, Invoice.invoice_id, "INV-L")
        session.add(Invoice(
            invoice_id=inv_id, invoice_number=inv_no, po_id=po.po_id,
            supplier_id=po.supplier_id, invoice_day=abs_day, invoice_date=day_to_date(abs_day),
            amount=amount, po_amount=po.total_amount,
            matches_po=abs(amount - po.total_amount) < 0.01, is_duplicate=False,
            payment_status="paid", anomaly_flag="", phase=phase_of(abs_day),
        ))
        session.flush()
        return inv_id
