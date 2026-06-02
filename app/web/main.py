from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.db.config_repo import current_config, save_config
from app.db.models import (
    Decision, Delivery, Event, Invoice, MemoryEmbedding, PendingApproval, Product,
    PurchaseOrder, SimState, Supplier,
)
from app.db.session import get_session, init_db
from app.sim import runner


@asynccontextmanager
async def lifespan(_app: "FastAPI"):
    """On a fresh host (e.g. Render): ensure the schema + pgvector extension exist,
    and seed the dataset once if the DB is empty. Idempotent — never wipes data."""
    try:
        init_db(drop=False)
        with get_session() as s:
            empty = s.execute(select(func.count()).select_from(Product)).scalar_one() == 0
        if empty:
            from app.db.loader import load_all
            load_all(reset=False)
            print("[startup] dataset seeded.")
    except Exception as e:  # never block startup on a seeding hiccup
        print(f"[startup] seed skipped: {type(e).__name__}: {e}")
    yield


BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="Betsy — Procurement Agent", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


def _pending_count() -> int:
    """Pending-approval count — exposed to every template for the rail badge."""
    try:
        with get_session() as s:
            return int(s.execute(
                select(func.count()).select_from(PendingApproval)
                .where(PendingApproval.status == "pending")).scalar_one() or 0)
    except Exception:
        return 0


templates.env.globals["pending_count"] = _pending_count


def _back(request: Request, default: str = "/") -> RedirectResponse:
    """Redirect to the page the action came from (so controls work from any view)."""
    return RedirectResponse(request.headers.get("referer") or default, status_code=303)


# ----------------------------- helpers ----------------------------- #
def _sim_state(s) -> SimState:
    st = s.get(SimState, 1)
    if not st:
        st = SimState(id=1, status="idle", message="Run the loader first.")
        s.add(st)
        s.flush()
    return st


def _pending(s) -> list[PendingApproval]:
    return s.execute(
        select(PendingApproval).where(PendingApproval.status == "pending")
        .order_by(PendingApproval.created_at)
    ).scalars().all()


def _deck_stats(s) -> dict:
    """Live KPI tiles for the dashboard command-deck. Cheap aggregate queries."""
    def c(q) -> int:
        return int(s.execute(q).scalar_one() or 0)

    not_dead = PurchaseOrder.status.notin_(["cancelled", "rejected"])
    spend = float(s.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0.0))
        .where(PurchaseOrder.phase == "simulation", not_dead)).scalar_one())
    pos = c(select(func.count()).select_from(PurchaseOrder)
            .where(PurchaseOrder.phase == "simulation", not_dead))
    deliveries = c(select(func.count()).select_from(Delivery).where(Delivery.phase == "simulation"))
    on_time = c(select(func.count()).select_from(Delivery)
                .where(Delivery.phase == "simulation", Delivery.on_time.is_(True)))
    invoice_errors = c(select(func.count()).select_from(Invoice)
                       .where(Invoice.phase == "simulation", Invoice.payment_status == "held"))
    lessons = c(select(func.count()).select_from(Event).where(Event.kind == "lesson"))
    approved = c(select(func.count()).select_from(PendingApproval)
                 .where(PendingApproval.status == "approved"))
    rejected = c(select(func.count()).select_from(PendingApproval)
                 .where(PendingApproval.status == "rejected"))
    active = c(select(func.count()).select_from(Supplier).where(Supplier.status == "active"))
    total_sup = c(select(func.count()).select_from(Supplier))
    resolved = approved + rejected
    return {
        "spend": spend, "pos": pos, "deliveries": deliveries, "on_time": on_time,
        "on_time_rate": (on_time / deliveries) if deliveries else None,
        "invoice_errors": invoice_errors, "lessons": lessons,
        "approved": approved, "rejected": rejected,
        "approval_rate": (approved / resolved) if resolved else None,
        "active": active, "total_sup": total_sup,
    }


def _spend_series(s) -> list[dict]:
    """Cumulative procurement spend by sim day (for the deck area chart)."""
    rows = s.execute(
        select(PurchaseOrder.placed_day, PurchaseOrder.total_amount)
        .where(PurchaseOrder.phase == "simulation",
               PurchaseOrder.status.notin_(["cancelled", "rejected"]))).all()
    by_day: dict[int, float] = {}
    for pd, amt in rows:
        by_day[pd] = by_day.get(pd, 0.0) + float(amt or 0)
    cum, series = 0.0, []
    for d in sorted(by_day):
        cum += by_day[d]
        series.append({"day": d - 60, "spend": round(cum, 2)})
    return series


def _supplier_spark(s, supplier_id: str, limit: int = 30) -> list[float]:
    details = s.execute(
        select(Event.detail).where(Event.kind == "score", Event.supplier_id == supplier_id)
        .order_by(Event.id)).scalars().all()
    vals = [float(d["new_score"]) for d in details if d and d.get("new_score") is not None]
    return vals[-limit:]


def _supplier_rows(s) -> list[dict]:
    sups = s.execute(select(Supplier).order_by(Supplier.current_score.desc())).scalars().all()
    return [{"s": sup, "spark": _supplier_spark(s, sup.supplier_id)} for sup in sups]


def _inventory_rows(s) -> list[dict]:
    prods = s.execute(select(Product).order_by(Product.product_id)).scalars().all()
    order = {"stockout": 0, "reorder": 1, "ok": 2}
    out = []
    for p in prods:
        state = "stockout" if p.current_stock == 0 else (
            "reorder" if p.current_stock <= p.reorder_point else "ok")
        out.append({
            "p": p, "state": state,
            "days_cover": round(p.current_stock / p.daily_usage_rate, 1) if p.daily_usage_rate else None,
            "scale": max(p.current_stock, p.reorder_point, p.safety_stock, 1) * 1.25,
        })
    out.sort(key=lambda r: (order[r["state"]], r["days_cover"] if r["days_cover"] is not None else 999))
    return out


def _scenario_rows(s) -> list[dict]:
    from app.eval.export import _scenario_description
    from app.sim.scenarios import SCENARIOS
    st = s.get(SimState, 1)
    fired = set(st.fired_scenarios or []) if st else set()
    return [{"id": sc["id"], "type": sc["type"], "day": sc.get("sim_day"),
             "desc": _scenario_description(sc), "fired": sc["id"] in fired} for sc in SCENARIOS]


def _lessons(s) -> list[MemoryEmbedding]:
    return s.execute(
        select(MemoryEmbedding).where(MemoryEmbedding.kind.in_(["reflection", "rejection"]))
        .order_by(MemoryEmbedding.id.desc()).limit(80)).scalars().all()


def _pending_detailed(s) -> list[dict]:
    out = []
    for pa in _pending(s):
        dec = s.get(Decision, pa.decision_id)
        out.append({"pa": pa, "candidates": (dec.candidates if dec else []) or []})
    return out


def _rejection_reason(s, decision_id: str) -> tuple[str, str]:
    pa = s.get(PendingApproval, decision_id)
    reason = pa.jenny_reason if pa else ""
    lesson = s.execute(
        select(MemoryEmbedding).where(MemoryEmbedding.kind == "rejection",
                                      MemoryEmbedding.decision_id == decision_id)
        .order_by(MemoryEmbedding.id.desc())).scalars().first()
    return reason, (lesson.text if lesson else "")


# ----------------------------- pages ----------------------------- #
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with get_session() as s:
        st = _sim_state(s)
        return templates.TemplateResponse(
            request=request, 
            name="dashboard.html", 
            context={"request": request, "state": st, "running": runner.is_running()}
        )


@app.get("/fragment/topstatus", response_class=HTMLResponse)
def topstatus(request: Request):
    with get_session() as s:
        st = _sim_state(s)
        return templates.TemplateResponse(
            request=request, name="partials/topstatus.html",
            context={"request": request, "state": st,
                     "sim_day": max(0, st.current_day - 60), "pending": _pending_count()})


@app.get("/fragment/live", response_class=HTMLResponse)
def live(request: Request):
    with get_session() as s:
        st = _sim_state(s)
        pending = _pending(s)
        sd = max(0, st.current_day - 60)
        stats = _deck_stats(s)
        _, cfg = current_config(s)
        return templates.TemplateResponse(
            request=request,
            name="partials/live.html",
            context={
                "request": request, "state": st, "pending": pending,
                "running": runner.is_running(), "sim_day": sd, "stats": stats,
                "spend_series": _spend_series(s), "leaders": _supplier_rows(s)[:6],
                "monthly_cap": cfg.get("monthly_cap", 50000),
            }
        )


@app.get("/approvals", response_class=HTMLResponse)
def approvals_page(request: Request):
    with get_session() as s:
        return templates.TemplateResponse(
            request=request, name="approvals.html",
            context={"request": request, "items": _pending_detailed(s),
                     "running": runner.is_running()})


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers_page(request: Request):
    with get_session() as s:
        return templates.TemplateResponse(
            request=request, name="suppliers.html",
            context={"request": request, "rows": _supplier_rows(s)})


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request):
    with get_session() as s:
        return templates.TemplateResponse(
            request=request, name="inventory.html",
            context={"request": request, "rows": _inventory_rows(s)})


@app.get("/lessons", response_class=HTMLResponse)
def lessons_page(request: Request):
    with get_session() as s:
        return templates.TemplateResponse(
            request=request, name="lessons.html",
            context={"request": request, "lessons": _lessons(s)})


@app.get("/scenarios", response_class=HTMLResponse)
def scenarios_page(request: Request):
    with get_session() as s:
        return templates.TemplateResponse(
            request=request, name="scenarios.html",
            context={"request": request, "scenarios": _scenario_rows(s)})


@app.get("/activity", response_class=HTMLResponse)
def activity(request: Request):
    with get_session() as s:
        st = _sim_state(s)
        rows = s.execute(
            select(Event).order_by(Event.id.desc()).limit(250)
        ).scalars().all()
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={"request": request, "events": rows, "state": st,
                     "running": runner.is_running()})


@app.get("/decisions", response_class=HTMLResponse)
def decisions(request: Request):
    with get_session() as s:
        rows = s.execute(select(Decision).order_by(Decision.created_at.desc()).limit(80)).scalars().all()
        return templates.TemplateResponse(
            request=request, 
            name="decisions.html", 
            context={"request": request, "decisions": rows}
        )


@app.get("/decision/{decision_id}", response_class=HTMLResponse)
def decision_detail(request: Request, decision_id: str):
    with get_session() as s:
        d = s.get(Decision, decision_id)
        rej_reason, rej_lesson = ("", "")
        if d and d.action == "rejected":
            rej_reason, rej_lesson = _rejection_reason(s, decision_id)
        return templates.TemplateResponse(
            request=request,
            name="decision_detail.html",
            context={"request": request, "d": d,
                     "rej_reason": rej_reason, "rej_lesson": rej_lesson},
        )


@app.get("/invoices", response_class=HTMLResponse)
def invoices_page(request: Request):
    with get_session() as s:
        rows = s.execute(
            select(Invoice).where(Invoice.phase == "simulation")
            .order_by(Invoice.invoice_day.desc())
        ).scalars().all()
        return templates.TemplateResponse(
            request=request, name="invoices.html",
            context={"request": request, "invoices": rows})


@app.get("/deliveries", response_class=HTMLResponse)
def deliveries_page(request: Request):
    with get_session() as s:
        dels = s.execute(
            select(Delivery).where(Delivery.phase == "simulation")
            .order_by(Delivery.actual_delivery_day.desc())
        ).scalars().all()
        lessons = s.execute(
            select(MemoryEmbedding).where(MemoryEmbedding.kind.in_(["reflection", "rejection"]))
            .order_by(MemoryEmbedding.id.desc()).limit(60)
        ).scalars().all()
        return templates.TemplateResponse(
            request=request, name="deliveries.html",
            context={"request": request, "deliveries": dels, "lessons": lessons})


@app.get("/config", response_class=HTMLResponse)
def config_page(request: Request):
    with get_session() as s:
        ver, cfg = current_config(s)
        suppliers = s.execute(select(Supplier).order_by(Supplier.supplier_id)).scalars().all()
        return templates.TemplateResponse(
            request=request, 
            name="config.html", 
            context={"request": request, "version": ver, "cfg": cfg, "suppliers": suppliers}
        )


@app.get("/report", response_class=HTMLResponse)
def report_page(request: Request):
    from app.eval.report import build_report
    rep = build_report()
    return templates.TemplateResponse(
        request=request, 
        name="report.html", 
        context={"request": request, "rep": rep}
    )


# ----------------------------- actions ----------------------------- #
@app.post("/run")
def run(request: Request):
    runner.start(reset_data=False)
    return _back(request)


@app.post("/run-reset")
def run_reset(request: Request):
    runner.start(reset_data=True)
    return _back(request)


@app.post("/stop")
def stop(request: Request):
    runner.stop()
    return _back(request)


@app.post("/pause")
def pause(request: Request):
    runner.pause()
    return _back(request)


@app.post("/resume")
def resume(request: Request):
    runner.resume()
    return _back(request)


@app.post("/approve/{decision_id}")
def approve(request: Request, decision_id: str, reason: str = Form("")):
    runner.resolve_approval(decision_id, approved=True, reason=reason)
    return _back(request)


@app.post("/reject/{decision_id}")
def reject(request: Request, decision_id: str, reason: str = Form("")):
    runner.resolve_approval(decision_id, approved=False, reason=reason)
    return _back(request)


@app.post("/config")
def save_config_action(
    per_po_cap: float = Form(...), monthly_cap: float = Form(...),
    blocked_suppliers: str = Form(""),
    w_otd: float = Form(...), w_por: float = Form(...),
    w_lead: float = Form(...), w_price: float = Form(...),
):
    with get_session() as s:
        _, cfg = current_config(s)
        cfg = dict(cfg)
        cfg["per_po_cap"] = per_po_cap
        cfg["monthly_cap"] = monthly_cap
        cfg["blocked_suppliers"] = [x.strip() for x in blocked_suppliers.split(",") if x.strip()]
        cfg["weights"] = {"otd": w_otd, "por": w_por,
                          "lead_time_var": w_lead, "price_stability": w_price}
        save_config(s, cfg)
    return RedirectResponse("/config", status_code=303)


@app.get("/api/report")
def api_report():
    from app.eval.report import build_report
    return JSONResponse(build_report())