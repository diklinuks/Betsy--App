# Betsy Dataset — TechParts Manufacturing

Synthetic procurement dataset for the autonomous agent in [[Project Description]]. Implements the data model and 15 test scenarios specified in [[Dataset-Company]].

**Company context:** TechParts Manufacturing, 50–100 employees, ~$2.5M annual procurement spend, 25 SKUs across 5 categories, 15 suppliers.

---

## Files

| File | Rows | Purpose |
|---|---|---|
| `suppliers.csv` | 15 | Static supplier catalog with quality, lead time, MOQ, payment terms. |
| `products.csv` | 25 | Static product catalog with ABC class, usage rate, safety stock, reorder point, and starting stock at simulation day 1. |
| `supplier_products.csv` | 247 | Price catalog: for every (supplier, product) where the supplier covers the product's category. |
| `purchase_orders.csv` | 114 | All POs across the 150-day timeline (42 historical + 72 simulation). |
| `delivery_records.csv` | 113 | Delivery outcomes per PO: on-time, quantity received, defects. |
| `invoices.csv` | 114 | Invoices per PO: amount, PO match, duplicate flag, anomaly flag. |
| `scenarios.md` | — | Maps each test scenario to specific row IDs (audit trail). |
| `generate.py` | — | Deterministic generator (seed 42). Re-run to regenerate everything. |

---

## Day numbering

- **Day 1 = 2026-01-01.** All dates in CSVs are real calendar dates.
- **Historical phase** = Day 1–60 (2026-01-01 to 2026-03-01).
- **Simulation phase** = Day 61–150 (2026-03-02 to 2026-05-30). This is what the scenarios in [[Dataset-Company]] call "sim day 1 through sim day 90."
- The `phase` column on every transaction CSV makes filtering trivial.

**Why split this way:** the historical period gives Betsy 60 days of realistic supplier behavior (~80% on-time deliveries with quality scaled to each supplier's score) so she can derive initial supplier rankings instead of starting with hardcoded constants. The simulation period is where the 15 test scenarios fire.

---

## Schemas

### suppliers.csv

| Column | Type | Notes |
|---|---|---|
| `supplier_id` | string | S01–S15 |
| `name` | string | Display name |
| `category_focus` | string | `;`-separated categories (Electronics, Fasteners, Mechanical, Components, Materials) |
| `price_tier` | string | `$` = ~0.65× base price, `$$` = 0.85×, `$$$` = 1.00×, `$$$$` = 1.35× |
| `base_lead_time_days` | int | Typical lead time (per-product values may vary in supplier_products.csv) |
| `quality_score` | float | 0.0–1.0 initial reliability score (Betsy will update this) |
| `default_moq` | int | Default minimum order quantity |
| `payment_terms` | string | Net 15 / 30 / 45 / 60 |
| `unavailable_from_date` | date | If set, supplier becomes unavailable on this date (used for scenario 3.4) |
| `notes` | string | Free-text characterization |

### products.csv

| Column | Type | Notes |
|---|---|---|
| `product_id` | string | P01–P25 |
| `name` | string | |
| `category` | string | One of the 5 categories |
| `abc_class` | string | A (high value, low volume), B (medium), C (low value, high volume) |
| `unit` | string | unit / lb / ft |
| `base_unit_price` | float | Reference price; actual price per supplier is in supplier_products.csv |
| `daily_usage_rate` | int | Units consumed per day under normal demand |
| `safety_stock` | int | Buffer kept above the reorder point |
| `default_lead_time_days` | int | Industry-typical lead time |
| `reorder_point` | int | `(daily_usage × lead_time) + safety_stock` |
| `stock_at_sim_start` | int | Stock at the start of sim day 1 (= Day 61). **This is the authoritative starting inventory for Betsy** — calibrated so scenarios fire at the right days. It does NOT necessarily equal the natural end-of-historical-period stock (a known and documented simplification). |

### supplier_products.csv

| Column | Type | Notes |
|---|---|---|
| `supplier_id` | string | |
| `product_id` | string | |
| `unit_price` | float | base_unit_price × tier multiplier × ±5% jitter |
| `supplier_lead_time_days` | int | This supplier's lead time for this product (≈ base_lead_time ± 1) |
| `supplier_moq` | int | This supplier's MOQ for this product (scaled by product size) |

### purchase_orders.csv

| Column | Type | Notes |
|---|---|---|
| `po_id` | string | PO-0001+ |
| `supplier_id` | string | |
| `product_id` | string | |
| `placed_date` | date | |
| `expected_delivery_date` | date | placed_date + supplier_lead_time |
| `quantity` | int | |
| `unit_price` | float | Price agreed at time of order |
| `total_amount` | float | quantity × unit_price |
| `status` | string | `open` / `received` / `cancelled` / `rejected` |
| `phase` | string | `historical` / `simulation` |
| `notes` | string | Auto-tagged with scenario IDs where applicable |

### delivery_records.csv

| Column | Type | Notes |
|---|---|---|
| `delivery_id` | string | DLV-0001+ |
| `po_id` | string | FK to purchase_orders.csv |
| `supplier_id` | string | |
| `product_id` | string | |
| `expected_delivery_date` | date | From the PO |
| `actual_delivery_date` | date | What actually happened |
| `quantity_ordered` | int | |
| `quantity_received` | int | May be less than ordered (partial / defects) |
| `on_time` | bool | `true` / `false` |
| `quality_pass` | bool | `false` means batch rejected |
| `defects_count` | int | Number of defective units |
| `phase` | string | |
| `notes` | string | |

Note: scenario 4.3 (partial delivery) produces **two** delivery rows for one PO — initial partial + remainder.

### invoices.csv

| Column | Type | Notes |
|---|---|---|
| `invoice_id` | string | INV-0001+ |
| `invoice_number` | string | Supplier-issued invoice number `INV-{supplier}-{N}` |
| `po_id` | string | FK |
| `supplier_id` | string | |
| `invoice_date` | date | |
| `amount` | float | What the supplier billed |
| `po_amount` | float | What the PO total was |
| `matches_po` | bool | `amount == po_amount` |
| `is_duplicate` | bool | `true` for scenario 4.2 |
| `payment_status` | string | `paid` / `held` |
| `phase` | string | |
| `anomaly_flag` | string | Free-text reason if held |

---

## How to regenerate

```bash
cd data
python3 generate.py
```

Deterministic — same seed (42) produces the same dataset. Change `SEED` at the top of `generate.py` to get a different noise pattern while preserving all scenario events.

---

## Known simplifications

- **Stock continuity:** the historical depletion loop and `stock_at_sim_start` are decoupled. Historical POs and deliveries describe one realistic-looking depletion history; `stock_at_sim_start` is the authoritative inventory state Betsy reads at sim day 1, calibrated so scenarios trigger at the right days. If you want strict continuity, you'd need to back-solve initial historical stock to match.
- **Currency:** USD everywhere, no FX.
- **Single warehouse:** stock is a single value per product. No multi-location.
- **Demand model:** deterministic daily usage rate plus one scripted spike (scenario 2.1). No seasonality or stochastic demand.
- **No deliveries straddle the run:** transactions past sim day 90 are truncated.
- **One supplier per PO:** no split orders across suppliers in a single PO.

These simplifications are intentional — the dataset's purpose is to exercise Betsy's decision logic against the 15 scenarios, not to model a real ERP.
