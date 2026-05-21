from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db.config_repo import current_config, save_config
from app.db.models import Decision, PendingApproval, Product, SimState, Supplier
from app.db.session import get_session
from app.sim import runner

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="Betsy — Procurement Agent")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


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


@app.get("/fragment/live", response_class=HTMLResponse)
def live(request: Request):
    with get_session() as s:
        st = _sim_state(s)
        pending = _pending(s)
        sd = max(0, st.current_day - 60)
        return templates.TemplateResponse(
            request=request, 
            name="partials/live.html", 
            context={
                "request": request, "state": st, "pending": pending,
                "running": runner.is_running(), "sim_day": sd,
            }
        )


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
        return templates.TemplateResponse(
            request=request,
            name="decision_detail.html",
            context={"request": request, "d": d},
        )


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
def run():
    runner.start(reset_data=False)
    return RedirectResponse("/", status_code=303)


@app.post("/run-reset")
def run_reset():
    runner.start(reset_data=True)
    return RedirectResponse("/", status_code=303)


@app.post("/stop")
def stop():
    runner.stop()
    return RedirectResponse("/", status_code=303)


@app.post("/pause")
def pause():
    runner.pause()
    return RedirectResponse("/", status_code=303)


@app.post("/resume")
def resume():
    runner.resume()
    return RedirectResponse("/", status_code=303)


@app.post("/approve/{decision_id}")
def approve(decision_id: str, reason: str = Form("")):
    runner.resolve_approval(decision_id, approved=True, reason=reason)
    return RedirectResponse("/", status_code=303)


@app.post("/reject/{decision_id}")
def reject(decision_id: str, reason: str = Form("")):
    runner.resolve_approval(decision_id, approved=False, reason=reason)
    return RedirectResponse("/", status_code=303)


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