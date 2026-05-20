# Test Scenario Index

Maps each test scenario from [[Dataset-Company#How do I simulate real-world scenarios?]] to the specific rows in the CSVs that realize it. This is the audit trail for "scenario X actually fired in the dataset on day Y, via these rows."

**Day numbering**
- "Sim day N" = day N of the 90-day simulation period.
- "Absolute date" = the calendar date in the CSVs.
- Sim day 1 = absolute day 61 = **2026-03-02**.
- Sim day 90 = absolute day 150 = **2026-05-30**.

---

## Scenario Group 1 — Normal Inventory Management

### Scenario 1.1 — Standard Reorder
- **Trigger:** Sim day 15 (2026-03-15), Product P01 Resistor 1K hits reorder point (120 units, daily usage 10).
- **Row:** `purchase_orders.csv` — **PO-0045** — S13 LuxeParts, 300 units @ $0.0655, total $19.65.
- **Delivery:** `delivery_records.csv` — DLV-0045.
- **Expected Betsy behavior:** Detect reorder threshold, evaluate ≥3 electronics suppliers, place PO. Standard happy path.
- **Test goal:** Basic PO generation logic.

### Scenario 1.2 — Multiple Concurrent Reorders
- **Trigger:** Sim day 30 (2026-03-30), Products P09 Bolt M5 and P15 Bearing 6205 hit reorder point on the same day.
- **Rows:** `purchase_orders.csv` — **PO-0064** (S02 PremiumReliable, 1000× Bolt M5) and **PO-0065** (S15 Backup Specialists, 60× Bearing 6205).
- **Expected Betsy behavior:** Prioritize by ABC class (Bearing = A, Bolt = C). Group or sequence orders, possibly batch same-supplier items.
- **Test goal:** Prioritization and multi-item ordering logic.

---

## Scenario Group 2 — Demand Spikes and Stockouts

### Scenario 2.1 — Sudden Demand Spike
- **Trigger:** Sim day 22 (2026-03-23), Product P03 Diode demand spikes by 200 units on top of normal 15/day usage. Stock collapses to 0.
- **Row:** `purchase_orders.csv` — **PO-0050** — S13 LuxeParts (fastest, 1-day lead), 100 units, total $10.49.
- **Delivery:** DLV-0050, 1-day lead, marked "urgent emergency delivery".
- **Expected Betsy behavior:** Recognize urgency (stock < safety stock or hits zero). Override normal cost-optimization. Pick fastest supplier even at premium price.
- **Test goal:** Override normal criteria when stockout risk is high.

### Scenario 2.2 — Actual Stockout
- **Trigger:** Sim day 45 (2026-04-15), Product P08 Circuit Board A stock reaches 0 before any replenishment PO arrives. Production line halts.
- **Row:** `purchase_orders.csv` — **PO-0072** — S13 LuxeParts, 50 units emergency reorder, tagged "STOCKOUT detected ... safety stock adjusted upward post-incident."
- **Expected Betsy behavior:** Flag stockout event, place emergency PO, trigger post-incident analysis (raise safety stock for P08, escalate to Jenny).
- **Test goal:** Stockout detection + learning (safety-stock recalibration).

### Scenario 2.3 — Cascading Reorders (Motor Shortage)
- **Trigger:** Sim day 35 (2026-04-05), Product P20 Motor 12V hits reorder point. The preferred Components supplier S04 QuickTech is in market shortage.
- **Row:** `purchase_orders.csv` — **PO-0068** — S02 PremiumReliable (escalated premium), 20 units @ $47.07.
- **Expected Betsy behavior:** Recognize shortage, escalate to backup at higher cost, flag for human approval (high cost override).
- **Test goal:** Human-in-the-loop for high-value decisions.

---

## Scenario Group 3 — Supplier Problems

### Scenario 3.1 — Late Delivery (FastCheap)
- **Trigger:** Sim day 8 (2026-03-09), PO with S01 FastCheap Inc for 500 fasteners (P10 Screw M3), expected sim day 14, arrives sim day 15 (1 day late).
- **Rows:** `purchase_orders.csv` — **PO-0043**; `delivery_records.csv` — **DLV-0043** with `on_time=false`.
- **Expected Betsy behavior:** Log the lateness, reduce S01 reliability score (was 0.82 → toward 0.79).
- **Test goal:** Supplier-score updates from delivery performance.

### Scenario 3.2 — Wrong Quantity (TechHub Europe)
- **Trigger:** Sim day 10 (2026-03-11), PO with S08 TechHub Europe for 100 units (P02 Capacitor), delivery sim day 18 with only 95 units.
- **Rows:** `purchase_orders.csv` — **PO-0044**; `delivery_records.csv` — **DLV-0044** with `quantity_received=95` (ordered 100).
- **Expected Betsy behavior:** Detect discrepancy, trigger reorder for missing 5 units, penalize S08 supplier score.
- **Test goal:** Quality control and recovery from quantity errors.

### Scenario 3.3 — Quality Issues (MegaCorp)
- **Trigger:** Sim day 40 (2026-04-10), PO with S07 MegaCorp for 500 rivets (P13), delivery shows 25 defective (5% defect rate). Batch rejected.
- **Rows:** `purchase_orders.csv` — **PO-0069** (status `rejected`); `delivery_records.csv` — **DLV-0069** (`quality_pass=false`, `quantity_received=0`); `invoices.csv` — payment held with anomaly flag.
- **Expected Betsy behavior:** Heavy penalty to S07 quality score, mark unreliable, switch to backup supplier.
- **Test goal:** Quality metrics affect supplier scoring + payment hold.

### Scenario 3.4 — Supplier Becomes Unavailable (GlobalTrade Bankruptcy)
- **Trigger:** Sim day 50 (2026-04-20), S12 GlobalTrade declared bankrupt (encoded in `suppliers.csv:S12.unavailable_from_date`).
- **Setup row:** `purchase_orders.csv` — **PO-0066** — S12, 1000× Connector 8-pin, placed sim day 35, expected sim day 51. Status flipped to `cancelled` on bankruptcy day.
- **Expected Betsy behavior:** Detect PO cancellation, automatically trigger emergency reorder with backup supplier (S05 EcoSupply, S08 TechHub Europe, or S15 Backup Specialists).
- **Test goal:** Graceful supplier-failure handling.

---

## Scenario Group 4 — Invoice and Fraud Detection

### Scenario 4.1 — Invoice Amount Mismatch
- **Trigger:** Sim day 25 (2026-03-26), invoice arrives for a recent received PO with amount higher than PO total (extra 50 units double-charged).
- **Row:** `invoices.csv` — **INV-0058** — amount $518.04 vs PO amount $388.53, `matches_po=false`, `payment_status=held`, anomaly flagged.
- **Expected Betsy behavior:** Three-way match (PO + delivery + invoice). Detect amount mismatch, hold payment, alert Jenny.
- **Test goal:** Invoice matching and anomaly detection.

### Scenario 4.2 — Duplicate Invoice
- **Trigger:** Sim day 32 (2026-04-02), the same invoice arrives twice from S04 QuickTech.
- **Rows:** `invoices.csv` — **INV-0067** with `is_duplicate=true`, identical PO reference and amount as the original invoice (INV-0058's PO PO-0057 / sister invoice earlier in file).
- **Expected Betsy behavior:** Match invoice number + amount + supplier against history, detect duplicate, flag for rejection without payment.
- **Test goal:** Duplicate detection logic.

### Scenario 4.3 — Partial Delivery
- **Trigger:** Sim day 28 (2026-03-29), PO with S07 MegaCorp for 1000 washers (P12), supplier delivers 600 with promise "remainder in 5 days."
- **Rows:** `purchase_orders.csv` — **PO-0058**; `delivery_records.csv` — **DLV-0058** (600 units, "partial") and **DLV-0059** (400 units, "remainder of partial delivery").
- **Expected Betsy behavior:** Record partial, calculate new expected arrival for remainder, update inventory state without flagging fraud.
- **Test goal:** Partial delivery handling without false-positive anomaly.

---

## Scenario Group 5 — Decision-Making Under Constraints

### Scenario 5.1 — Budget Constraint
- **Trigger:** Sim day 18 (2026-03-19), Product P05 Microcontroller hits reorder point. The premium supplier (S02 PremiumReliable) would push spend over the monthly budget.
- **Row:** `purchase_orders.csv` — **PO-0047** — S04 QuickTech (second-best within budget), 90 units.
- **Expected Betsy behavior:** Reject most-expensive option, pick the second-best within budget. If no in-budget option exists, escalate.
- **Test goal:** Budget-aware decision making.

### Scenario 5.2 — Conflicting Criteria
- **Trigger:** Sim day 36 (2026-04-05), Product P06 Temperature Sensor hits reorder. Cheapest (S07) has worst quality and longest lead; fastest (S13) is 3x cost; balanced standard (S04) is in the middle.
- **Row:** `purchase_orders.csv` — **PO-0067** — S04 QuickTech, 150 units.
- **Expected Betsy behavior:** Apply weighted scoring (e.g., 40% quality, 30% price, 30% lead time) and pick the balanced supplier.
- **Test goal:** Multi-criteria weighted scoring works correctly.

### Scenario 5.3 — Human Override
- **Trigger:** Sim day 42 (2026-04-12), Betsy recommends S02 PremiumReliable for P14 Hinge (cost ~$1200). Jenny overrides and picks S03 BulkMaster (cost ~$800, but slower).
- **Row:** `purchase_orders.csv` — **PO-0070** — S03 BulkMaster, 60 units, notes flagged `HUMAN OVERRIDE`. Delivery (DLV-0070) arrives 3 days late.
- **Expected Betsy behavior:** Record override decision, track outcome, feed into learning loop (the override produced a worse outcome → does Betsy update its weights or log as one-off?).
- **Test goal:** HITL system + learning from override outcomes.

---

## Coverage summary

15 scenarios specified in [[Dataset-Company]]. All 15 are realized in the dataset:

| Group | Scenarios | Realized rows |
|---|---|---|
| 1. Normal inventory | 1.1, 1.2 | PO-0045, PO-0064, PO-0065 |
| 2. Demand spikes & stockouts | 2.1, 2.2, 2.3 | PO-0050, PO-0072, PO-0068 |
| 3. Supplier problems | 3.1, 3.2, 3.3, 3.4 | PO-0043, PO-0044, PO-0069, PO-0066 |
| 4. Invoice & fraud | 4.1, 4.2, 4.3 | INV-0058, INV-0067, PO-0058 |
| 5. Decision-making | 5.1, 5.2, 5.3 | PO-0047, PO-0067, PO-0070 |

Plus organic supplier noise across all 42 historical POs (random late deliveries and minor defects scaled to each supplier's quality score) — this is the baseline signal Betsy uses to derive initial supplier scores before sim day 1.
