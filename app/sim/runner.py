"""The simulation runner — the day-tick scheduler (Triggers.md).

Order per day: Consumption -> Delivery -> Inventory check -> Invoice.
Runs in a background thread. On an over-cap / escalated PO it writes a pending
approval, marks the sim paused, and blocks until the dashboard resolves it
(LangGraph-style interrupt, coordinated through the DB so the web layer can answer).
"""
from __future__ import annotations

import threading
import time
import uuid

from sqlalchemy import select

from app.agent.graph import propose_decision
from app.config.settings import DAY_DELAY_SECONDS, HISTORICAL_END_DAY, SIM_END_DAY
from app.db.config_repo import current_config
from app.db.models import (
    Decision, PendingApproval, Product, PurchaseOrder, SimState, Supplier,
)
from app.db.session import get_session
from app.learning.reflection import record_rejection, reflect_on_outcome
from app.sim.world import SimWorld
from app.tools import functions as f
from app.util import sim_day as to_sim_day

# ----------------------------- background control ----------------------------- #
_thread: threading.Thread | None = None
_stop = threading.Event()
_pause = threading.Event()
AUTO_APPROVE = False  # headless mode: resolve approvals automatically (no dashboard)
ABC_ORDER = {"A": 0, "B": 1, "C": 2}


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def start(reset_data: bool = False) -> bool:
    """Launch the sim in a background thread. Returns False if already running."""
    global _thread
    if is_running():
        return False
    if reset_data:
        from app.db.loader import load_all
        load_all(reset=True)
    _stop.clear()
    _thread = threading.Thread(target=_run, name="betsy-sim", daemon=True)
    _thread.start()
    return True


def stop() -> None:
    _stop.set()
    _pause.clear()


def pause() -> None:
    _pause.set()


def resume() -> None:
    _pause.clear()


def is_paused() -> bool:
    return _pause.is_set()


def _wait_if_paused(abs_day: int) -> None:
    announced = False
    while _pause.is_set() and not _stop.is_set():
        if not announced:
            _set_state("paused", abs_day, f"Paused by user at sim day {to_sim_day(abs_day)}.")
            announced = True
        time.sleep(0.5)
    if announced and not _stop.is_set():
        _set_state("running", abs_day, "Resumed.")


def resolve_approval(decision_id: str, approved: bool, reason: str) -> None:
    """Called by the web layer when Jenny answers an approval."""
    with get_session() as s:
        pa = s.get(PendingApproval, decision_id)
        if pa and pa.status == "pending":
            pa.status = "approved" if approved else "rejected"
            pa.jenny_reason = reason
            from datetime import datetime
            pa.resolved_at = datetime.utcnow()


def _set_state(status: str, day: int | None = None, message: str = "") -> None:
    with get_session() as s:
        st = s.get(SimState, 1) or SimState(id=1)
        st.status = status
        if day is not None:
            st.current_day = day
        if message:
            st.message = message
        s.add(st)


# ----------------------------- the loop ----------------------------- #
def _run() -> None:
    world = SimWorld(seed=42)
    _set_state("running", HISTORICAL_END_DAY, "Simulation started.")
    try:
        for abs_day in range(HISTORICAL_END_DAY + 1, SIM_END_DAY + 1):
            if _stop.is_set():
                _set_state("idle", abs_day, "Stopped by user.")
                return
            _wait_if_paused(abs_day)
            if _stop.is_set():
                _set_state("idle", abs_day, "Stopped by user.")
                return
            sd = to_sim_day(abs_day)
            world.events = []

            with get_session() as s:
                world.apply_availability_events(s, abs_day)
                world.apply_consumption(s, abs_day)
                _ship_due_pos(s, world, abs_day)        # open POs reaching expected day -> shipped
                _process_deliveries(s, world, abs_day)  # deliveries that land today

            _inventory_check(world, abs_day)            # reorder decisions (may pause)

            with get_session() as s:
                _process_invoices(s, world, abs_day)

            _set_state("running", abs_day,
                       f"Sim day {sd}/90 — " + ("; ".join(world.events) if world.events else "ok"))
            time.sleep(DAY_DELAY_SECONDS)  # smooth pacing between days
        with get_session() as s:
            st = s.get(SimState, 1)
            if st:
                st.fired_scenarios = sorted(world.fired)
        _set_state("finished", SIM_END_DAY, "Simulation complete.")
    except Exception as e:  # noqa: BLE001
        _set_state("error", message=f"{type(e).__name__}: {e}")
        raise


# ----------------------------- delivery side ----------------------------- #
def _ship_due_pos(s, world: SimWorld, abs_day: int) -> None:
    """POs reaching their expected delivery day: compute outcome, schedule arrival."""
    due = s.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.status == "open",
            PurchaseOrder.expected_delivery_day == abs_day)
    ).scalars().all()
    for po in due:
        sup = s.get(Supplier, po.supplier_id)
        outcome = world.outcome_for_po(po, sup, abs_day)
        po.status = "shipped"
        world.schedule_delivery(po.po_id, outcome)
    s.flush()


def _process_deliveries(s, world: SimWorld, abs_day: int) -> None:
    for d in world.due_deliveries(abs_day):
        po = s.get(PurchaseOrder, d["po_id"])
        if not po or po.status == "cancelled":
            continue
        o = d["outcome"]
        rec = f.delivery_record(
            s, po_id=po.po_id, on_time=o["on_time"], quantity_received=o["qty_received"],
            quality_pass=o["quality_pass"], defects=o["defects"], actual_day=o["actual_day"],
            notes=o["note"])
        if o["qty_received"]:
            f.inventory_update(s, po.product_id, o["qty_received"])
        f.supplier_score_update(s, po.supplier_id, rec["delivery_id"])
        world.schedule_invoice(po.po_id, abs_day)
        _close_decision(s, po, o)  # outcome-triggered reflection
    # partial-delivery remainders
    for r in world.due_remainders(abs_day):
        po = s.get(PurchaseOrder, r["po_id"])
        if po:
            f.inventory_update(s, po.product_id, r["qty"])
            po.notes = (po.notes + " | remainder delivered").strip(" |")
    s.flush()


def _close_decision(s, po: PurchaseOrder, outcome: dict) -> None:
    """Record the outcome on the decision. Reflection (an LLM call) fires only on a
    POOR outcome — late, defective, or short — to stay inside the free-tier quota.
    Good outcomes just record the result with no model call."""
    if not po.decision_id:
        return
    dec = s.get(Decision, po.decision_id)
    if not dec or dec.outcome is not None:
        return
    result = {
        "on_time": outcome["on_time"], "quality_pass": outcome["quality_pass"],
        "qty_received": outcome["qty_received"], "defects": outcome["defects"],
    }
    poor = (not outcome["on_time"]) or (not outcome["quality_pass"]) or outcome["defects"] > 0
    if poor:
        reflect_on_outcome(s, dec, result)   # writes + embeds a lesson (LLM)
    else:
        dec.outcome = result                 # record only; no model call
        s.flush()


# ----------------------------- inventory check / reorder ----------------------------- #
def _inventory_check(world: SimWorld, abs_day: int) -> None:
    """Find SKUs at/below reorder point and decide, prioritised by ABC class."""
    with get_session() as s:
        products = s.execute(select(Product)).scalars().all()
        crossings = []
        for p in products:
            inbound = _inbound_qty(s, p.product_id)
            if p.current_stock + inbound <= p.reorder_point:
                crossings.append(p.product_id)
        crossings.sort(key=lambda pid: ABC_ORDER.get(
            next(pp.abc_class for pp in products if pp.product_id == pid), 3))

    for pid in crossings:
        if _stop.is_set():
            return
        _handle_reorder(world, abs_day, pid)


def _inbound_qty(s, product_id: str) -> int:
    rows = s.execute(
        select(PurchaseOrder.quantity).where(
            PurchaseOrder.product_id == product_id,
            PurchaseOrder.status.in_(["open", "shipped"]))
    ).scalars().all()
    return sum(rows)


def _handle_reorder(world: SimWorld, abs_day: int, product_id: str) -> None:
    sd = to_sim_day(abs_day)
    with get_session() as s:
        p = s.get(Product, product_id)
        cfg_ver, cfg = current_config(s)
        candidates, avoid, feedback = _candidates_for(s, product_id)
        stockout = p.current_stock == 0

        if stockout:  # learning: raise safety stock after a stockout
            bump = p.daily_usage_rate * 7
            p.safety_stock += bump
            p.reorder_point += bump
            s.flush()
            world.events.append(f"stockout on {product_id}: safety stock raised +{bump}")

        if not candidates:
            _log_simple(s, sd, "reorder", product_id, "no active supplier — escalated",
                        escalated=True, action="escalated")
            return

        ctx = {
            "product": {"product_id": p.product_id, "name": p.name, "abc_class": p.abc_class,
                        "current_stock": p.current_stock, "daily_usage": p.daily_usage_rate,
                        "reorder_point": p.reorder_point, "safety_stock": p.safety_stock},
            "candidates": candidates, "sim_day": sd,
            "urgent": stockout or p.current_stock <= p.safety_stock,
            "avoid_suppliers": list(avoid), "jenny_feedback": feedback,
        }

    proposal = propose_decision(ctx)  # LLM (or heuristic) — outside the session

    with get_session() as s:
        p = s.get(Product, product_id)
        _, cfg = current_config(s)
        cfg_ver = current_config(s)[0]
        candidates, _, _ = _candidates_for(s, product_id)
        chosen = _validate_choice(proposal, candidates)
        if chosen is None:
            _log_simple(s, sd, "reorder", product_id, "no valid supplier choice",
                        escalated=True, action="escalated")
            return
        qty = max(int(proposal.get("quantity") or 0), chosen["moq"])
        unit_price = chosen["unit_price"]
        total = round(qty * unit_price, 2)
        decision_id = f"DEC-{uuid.uuid4().hex[:10]}"
        cand_audit = [{"supplier_id": c["supplier_id"], "score": c["current_score"],
                       "unit_price": c["unit_price"], "lead": c["lead_time_days"]}
                      for c in candidates]

        over_cap = total > cfg["per_po_cap"] or \
            f._month_to_date_spend(s, abs_day) + total > cfg["monthly_cap"]
        needs_human = bool(proposal.get("escalate")) or over_cap

        if needs_human:
            reason = ("over per-PO/monthly cap" if over_cap else "Betsy flagged this case")
            s.add(PendingApproval(
                decision_id=decision_id, sim_day=sd, product_id=product_id,
                proposal={"supplier_id": chosen["supplier_id"], "supplier_name": chosen["name"],
                          "quantity": qty, "unit_price": unit_price, "total": total,
                          "lead_time": chosen["lead_time_days"], "reliability": chosen["current_score"],
                          "daily_usage": p.daily_usage_rate, "current_stock": p.current_stock,
                          "reorder_point": p.reorder_point,
                          "days_of_cover": round(p.current_stock / p.daily_usage_rate, 1) if p.daily_usage_rate else None,
                          "reasoning": proposal.get("reasoning", ""),
                          "alternatives": proposal.get("alternatives", []),
                          "confidence": proposal.get("confidence")},
                reason_needed=reason, status="pending"))
            # log the (pending) decision now; attribution set on resolution
            f.decision_log(
                s, decision_id=decision_id, sim_day=sd, trigger_type="reorder",
                product_id=product_id, candidates=cand_audit,
                chosen_supplier=chosen["supplier_id"], chosen_quantity=qty,
                reasoning=proposal.get("reasoning", ""),
                alternatives=proposal.get("alternatives", []),
                confidence=proposal.get("confidence"), action="awaiting_approval",
                escalated=True, attribution="pending", config_version=cfg_ver,
                urgent=ctx["urgent"])

    if needs_human:
        _set_state("paused", abs_day, f"Awaiting approval for {product_id} (sim day {sd}).")
        status, jenny_reason = _await_resolution(decision_id)
        _set_state("running", abs_day, "Resumed.")
        _apply_resolution(decision_id, product_id, chosen, qty, unit_price,
                          abs_day, sd, status, jenny_reason, world)
        return

    # autonomous path
    with get_session() as s:
        res = f.po_generate(s, product_id, chosen["supplier_id"], qty, unit_price,
                            day=abs_day, sim_day=sd, decision_id=decision_id,
                            approved=False, attribution="autonomous",
                            notes=proposal.get("_source", ""))
        action = "po_generated" if res.get("status") == "created" else res.get("status", "blocked")
        f.decision_log(
            s, decision_id=decision_id, sim_day=sd, trigger_type="reorder",
            product_id=product_id, candidates=cand_audit,
            chosen_supplier=chosen["supplier_id"], chosen_quantity=qty,
            reasoning=proposal.get("reasoning", ""), alternatives=proposal.get("alternatives", []),
            confidence=proposal.get("confidence"), action=action, escalated=False,
            attribution="autonomous", config_version=cfg_ver, urgent=ctx["urgent"])


def _await_resolution(decision_id: str) -> tuple[str, str]:
    if AUTO_APPROVE:
        resolve_approval(decision_id, approved=True, reason="auto-approved (headless)")
    while not _stop.is_set():
        with get_session() as s:
            pa = s.get(PendingApproval, decision_id)
            if pa and pa.status != "pending":
                return pa.status, pa.jenny_reason
        time.sleep(0.5)
    return "rejected", "simulation stopped"


def _apply_resolution(decision_id, product_id, chosen, qty, unit_price, abs_day, sd,
                      status, jenny_reason, world: SimWorld) -> None:
    with get_session() as s:
        dec = s.get(Decision, decision_id)
        if status == "approved":
            f.po_generate(s, product_id, chosen["supplier_id"], qty, unit_price,
                          day=abs_day, sim_day=sd, decision_id=decision_id,
                          approved=True, attribution="post-approval",
                          notes="approved by Jenny")
            if dec:
                dec.action = "po_generated"
                dec.attribution = "post-approval"
        else:
            if dec:
                dec.action = "rejected"
                dec.attribution = "post-approval"
                record_rejection(s, dec, jenny_reason or "no reason given")
            world.events.append(f"Jenny rejected reorder for {product_id}")


# ----------------------------- invoice side ----------------------------- #
def _process_invoices(s, world: SimWorld, abs_day: int) -> None:
    for inv_id in world.make_due_invoices(s, abs_day):
        res = f.invoice_match(s, inv_id)
        if res.get("status") == "held":
            sd = to_sim_day(abs_day)
            _log_simple(s, sd, "invoice", None,
                        f"invoice {inv_id} held: {res.get('anomaly')}",
                        escalated=True, action="invoice_held")
            world.events.append(f"invoice anomaly: {res.get('anomaly')}")


# ----------------------------- helpers ----------------------------- #
def _candidates_for(s, product_id: str):
    """Active suppliers for a product, MINUS any Jenny has rejected for it.
    Returns (candidates, avoided_ids, feedback) where feedback = [(supplier, reason), ...].
    This is the learning hook: a rejected supplier is dropped from the next decision so
    Betsy can't keep proposing it."""
    cands = f.supplier_catalogue(s, product_id)
    pas = s.execute(
        select(PendingApproval).where(
            PendingApproval.product_id == product_id,
            PendingApproval.status == "rejected")
    ).scalars().all()
    avoid = {pa.proposal.get("supplier_id") for pa in pas
             if isinstance(pa.proposal, dict) and pa.proposal.get("supplier_id")}
    feedback = [(pa.proposal.get("supplier_id"), pa.jenny_reason) for pa in pas if pa.jenny_reason]
    filtered = [c for c in cands if c["supplier_id"] not in avoid]
    return (filtered or cands), avoid, feedback


def _validate_choice(proposal: dict, candidates: list[dict]) -> dict | None:
    by_id = {c["supplier_id"]: c for c in candidates}
    chosen = by_id.get(proposal.get("chosen_supplier_id"))
    if chosen:
        return chosen
    return max(candidates, key=lambda c: c["current_score"]) if candidates else None


def _log_simple(s, sd, trigger, product_id, reasoning, *, escalated, action) -> None:
    f.decision_log(
        s, decision_id=f"DEC-{uuid.uuid4().hex[:10]}", sim_day=sd, trigger_type=trigger,
        product_id=product_id, candidates=[], chosen_supplier=None, chosen_quantity=None,
        reasoning=reasoning, alternatives=[], confidence=None, action=action,
        escalated=escalated, attribution="autonomous", config_version=1)
