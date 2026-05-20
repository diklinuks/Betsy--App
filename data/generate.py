"""
Betsy synthetic dataset generator (TechParts Manufacturing).

Produces 6 CSVs spanning Day 1..150 (2026-01-01..2026-05-30):
  Days 1-60   = historical baseline (phase=historical)
  Days 61-150 = simulation period   (phase=simulation, scenarios baked in)

Deterministic: same seed -> same dataset.

Run: python3 generate.py
"""

import csv
import os
import random
from datetime import date, timedelta

SEED = 42
START_DATE = date(2026, 1, 1)
HISTORICAL_END_DAY = 60
SIM_END_DAY = 150
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

random.seed(SEED)


def day_to_date(d):
    return (START_DATE + timedelta(days=d - 1)).isoformat()


def phase_of(d):
    return "historical" if d <= HISTORICAL_END_DAY else "simulation"


# ---------------------------------------------------------------------------
# Static catalogs
# ---------------------------------------------------------------------------

# columns: supplier_id, name, category_focus, price_tier, base_lead_time_days,
#          quality_score, default_moq, payment_terms, unavailable_from_date, notes
SUPPLIERS = [
    ("S01", "FastCheap Inc",       "Electronics;Fasteners",                                 "$$$",   6, 0.82,  100, "Net 30", "", "Cheap but slow, occasional quality issues"),
    ("S02", "PremiumReliable",     "Electronics;Fasteners;Mechanical;Components;Materials", "$$$$",  2, 0.98,   20, "Net 45", "", "Expensive but very reliable, low MOQ"),
    ("S03", "BulkMaster",          "Fasteners;Mechanical",                                  "$$",   11, 0.75,  500, "Net 60", "", "Cheapest, but high MOQ and slow"),
    ("S04", "QuickTech",           "Electronics;Components",                                "$$$",   3, 0.90,   50, "Net 30", "", "Fast delivery, good quality, balanced"),
    ("S05", "EcoSupply",           "Electronics;Fasteners;Mechanical;Components;Materials", "$$$",   9, 0.88,   30, "Net 30", "", "Sustainable, reliable, medium lead time"),
    ("S06", "LocalFasteners",      "Fasteners",                                             "$$",    4, 0.85,  200, "Net 15", "", "Good for fasteners only"),
    ("S07", "MegaCorp",            "Electronics;Fasteners;Mechanical;Components;Materials", "$$",   17, 0.70, 1000, "Net 60", "", "Very cheap, very slow, quality unreliable"),
    ("S08", "TechHub Europe",      "Electronics",                                           "$$$",   8, 0.92,   25, "Net 30", "", "Good for electronics, late ~20% of the time"),
    ("S09", "JustInTime Parts",    "Components;Mechanical",                                 "$$$",   2, 0.89,   10, "Net 15", "", "Expensive but fastest, very low MOQ"),
    ("S10", "ReliableStandard",    "Electronics;Fasteners;Mechanical;Components;Materials", "$$$",   5, 0.87,   40, "Net 30", "", "Consistent, middle-ground option"),
    ("S11", "StorageWarehouse",    "Electronics;Fasteners;Mechanical;Components;Materials", "$$",    1, 0.80,  300, "Net 15", "", "Local, very fast, but lower quality"),
    ("S12", "GlobalTrade",         "Electronics;Fasteners",                                 "$$",   17, 0.78,  600, "Net 60", "2026-04-20", "Bankrupt on sim day 50 (scenario 3.4)"),
    ("S13", "LuxeParts",           "Electronics;Components",                                "$$$$",  1, 0.96,    5, "Net 30", "", "Premium, fastest, extremely low MOQ"),
    ("S14", "MidLevel Supply",     "Fasteners;Mechanical",                                  "$$$",   6, 0.86,   60, "Net 30", "", "Balanced across all criteria"),
    ("S15", "Backup Specialists",  "Electronics;Fasteners;Mechanical;Components;Materials", "$$$",   8, 0.84,   50, "Net 30", "", "Reliable backup supplier, no discounts"),
]

# Tier -> price multiplier off base
TIER_MULT = {"$": 0.65, "$$": 0.85, "$$$": 1.00, "$$$$": 1.35}

# columns: product_id, name, category, abc_class, unit, base_unit_price,
#          daily_usage, safety_stock, default_lead_time, reorder_point, stock_at_sim_start
# stock_at_sim_start is calibrated so scenarios trigger naturally during sim.
PRODUCTS = [
    ("P01", "Resistor 1K Ohm",            "Electronics",  "C", "unit",   0.05,  10,  70, 5, 120,  260),  # scenario 1.1: hits reorder sim day 15
    ("P02", "Capacitor 10uF",             "Electronics",  "C", "unit",   0.15,   8,  60, 5, 100,  500),
    ("P03", "Diode 1N4001",               "Electronics",  "B", "unit",   0.10,  15,  75, 5, 150,  395),  # scenario 2.1: 80 units at sim day 22 before spike
    ("P04", "Transformer 12V",            "Electronics",  "B", "unit",   8.00,   2,  10, 7,  24,   80),
    ("P05", "Microcontroller ATmega328",  "Electronics",  "A", "unit",  35.00,   3,  20, 7,  41,   95),  # scenario 5.1: hits reorder sim day 18
    ("P06", "Temperature Sensor DS18B20", "Electronics",  "B", "unit",   3.00,   5,  25, 7,  60,  235),  # scenario 5.2: hits reorder sim day 36
    ("P07", "Connector 8-pin",            "Electronics",  "C", "unit",   0.40,  20, 100, 6, 220,  800),
    ("P08", "Circuit Board A",            "Electronics",  "A", "unit",  25.00,   4,  20, 7,  48,  180),  # scenario 2.2: stockout sim day 45
    ("P09", "Bolt M5x20",                 "Fasteners",    "C", "unit",   0.08,  25, 150, 5, 275, 1000),  # scenario 1.2: hits reorder sim day 30
    ("P10", "Screw M3x10",                "Fasteners",    "C", "unit",   0.05,  30, 200, 5, 350,  900),
    ("P11", "Hex Nut M5",                 "Fasteners",    "C", "unit",   0.04,  25, 180, 5, 305,  900),
    ("P12", "Washer M5",                  "Fasteners",    "C", "unit",   0.02,  35, 250, 5, 425, 1200),
    ("P13", "Rivet 4mm",                  "Fasteners",    "B", "unit",   0.06,  18, 100, 6, 208,  600),
    ("P14", "Hinge 50mm",                 "Fasteners",    "B", "unit",   1.50,   4,  20, 6,  44,  120),
    ("P15", "Bearing 6205",               "Mechanical",   "A", "unit", 250.00,   2,  10, 7,  24,   82),  # scenario 1.2: hits reorder sim day 30
    ("P16", "Spur Gear 20T",              "Mechanical",   "B", "unit",  12.00,   3,  15, 7,  36,  120),
    ("P17", "Shaft 10mm",                 "Mechanical",   "B", "unit",   8.00,   2,  10, 7,  24,   80),
    ("P18", "Spring Compression 50mm",    "Mechanical",   "C", "unit",   0.80,  10,  50, 5, 100,  300),
    ("P19", "Aluminum Frame 200mm",       "Mechanical",   "B", "unit",  15.00,   2,  10, 7,  24,   80),
    ("P20", "Motor 12V DC",               "Components",   "A", "unit",  35.00,   2,  10, 7,  24,   94),  # scenario 2.3: hits reorder sim day 35
    ("P21", "Relay 5V",                   "Components",   "B", "unit",   3.50,   4,  20, 6,  44,  140),
    ("P22", "Toggle Switch",              "Components",   "C", "unit",   1.20,   6,  30, 6,  66,  200),
    ("P23", "Battery 9V",                 "Components",   "B", "unit",   2.50,   5,  25, 6,  55,  175),
    ("P24", "Aluminum Stock 6061",        "Materials",    "B", "lb",     4.50,  12,  60, 7, 144,  400),
    ("P25", "Copper Wire 14AWG",          "Materials",    "B", "ft",     0.85,  20, 100, 7, 240,  680),
]


def supplier_dict():
    return {s[0]: s for s in SUPPLIERS}


def product_dict():
    return {p[0]: p for p in PRODUCTS}


# ---------------------------------------------------------------------------
# supplier_products catalog
# ---------------------------------------------------------------------------

def build_supplier_products():
    """For every (supplier, product) where supplier covers product's category,
    derive unit_price, supplier-specific lead_time, and supplier_moq.
    """
    rows = []
    for s in SUPPLIERS:
        sid, _, cats, tier, base_lead, _qs, base_moq, _pt, _unav, _notes = s
        cat_set = set(cats.split(";"))
        for p in PRODUCTS:
            pid, _pname, pcat, _abc, _unit, base_price, _du, _ss, _dl, _rp, _stk = p
            if pcat not in cat_set:
                continue
            # price = base * tier multiplier * small per-pair jitter
            jitter = 1.0 + random.uniform(-0.05, 0.05)
            unit_price = round(base_price * TIER_MULT[tier] * jitter, 4)
            # supplier lead time: base ± 1 day, min 1
            lead = max(1, base_lead + random.randint(-1, 1))
            # supplier moq for this product: default scaled by product size
            if base_price < 1.0:
                moq = base_moq  # small parts: keep MOQ as-is
            elif base_price < 20:
                moq = max(5, base_moq // 2)
            else:
                moq = max(2, base_moq // 5)
            rows.append((sid, pid, unit_price, lead, moq))
    return rows


# ---------------------------------------------------------------------------
# Transactions: POs, deliveries, invoices
# ---------------------------------------------------------------------------

class TxnLog:
    def __init__(self):
        self.pos = []
        self.deliveries = []
        self.invoices = []
        self._po_counter = 0
        self._inv_counter = 0

    def next_po_id(self):
        self._po_counter += 1
        return f"PO-{self._po_counter:04d}"

    def next_invoice_no(self, supplier_id):
        self._inv_counter += 1
        return f"INV-{supplier_id}-{self._inv_counter:04d}"


def pick_supplier_for_history(pid, sp_map, sup_map, exclude=None):
    """Realistic historical selection: weighted by quality * inverse price.
    Used only for historical (Days 1-60) baseline.
    """
    exclude = exclude or set()
    candidates = sp_map.get(pid, [])
    candidates = [c for c in candidates if c[0] not in exclude]
    if not candidates:
        return None
    weights = []
    for sid, _pid, unit_price, _lead, _moq in candidates:
        q = sup_map[sid][5]
        # bias toward quality, slight price sensitivity
        w = (q ** 2) / max(unit_price, 0.01) ** 0.2
        weights.append(w)
    return random.choices(candidates, weights=weights, k=1)[0]


def supplier_behavior(sid, sup_map):
    """Probabilistic on-time / quality behavior driven by quality_score.
    Returns (late_days, defect_rate)."""
    q = sup_map[sid][5]
    # late probability scales with (1 - q)
    if random.random() < (1 - q) * 0.6:
        late_days = random.choice([1, 1, 2, 2, 3])
    else:
        late_days = 0
    # defect rate (proportion defective); usually 0
    if random.random() < (1 - q) * 0.25:
        defect_rate = round(random.uniform(0.01, 0.05), 3)
    else:
        defect_rate = 0.0
    return late_days, defect_rate


def make_invoice(log, po, sup, when_day, amount_override=None, dup=False, anomaly=""):
    inv_no = log.next_invoice_no(po["supplier_id"])
    amt = amount_override if amount_override is not None else po["total_amount"]
    log.invoices.append({
        "invoice_id": f"INV-{len(log.invoices)+1:04d}",
        "invoice_number": inv_no,
        "po_id": po["po_id"],
        "supplier_id": po["supplier_id"],
        "invoice_date": day_to_date(when_day),
        "amount": round(amt, 2),
        "po_amount": round(po["total_amount"], 2),
        "matches_po": "true" if abs(amt - po["total_amount"]) < 0.01 else "false",
        "is_duplicate": "true" if dup else "false",
        "payment_status": "paid" if not anomaly else "held",
        "anomaly_flag": anomaly,
        "phase": phase_of(when_day),
    })


def make_delivery(log, po, actual_day, qty_received, defects=0, quality_pass="true", notes=""):
    on_time = "true" if actual_day <= po["expected_delivery_day"] else "false"
    log.deliveries.append({
        "delivery_id": f"DLV-{len(log.deliveries)+1:04d}",
        "po_id": po["po_id"],
        "supplier_id": po["supplier_id"],
        "product_id": po["product_id"],
        "expected_delivery_date": day_to_date(po["expected_delivery_day"]),
        "actual_delivery_date": day_to_date(actual_day),
        "quantity_ordered": po["quantity"],
        "quantity_received": qty_received,
        "on_time": on_time,
        "quality_pass": quality_pass,
        "defects_count": defects,
        "notes": notes,
        "phase": phase_of(actual_day),
    })


def make_po(log, sup_map, sp_map, prod_map, pid, supplier_choice, placed_day,
            quantity, notes=""):
    sid, _pid, unit_price, sup_lead, _moq = supplier_choice
    qty = quantity
    total = round(qty * unit_price, 2)
    expected = placed_day + sup_lead
    po = {
        "po_id": log.next_po_id(),
        "supplier_id": sid,
        "product_id": pid,
        "placed_date": day_to_date(placed_day),
        "expected_delivery_date": day_to_date(expected),
        "expected_delivery_day": expected,
        "placed_day": placed_day,
        "quantity": qty,
        "unit_price": unit_price,
        "total_amount": total,
        "status": "open",
        "notes": notes,
        "phase": phase_of(placed_day),
    }
    log.pos.append(po)
    return po


# ---------------------------------------------------------------------------
# Historical simulation: drive POs from inventory depletion across Days 1..60
# ---------------------------------------------------------------------------

def simulate_inventory_history(log, sup_map, sp_map, prod_map):
    """For each product, run a depletion loop across Days 1..60 issuing POs at
    reorder point, with a 'reasonable but imperfect' supplier policy."""
    for p in PRODUCTS:
        pid, _pname, _cat, _abc, _unit, _bp, du, ss, _dl, rp, _stk = p
        # Start at ~2x reorder point so realistic depletion cycles fire across
        # the 60-day history. Historical end-state stock will NOT equal
        # stock_at_sim_start (which is the authoritative sim starting value
        # from products.csv — documented in README).
        stock = rp * 2 + ss
        outstanding = []  # list of (arrival_day, qty)
        last_supplier = None
        d = 1
        while d <= HISTORICAL_END_DAY:
            # receive any arrivals due today
            arrived_today = [o for o in outstanding if o[0] == d]
            for arr_day, q in arrived_today:
                stock += q
            outstanding = [o for o in outstanding if o[0] != d]
            # consume daily usage
            stock -= du
            if stock < 0:
                stock = 0
            # place PO if at/below reorder point and no outstanding covering it
            inbound = sum(q for _ad, q in outstanding)
            if stock + inbound <= rp:
                pick = pick_supplier_for_history(pid, sp_map, sup_map,
                                                 exclude={last_supplier} if last_supplier else None)
                if pick is None:
                    pick = pick_supplier_for_history(pid, sp_map, sup_map)
                if pick is None:
                    d += 1
                    continue
                sid, _pid, unit_price, sup_lead, sup_moq = pick
                # Order quantity: EOQ-ish heuristic = max(MOQ, ~30 days of usage)
                qty = max(sup_moq, du * 30)
                # Round to nicer numbers
                if qty < 50:
                    qty = int(round(qty / 10.0)) * 10 or sup_moq
                elif qty < 500:
                    qty = int(round(qty / 25.0)) * 25 or sup_moq
                else:
                    qty = int(round(qty / 100.0)) * 100 or sup_moq
                qty = max(qty, sup_moq)
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, qty,
                             notes="auto-generated baseline reorder")
                # Generate delivery (with realistic supplier-behavior noise)
                late, defect_rate = supplier_behavior(sid, sup_map)
                actual = po["expected_delivery_day"] + late
                # historical: clip to day 60 if delivery would exceed history bound
                qty_recv = qty
                defects = int(round(qty * defect_rate))
                if defects > qty * 0.04:
                    quality = "false"
                    notes = f"defective batch: {defects} units rejected"
                    qty_recv = qty - defects
                elif defects > 0:
                    quality = "true"
                    notes = f"{defects} defects in batch (accepted)"
                    qty_recv = qty - defects
                else:
                    quality = "true"
                    notes = ""
                if actual <= HISTORICAL_END_DAY:
                    make_delivery(log, po, actual, qty_recv, defects=defects,
                                  quality_pass=quality, notes=notes)
                    po["status"] = "received"
                    # historical invoices: clean (always match)
                    inv_day = min(actual + random.randint(0, 3), HISTORICAL_END_DAY)
                    make_invoice(log, po, sup_map[sid], inv_day)
                    outstanding.append((actual, qty_recv))
                else:
                    # straddles into simulation period: still place delivery
                    make_delivery(log, po, actual, qty_recv, defects=defects,
                                  quality_pass=quality, notes=notes)
                    po["status"] = "received"
                    inv_day = actual + random.randint(0, 3)
                    make_invoice(log, po, sup_map[sid], inv_day)
                    outstanding.append((actual, qty_recv))
                last_supplier = sid
            d += 1
        # Force end-state stock to match calibrated stock_at_sim_start by
        # logging a final adjustment (no PO/delivery, just stored in product state).
        # We rely on PRODUCTS table for "stock_at_sim_start", so nothing more needed.


# ---------------------------------------------------------------------------
# Simulation period (Days 61..150): inventory + scripted scenario events
# ---------------------------------------------------------------------------

def simulate_sim_period(log, sup_map, sp_map, prod_map):
    """Plays Days 61..150 with Betsy-like reorder behavior + scripted scenarios.

    The 'simulation' rows show ONE possible execution that exercises every test
    scenario from Dataset-Company.md. Scenario IDs are noted in the PO `notes`.
    """
    # stock state per product at start of sim day 1 (= Day 61)
    stock = {p[0]: p[10] for p in PRODUCTS}
    # demand modifiers per product per day: dict (pid, day) -> extra units
    demand_spikes = {("P03", 82): 200}  # scenario 2.1
    # supplier availability: any new PO blocked from S12 from Day 110 onwards
    s12_open_pos_to_cancel = []
    # track outstanding deliveries per product
    outstanding = {p[0]: [] for p in PRODUCTS}
    last_supplier_per_product = {p[0]: None for p in PRODUCTS}
    # Pre-fill outstanding from any historical POs that arrived in sim period
    for po in log.pos:
        if po["expected_delivery_day"] > HISTORICAL_END_DAY:
            # find matching delivery
            d_row = next((d for d in log.deliveries if d["po_id"] == po["po_id"]), None)
            if d_row:
                arrival_day = (date.fromisoformat(d_row["actual_delivery_date"]) - START_DATE).days + 1
                outstanding[po["product_id"]].append((arrival_day, int(d_row["quantity_received"])))

    # ---- helper: pick supplier with scenario-aware overrides ----
    def pick_supplier(pid, day, prefer=None, exclude=None):
        exclude = exclude or set()
        # S12 unavailable after Day 110
        if day >= 110:
            exclude.add("S12")
        cands = [c for c in sp_map.get(pid, []) if c[0] not in exclude]
        if not cands:
            return None
        if prefer:
            for c in cands:
                if c[0] == prefer:
                    return c
        return pick_supplier_for_history(pid, sp_map, sup_map, exclude=exclude)

    # Track scenario events we've already triggered to avoid double-firing
    fired = set()

    def schedule_delivery(po, late=0, qty_short=0, defects=0, qty_recv_override=None,
                          partial_remainder_days=None, quality_override=None, notes=""):
        sid = po["supplier_id"]
        actual = po["expected_delivery_day"] + late
        if qty_recv_override is not None:
            qty_recv = qty_recv_override
        else:
            qty_recv = po["quantity"] - qty_short - defects
        if quality_override:
            quality = quality_override
        else:
            quality = "false" if defects > po["quantity"] * 0.04 else "true"
        make_delivery(log, po, actual, qty_recv, defects=defects,
                      quality_pass=quality, notes=notes)
        po["status"] = "received" if quality == "true" else "rejected"
        outstanding[po["product_id"]].append((actual, qty_recv if quality == "true" else 0))
        # partial delivery: schedule remainder
        if partial_remainder_days:
            remainder = po["quantity"] - qty_recv
            rem_day = actual + partial_remainder_days
            make_delivery(log, po, rem_day, remainder, defects=0,
                          quality_pass="true",
                          notes=f"remainder of partial delivery for {po['po_id']}")
            outstanding[po["product_id"]].append((rem_day, remainder))

    # ---- daily loop ----
    for d in range(HISTORICAL_END_DAY + 1, SIM_END_DAY + 1):
        sim_day = d - HISTORICAL_END_DAY  # 1..90

        # receive arrivals
        for pid in stock:
            arrived = [o for o in outstanding[pid] if o[0] == d]
            for _ad, q in arrived:
                stock[pid] += q
            outstanding[pid] = [o for o in outstanding[pid] if o[0] != d]

        # consume daily usage + any demand spikes today
        for p in PRODUCTS:
            pid = p[0]
            du = p[6]
            extra = demand_spikes.get((pid, d), 0)
            stock[pid] -= (du + extra)
            if stock[pid] < 0:
                stock[pid] = 0

        # ---- scripted scenario events keyed to specific sim days ----
        # Scenario 3.1: late delivery from FastCheap (S01). Place PO around sim day 8
        # for 500 fasteners (Screw M3), expected sim day 14, actual sim day 15.
        # Uses P10 not P09 so scenario 1.2 (P09 Bolt) reorder still fires naturally.
        if sim_day == 8 and "3.1" not in fired:
            pid = "P10"
            pick = pick_supplier(pid, d, prefer="S01")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, 500,
                             notes="scenario 3.1: late delivery test")
                schedule_delivery(po, late=1, notes="1 day late (scenario 3.1)")
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 2)
                fired.add("3.1")

        # Scenario 3.2: TechHub Europe (S08) wrong quantity. Sim day 10 PO for 100 units,
        # delivery sim day 18 with 95 units. Uses P02 Capacitor so scenario 1.1
        # (P01 Resistor reorder) still fires naturally.
        if sim_day == 10 and "3.2" not in fired:
            pid = "P02"
            pick = pick_supplier(pid, d, prefer="S08")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, 100,
                             notes="scenario 3.2: wrong quantity test")
                schedule_delivery(po, late=0, qty_short=5,
                                  notes="received 95/100 units (scenario 3.2)")
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 1)
                fired.add("3.2")

        # Scenario 5.1: Microcontroller budget constraint at sim day 18.
        # Stock at sim start = 117; usage 3/day; reorder 41. Hits ~sim day 26.
        # Force escalation: place PO at reorder time noting budget escalation.
        # We just leave the natural reorder to fire (below) and tag it.

        # Scenario 2.1: Diode demand spike consumed sim day 22. Force emergency
        # reorder with the fastest supplier (S13 LuxeParts) regardless of inbound.
        if sim_day == 22 and "2.1" not in fired:
            pick = pick_supplier("P03", d, prefer="S13")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, "P03", pick, d, 100,
                             notes="scenario 2.1: emergency reorder after demand spike (200u) → fastest supplier")
                late, _dr = supplier_behavior(pick[0], sup_map)
                schedule_delivery(po, late=late, notes="urgent emergency delivery (scenario 2.1)")
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 1)
                fired.add("2.1")

        # Scenario 4.1: invoice mismatch at sim day 25 = Day 85. Pick the most recent
        # received PO and emit a follow-up invoice with wrong amount.
        if sim_day == 25 and "4.1" not in fired:
            recent = next((p for p in reversed(log.pos)
                           if p["status"] == "received" and phase_of(p["placed_day"]) == "simulation"), None)
            if recent:
                wrong_amt = round(recent["total_amount"] + recent["unit_price"] * 50, 2)
                make_invoice(log, recent, sup_map[recent["supplier_id"]], d,
                             amount_override=wrong_amt,
                             anomaly="invoice amount exceeds PO by 50 units (scenario 4.1)")
                fired.add("4.1")

        # Scenario 4.3: partial delivery at sim day 28 = Day 88. Place a large PO
        # with S07 MegaCorp that splits into 60% + 40%. Uses P12 Washer.
        if sim_day == 28 and "4.3" not in fired:
            pid = "P12"  # Washer M5
            pick = pick_supplier(pid, d, prefer="S07")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, 1000,
                             notes="scenario 4.3: partial delivery test")
                first_part = 600
                schedule_delivery(po, late=0, qty_recv_override=first_part,
                                  partial_remainder_days=5,
                                  notes="partial: 600 now, 400 in 5 days (scenario 4.3)")
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 1)
                fired.add("4.3")

        # Scenario 4.2: duplicate invoice from QuickTech (S04) at sim day 32 = Day 92.
        # Find a recent QuickTech PO and duplicate its invoice.
        if sim_day == 32 and "4.2" not in fired:
            qt_pos = [p for p in log.pos if p["supplier_id"] == "S04"
                      and phase_of(p["placed_day"]) == "simulation"
                      and p["status"] in ("received", "open")]
            if not qt_pos:
                # ensure there's at least one QuickTech PO; create one
                pid = "P05"  # Microcontroller fits QuickTech
                pick = pick_supplier(pid, d, prefer="S04")
                if pick:
                    po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d - 7, 50,
                                 notes="scenario 4.2 setup: QuickTech PO")
                    schedule_delivery(po, late=0)
                    make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 1)
                    qt_pos = [po]
            target = qt_pos[-1]
            # original invoice already issued; emit duplicate
            make_invoice(log, target, sup_map[target["supplier_id"]], d,
                         dup=True, anomaly="duplicate of prior invoice (scenario 4.2)")
            fired.add("4.2")

        # Scenario 5.2: Sensor reorder at sim day 36 with conflicting criteria.
        # Just tag the natural reorder if it fires here.

        # Scenario 3.3: MegaCorp defective shipment at sim day 40. Place PO with S07,
        # ship with 5% defects, batch rejected. Uses P13 Rivet so P09 Bolt's
        # scenario 1.2 reorder still fires naturally.
        if sim_day == 40 and "3.3" not in fired:
            pid = "P13"
            pick = pick_supplier(pid, d, prefer="S07")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, 500,
                             notes="scenario 3.3: quality test")
                schedule_delivery(po, late=0, defects=25, quality_override="false",
                                  qty_recv_override=0,
                                  notes="batch rejected: 25/500 defective = 5% (scenario 3.3)")
                # invoice still gets created but held
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 1,
                             anomaly="rejected shipment, payment held (scenario 3.3)")
                fired.add("3.3")

        # Scenario 5.3: human override at sim day 42 = Day 102. Betsy recommends S02
        # for hinges, human picks S03 (slower, cheaper). Override delivered late.
        if sim_day == 42 and "5.3" not in fired:
            pid = "P14"  # Hinge
            # S03 (BulkMaster) covers Fasteners
            pick = pick_supplier(pid, d, prefer="S03")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, 60,
                             notes="scenario 5.3: HUMAN OVERRIDE — Betsy recommended S02, Jenny chose S03")
                schedule_delivery(po, late=3, notes="3 days late (scenario 5.3: override outcome)")
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 2)
                fired.add("5.3")

        # Scenario 2.3: Motor 12V reorder at sim day 35 with QuickTech in shortage.
        # Encoded: QuickTech still in catalog but if Betsy reorders Motor she'd see
        # a flagged escalation (notes field). We'll tag the PO when it fires.

        # Scenario 3.4 setup: ensure S12 has an open PO at sim day 50.
        # Place a long-lead-time PO with S12 on sim day 35 (still open when bankrupt).
        if sim_day == 35 and "3.4-setup" not in fired:
            pid = "P07"  # Connector 8-pin (Electronics, S12 covers)
            pick = pick_supplier(pid, d, prefer="S12")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, 1000,
                             notes="scenario 3.4 setup: open PO with S12 GlobalTrade")
                # NOTE: do NOT schedule a delivery — the bankruptcy event will mark it cancelled.
                fired.add("3.4-setup")

        # Scenario 3.4: S12 bankrupt on sim day 50 (= Day 110). Cancel any open PO from S12.
        if sim_day == 50 and "3.4" not in fired:
            for po in log.pos:
                if po["supplier_id"] == "S12" and po["status"] == "open":
                    po["status"] = "cancelled"
                    po["notes"] += " | cancelled: S12 bankrupt (scenario 3.4)"
                    # also tag delivery if exists as failed
                    for dlv in log.deliveries:
                        if dlv["po_id"] == po["po_id"]:
                            dlv["notes"] = (dlv["notes"] + " | supplier bankrupt").strip(" |")
                            dlv["quantity_received"] = 0
                            dlv["quality_pass"] = "false"
            fired.add("3.4")

        # Scenario 2.2: Circuit Board A stockout at sim day 45.
        # Stock at sim day 1 = 220; usage 4/day; reorder 48. Hits reorder ~ day 43.
        # If Betsy doesn't reorder in time (or supplier is slow), stockout on day 45.
        # We'll let the natural loop fire a reorder; to FORCE stockout, we skip it.
        # The flag below marks the stockout event in scenarios.md.
        if sim_day == 45 and "2.2" not in fired:
            # Force stockout demonstration (historical PO arrivals may have
            # delayed actual depletion). Mark stock as 0 and place emergency reorder.
            stock["P08"] = 0
            pick = pick_supplier("P08", d, prefer="S13")
            if pick:
                po = make_po(log, sup_map, sp_map, prod_map, "P08", pick, d, 50,
                             notes="scenario 2.2: STOCKOUT detected on P08 → emergency reorder; safety stock adjusted upward post-incident")
                late, _dr = supplier_behavior(pick[0], sup_map)
                schedule_delivery(po, late=late, notes="post-stockout emergency delivery (scenario 2.2)")
                make_invoice(log, po, sup_map[pick[0]], po["expected_delivery_day"] + 1)
            fired.add("2.2")

        # ---- natural reorder loop for sim period ----
        for p in PRODUCTS:
            pid = p[0]
            du = p[6]
            rp = p[9]
            inbound = sum(q for _ad, q in outstanding[pid])
            if stock[pid] + inbound > rp:
                continue
            # scenario 2.2: suppress P08 reorders for the first 45 sim days
            # so stock depletes to zero and the stockout is observable
            if pid == "P08" and sim_day <= 45:
                continue
            # pick supplier
            preferred = None
            tag = ""
            # Scenario 2.1 (sim day 22): Diode urgent → prefer fastest (S13)
            if pid == "P03" and 81 <= d <= 84:
                preferred = "S13"
                tag = "scenario 2.1: demand spike → fastest supplier"
            # Scenario 5.1 (sim day 18-26): Microcontroller budget constraint
            if pid == "P05" and sim_day <= 28 and "5.1" not in fired:
                preferred = "S04"  # second-best within budget
                tag = "scenario 5.1: budget constraint → 2nd best supplier within budget"
                fired.add("5.1")
            # Scenario 1.1 (sim day 15-17): standard Resistor reorder
            if pid == "P01" and sim_day <= 18 and "1.1" not in fired:
                tag = "scenario 1.1: standard reorder"
                fired.add("1.1")
            # Scenario 1.2 (sim day 30): Bolt/Bearing simultaneous reorder
            if pid in ("P09", "P15") and 88 <= d <= 92:
                if "1.2" not in fired:
                    tag = "scenario 1.2: concurrent reorder (multi-product)"
                    fired.add("1.2")
                else:
                    tag = "scenario 1.2: concurrent reorder (multi-product)"
            # Scenario 5.2 (sim day 36): Sensor weighted scoring
            if pid == "P06" and 95 <= d <= 98 and "5.2" not in fired:
                preferred = "S04"  # standard balanced pick
                tag = "scenario 5.2: weighted scoring → balanced supplier"
                fired.add("5.2")
            # Scenario 2.3 (sim day 35): Motor reorder, QuickTech in shortage
            if pid == "P20" and 93 <= d <= 97 and "2.3" not in fired:
                preferred = "S02"  # escalate to premium
                tag = "scenario 2.3: motor shortage → escalate to premium (HITL)"
                fired.add("2.3")

            pick = pick_supplier(pid, d, prefer=preferred,
                                 exclude={last_supplier_per_product[pid]} if last_supplier_per_product[pid] else None)
            if pick is None:
                pick = pick_supplier(pid, d, prefer=preferred)
            if pick is None:
                continue
            sid, _pid, unit_price, sup_lead, sup_moq = pick
            qty = max(sup_moq, du * 30)
            if qty < 50:
                qty = int(round(qty / 10.0)) * 10 or sup_moq
            elif qty < 500:
                qty = int(round(qty / 25.0)) * 25 or sup_moq
            else:
                qty = int(round(qty / 100.0)) * 100 or sup_moq
            qty = max(qty, sup_moq)
            po = make_po(log, sup_map, sp_map, prod_map, pid, pick, d, qty,
                         notes=tag or "auto reorder")
            # delivery behavior in sim period: natural noise, unless overridden by scenario
            late, defect_rate = supplier_behavior(sid, sup_map)
            defects = int(round(qty * defect_rate))
            if defects > qty * 0.04:
                quality = "false"
                qty_recv = qty - defects
                notes = f"defective: {defects} units rejected"
            elif defects > 0:
                quality = "true"
                qty_recv = qty - defects
                notes = f"{defects} defects (accepted)"
            else:
                quality = "true"
                qty_recv = qty
                notes = ""
            actual = po["expected_delivery_day"] + late
            if actual <= SIM_END_DAY + 10:  # allow tails past sim end for realism
                make_delivery(log, po, actual, qty_recv, defects=defects,
                              quality_pass=quality, notes=notes)
                po["status"] = "received"
                inv_day = actual + random.randint(0, 3)
                if inv_day <= SIM_END_DAY + 15:
                    make_invoice(log, po, sup_map[sid], inv_day)
                outstanding[pid].append((actual, qty_recv if quality == "true" else 0))
            last_supplier_per_product[pid] = sid


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_suppliers():
    path = os.path.join(DATA_DIR, "suppliers.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["supplier_id", "name", "category_focus", "price_tier",
                    "base_lead_time_days", "quality_score", "default_moq",
                    "payment_terms", "unavailable_from_date", "notes"])
        for s in SUPPLIERS:
            w.writerow(s)
    return path


def write_products():
    path = os.path.join(DATA_DIR, "products.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "name", "category", "abc_class", "unit",
                    "base_unit_price", "daily_usage_rate", "safety_stock",
                    "default_lead_time_days", "reorder_point",
                    "stock_at_sim_start"])
        for p in PRODUCTS:
            w.writerow(p)
    return path


def write_supplier_products(rows):
    path = os.path.join(DATA_DIR, "supplier_products.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["supplier_id", "product_id", "unit_price",
                    "supplier_lead_time_days", "supplier_moq"])
        for r in rows:
            w.writerow(r)
    return path


def write_pos(log):
    path = os.path.join(DATA_DIR, "purchase_orders.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["po_id", "supplier_id", "product_id", "placed_date",
                    "expected_delivery_date", "quantity", "unit_price",
                    "total_amount", "status", "phase", "notes"])
        for po in log.pos:
            w.writerow([po["po_id"], po["supplier_id"], po["product_id"],
                        po["placed_date"], po["expected_delivery_date"],
                        po["quantity"], po["unit_price"], po["total_amount"],
                        po["status"], po["phase"], po["notes"]])
    return path


def write_deliveries(log):
    path = os.path.join(DATA_DIR, "delivery_records.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["delivery_id", "po_id", "supplier_id", "product_id",
                    "expected_delivery_date", "actual_delivery_date",
                    "quantity_ordered", "quantity_received", "on_time",
                    "quality_pass", "defects_count", "phase", "notes"])
        for d in log.deliveries:
            w.writerow([d["delivery_id"], d["po_id"], d["supplier_id"],
                        d["product_id"], d["expected_delivery_date"],
                        d["actual_delivery_date"], d["quantity_ordered"],
                        d["quantity_received"], d["on_time"], d["quality_pass"],
                        d["defects_count"], d["phase"], d["notes"]])
    return path


def write_invoices(log):
    path = os.path.join(DATA_DIR, "invoices.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["invoice_id", "invoice_number", "po_id", "supplier_id",
                    "invoice_date", "amount", "po_amount", "matches_po",
                    "is_duplicate", "payment_status", "phase",
                    "anomaly_flag"])
        for inv in log.invoices:
            w.writerow([inv["invoice_id"], inv["invoice_number"], inv["po_id"],
                        inv["supplier_id"], inv["invoice_date"], inv["amount"],
                        inv["po_amount"], inv["matches_po"], inv["is_duplicate"],
                        inv["payment_status"], inv["phase"], inv["anomaly_flag"]])
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sup_map = supplier_dict()
    prod_map = product_dict()
    sp_rows = build_supplier_products()
    # build sp_map: pid -> list of (sid, pid, price, lead, moq)
    sp_map = {}
    for r in sp_rows:
        sp_map.setdefault(r[1], []).append(r)

    log = TxnLog()
    simulate_inventory_history(log, sup_map, sp_map, prod_map)
    simulate_sim_period(log, sup_map, sp_map, prod_map)

    # write
    paths = [
        write_suppliers(),
        write_products(),
        write_supplier_products(sp_rows),
        write_pos(log),
        write_deliveries(log),
        write_invoices(log),
    ]
    print("Generated:")
    for p in paths:
        print(f"  {os.path.relpath(p, DATA_DIR)}")
    print(f"Totals: {len(log.pos)} POs, {len(log.deliveries)} deliveries, "
          f"{len(log.invoices)} invoices")


if __name__ == "__main__":
    main()
