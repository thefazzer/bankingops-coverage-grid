"""Regenerates the synthetic fixture responses under tests/fixtures/<model_id>/<i>.json.

All content is SYNTHETIC: vendor/model names are invented; anchors use placeholder G-SIB names
("Example G-SIB A") and generic-looking citations. Run:  python tests/fixtures/_gen_fixtures.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

# ---------------------------------------------------------------- division universe (synthetic)
DIVS = {
    "rates_trading": {
        "a1": [("Interest-rate derivative clearing mandate", "EU", "EMIR Art. 4 (Regulation (EU) 648/2012)"),
               ("Swap dealer business conduct", "US", "CFTC Regulation Part 23 Subpart H")],
        "a2": ("Example G-SIB A", "Annual Report 10-K", 2024, "Fixed Income, Currencies and Commodities markets revenue"),
        "a3": ("BIS", "OTC derivatives statistics: interest rate contracts, notional outstanding", 530.0,
               "USD trillion", "2024-06-30"),
        "function": "rates trader / desk assistant",
        "headcount": [40, 120], "cost": [250000, 450000], "det": 0.65,
        "tasks": [("price a client request for quote from the desk curve", "RFQ ticket, curve snapshot, risk limits",
                   "quote sent and trade booked or declined", "RFQ audit log and booking record"),
                  ("hedge the desk delta within end-of-day limits", "risk report, limit sheet, hedge trades",
                   "end-of-day delta inside limit", "end-of-day risk report and limit breach log"),
                  ("confirm trade economics against counterparty confirmation", "trade ticket, confirmation message",
                   "confirmation matched or discrepancy raised", "confirmation matching record")],
        "axis": {"business_line": "global markets", "side": "sell", "region": ["GLOBAL"], "product": ["rates"],
                 "office": "front"},
    },
    "fx_trading": {
        "a1": [("FX Global Code adherence", "GLOBAL", "FX Global Code (2021) Principle 9")],
        "a2": ("Example G-SIB A", "Annual Report 10-K", 2024, "Fixed Income, Currencies and Commodities markets revenue"),
        "a3": ("BIS", "Triennial Central Bank Survey: FX turnover, daily average", 7.5, "USD trillion", "2022-04"),
        "function": "fx spot and forward trader",
        "headcount": [30, 90], "cost": [220000, 400000], "det": 0.7,
        "tasks": [("price and execute client fx orders", "order ticket, market data, limits",
                   "fill at or better than order limit", "order and execution record"),
                  ("square the end-of-day fx position", "position report, hedge trades", "position within limit",
                   "end-of-day position report"),
                  ("validate trade details against client confirmation", "trade ticket, confirmation",
                   "match or exception", "confirmation matching log")],
        "axis": {"business_line": "global markets", "side": "sell", "region": ["GLOBAL"], "product": ["fx"],
                 "office": "front"},
    },
    "credit_trading": {
        "a1": [("Volcker Rule market-making exemption", "US", "12 CFR Part 248 §248.4(b)")],
        "a2": ("Example G-SIB B", "Annual Report", 2024, "Global Markets — Credit"),
        "a3": ("SIFMA", "US corporate bond average daily trading volume", 45.0, "USD billion", "2024"),
        "function": "credit trader",
        "headcount": [25, 80], "cost": [240000, 420000], "det": 0.65,
        "tasks": [("price a bond enquiry from the desk axe sheet", "enquiry, inventory, axe sheet",
                   "quote given and enquiry closed", "enquiry log and booking"),
                  ("mark end-of-day inventory to independent prices", "inventory, pricing sources",
                   "marks accepted by product control", "price verification report"),
                  ("allocate a block trade across client accounts", "block ticket, allocation instructions",
                   "allocations booked", "allocation record")],
        "axis": {"business_line": "global markets", "side": "sell", "region": ["AMER", "EMEA"], "product": ["credit"],
                 "office": "front"},
    },
    "securities_services": {
        "a1": [("Central securities depository settlement discipline", "EU", "CSDR Art. 7 (Regulation (EU) 909/2014)")],
        "a2": ("Example G-SIB C", "Annual Report 10-K", 2024, "Securities Services revenue"),
        "a3": ("Example G-SIB C", "Assets under custody and administration", 45.0, "USD trillion", "2024-12-31"),
        "function": "custody operations analyst",
        "headcount": [400, 1500], "cost": [150000, 300000], "det": 0.9,
        "tasks": [("process a corporate action election", "event notice, client instruction, holdings",
                   "election submitted by deadline", "corporate action event record"),
                  ("reconcile client holdings to depository records", "holdings ledger, depository statement",
                   "breaks cleared or escalated", "reconciliation break report"),
                  ("settle a client securities instruction", "settlement instruction, cash and stock positions",
                   "instruction settled or failed with reason", "settlement status record")],
        "axis": {"business_line": "securities services", "side": "both", "region": ["GLOBAL"], "product": ["multi"],
                 "office": "back"},
    },
    "collateral_management": {
        "a1": [("Uncleared margin rules", "EU", "EMIR Art. 11 and Delegated Regulation (EU) 2016/2251")],
        "a2": ("Example G-SIB B", "Annual Report", 2024, "Global Markets — Financing and collateral"),
        "a3": ("ISDA", "Margin Survey: initial margin collected by phase-one firms", 1400.0, "USD billion", "2023"),
        "function": "collateral operations analyst",
        "headcount": [80, 300], "cost": [160000, 320000], "det": 0.85,
        "tasks": [("issue a margin call from the exposure calculation", "exposure report, agreement terms",
                   "call issued and agreed or disputed", "margin call record"),
                  ("validate collateral eligibility and haircuts", "collateral schedule, delivered assets",
                   "collateral accepted or rejected", "collateral booking record"),
                  ("resolve a margin dispute", "dispute notice, portfolio reconciliation", "dispute closed",
                   "dispute log")],
        "axis": {"business_line": "global markets", "side": "both", "region": ["GLOBAL"], "product": ["multi"],
                 "office": "middle"},
    },
    "trade_support": {
        "a1": [("Transaction reporting", "EU", "MiFIR Art. 26 (Regulation (EU) 600/2014)")],
        "a2": ("Example G-SIB A", "Annual Report 10-K", 2024, "Markets operating expenses"),
        "a3": ("Example Industry Survey", "Capital markets operations headcount per G-SIB", 6000.0, "seats", "2024"),
        "function": "trade support analyst",
        "headcount": [100, 400], "cost": [150000, 290000], "det": 0.95,
        "tasks": [("book and validate a trade against the front-office blotter", "blotter, booking system",
                   "trade booked and matched", "booking log"),
                  ("clear a trade break between front-office and risk systems", "break report, source tickets",
                   "break cleared", "break resolution record"),
                  ("amend a booking on trader instruction with approval", "amendment request, approval",
                   "amendment applied", "amendment audit trail")],
        "axis": {"business_line": "global markets", "side": "sell", "region": ["GLOBAL"], "product": ["multi"],
                 "office": "middle"},
    },
    "settlements": {
        "a1": [("Settlement discipline regime", "EU", "CSDR Art. 7 (Regulation (EU) 909/2014)"),
               ("T+1 settlement cycle", "US", "SEC Rule 15c6-1")],
        "a2": ("Example G-SIB C", "Annual Report 10-K", 2024, "Securities Services revenue"),
        "a3": ("DTCC", "Average daily settlement value processed", 2.5, "USD trillion", "2024"),
        "function": "settlements analyst",
        "headcount": [150, 600], "cost": [140000, 300000], "det": 0.95,
        "tasks": [("match settlement instructions with counterparty", "instruction, counterparty instruction",
                   "matched or unmatched with reason", "matching status record"),
                  ("resolve a failed settlement", "fail report, positions", "settled or buy-in initiated",
                   "fail resolution record"),
                  ("release a payment against delivery", "settlement instruction, cash position", "payment released",
                   "payment record")],
        "axis": {"business_line": "operations", "side": "sell", "region": ["GLOBAL"], "product": ["multi"],
                 "office": "back"},
    },
    "regulatory_reporting": {
        "a1": [("Derivative transaction reporting", "EU", "EMIR Art. 9 (Regulation (EU) 648/2012)"),
               ("Swap data reporting", "US", "CFTC Regulation Part 45")],
        "a2": ("Example G-SIB B", "Annual Report", 2024, "Operations and technology expense"),
        "a3": ("ESMA", "EMIR trade repository reports received per day", 300.0, "million", "2023"),
        "function": "regulatory reporting analyst",
        "headcount": [60, 250], "cost": [160000, 300000], "det": 0.9,
        "tasks": [("submit daily transaction reports to the repository", "trade population, reference data",
                   "report accepted by repository", "repository acknowledgement"),
                  ("remediate a rejected report", "rejection file, source trade", "resubmitted and accepted",
                   "resubmission log"),
                  ("reconcile reported population to booked trades", "booking system extract, reported extract",
                   "population reconciled", "completeness reconciliation report")],
        "axis": {"business_line": "operations", "side": "sell", "region": ["EMEA", "AMER"], "product": ["multi"],
                 "office": "control"},
    },
    "equities_trading": {
        "a1": [("Best execution", "EU", "MiFID II Art. 27 (Directive 2014/65/EU)")],
        "a2": ("Example G-SIB A", "Annual Report 10-K", 2024, "Equity markets revenue"),
        "a3": ("WFE", "Electronic order book value traded", 120.0, "USD trillion", "2023"),
        "function": "cash equities trader",
        "headcount": [30, 100], "cost": [260000, 460000], "det": 0.6,
        "tasks": [("execute a client order against the best-execution policy", "order, venue data",
                   "order filled within policy", "execution quality report"),
                  ("hedge a facilitation position", "position, risk limits", "position within limit",
                   "end-of-day risk report"),
                  ("confirm allocations with the client", "fill, allocation", "allocation confirmed",
                   "allocation record")],
        "axis": {"business_line": "global markets", "side": "sell", "region": ["GLOBAL"], "product": ["equities"],
                 "office": "front"},
    },
    "commodities_trading": {
        "a1": [("Position limits", "US", "CFTC Regulation Part 150")],
        "a2": ("Example G-SIB A", "Annual Report 10-K", 2024, "Fixed Income, Currencies and Commodities markets revenue"),
        "a3": None,
        "function": "commodities trader",
        "headcount": [15, 50], "cost": [250000, 430000], "det": 0.62,
        "tasks": [("price a client commodity hedge request", "request, forward curve", "quote given",
                   "quote log"),
                  ("manage the desk position against limits", "position report", "position within limit",
                   "end-of-day risk report"),
                  ("confirm trade terms with counterparty", "ticket, confirmation", "matched", "confirmation record")],
        "axis": {"business_line": "global markets", "side": "sell", "region": ["AMER"], "product": ["commodities"],
                 "office": "front"},
    },
    "market_risk_control": {
        "a1": [("Market risk capital", "GLOBAL", "Basel Framework MAR20")],
        "a2": ("Example G-SIB B", "Pillar 3 Report", 2024, "Market risk RWA"),
        "a3": None,
        "function": "market risk controller",
        "headcount": [50, 200], "cost": [180000, 300000], "det": 0.6,
        "tasks": [("validate daily VaR against limits", "VaR report, limits", "breaches escalated",
                   "limit monitoring record"),
                  ("sign off end-of-day risk figures", "risk feed, adjustments", "figures signed", "sign-off log"),
                  ("investigate a backtesting exception", "P&L, VaR", "exception explained", "backtesting record")],
        "axis": {"business_line": "risk", "side": "sell", "region": ["GLOBAL"], "product": ["multi"],
                 "office": "control"},
    },
}

# ---------------------------------------------------------------- vendors (synthetic)
VENDORS = {
    "alpha-lm-1.0": {"vendor": "alphalabs", "names": {
        "rates_trading": "Rates Trading", "fx_trading": "FX Trading", "credit_trading": "Credit Trading",
        "securities_services": "Securities Services", "collateral_management": "Collateral Management",
        "trade_support": "Trade Support", "settlements": "Settlements", "regulatory_reporting": "Regulatory Reporting",
        "equities_trading": "Equities Trading", "market_risk_control": "Market Risk Control"},
        "samples": [
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "trade_support", "settlements", "equities_trading", "market_risk_control"],
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "trade_support", "settlements", "equities_trading", "regulatory_reporting"],
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "settlements", "equities_trading"],
        ],
        "cost_shift": 0, "det_shift": 0.0},
    "beta-reasoner-2": {"vendor": "betamind", "names": {
        "rates_trading": "Interest Rates Trading Desk", "fx_trading": "Foreign Exchange Trading",
        "credit_trading": "Credit Trading Desk", "securities_services": "Securities Services (Custody & Fund Services)",
        "collateral_management": "Collateral Management & Margining", "settlements": "Settlements Operations",
        "regulatory_reporting": "Transaction Regulatory Reporting", "equities_trading": "Cash Equities Trading"},
        "samples": [
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "settlements", "regulatory_reporting", "equities_trading"],
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "settlements", "regulatory_reporting", "equities_trading"],
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "settlements", "regulatory_reporting"],
        ],
        "cost_shift": 10000, "det_shift": 0.02},
    "gamma-analyst-3": {"vendor": "gammaworks", "names": {
        "rates_trading": "Rates Trading", "fx_trading": "FX Trading Desk", "credit_trading": "Flow Credit Trading",
        "collateral_management": "Collateral Management", "trade_support": "Trade Support Middle Office",
        "settlements": "Trade Settlements", "regulatory_reporting": "Regulatory Reporting",
        "market_risk_control": "Market Risk Control"},
        "samples": [
            ["rates_trading", "fx_trading", "credit_trading", "collateral_management", "trade_support",
             "settlements", "regulatory_reporting", "market_risk_control"],
            ["rates_trading", "fx_trading", "credit_trading", "collateral_management", "trade_support",
             "settlements", "regulatory_reporting"],
            ["rates_trading", "fx_trading", "credit_trading", "collateral_management", "trade_support",
             "settlements", "regulatory_reporting", "market_risk_control"],
        ],
        "cost_shift": 8000, "det_shift": -0.01},
    "delta-decomposer-4": {"vendor": "deltaresearch", "names": {
        "rates_trading": "Global Rates Trading", "fx_trading": "FX Trading", "credit_trading": "Credit Trading",
        "securities_services": "Securities Services", "collateral_management": "Collateral Management",
        "trade_support": "Trade Support", "settlements": "Settlements",
        "regulatory_reporting": "Regulatory Reporting", "commodities_trading": "Commodities Trading"},
        "samples": [
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "trade_support", "settlements", "regulatory_reporting", "commodities_trading"],
            ["rates_trading", "fx_trading", "securities_services", "collateral_management", "trade_support",
             "settlements", "regulatory_reporting", "commodities_trading"],
            ["rates_trading", "fx_trading", "credit_trading", "securities_services", "collateral_management",
             "trade_support", "settlements", "regulatory_reporting"],
        ],
        "cost_shift": 5000, "det_shift": 0.01},
}

REJECTED = [
    {"name": "Investment Banking Advisory", "reason_codes": ["R_NOT_CAPITAL_MARKETS"],
     "note": "M&A advisory is not a markets operation."},
    {"name": "Institutional Sales Coverage", "reason_codes": ["R_RELATIONAL_DOMINANT"],
     "note": "Relationship management dominates; few checkable terminal states."},
    {"name": "Client Onboarding", "reason_codes": ["R_SEAT_BELOW_THRESHOLD"],
     "note": "Addressable seat cost below threshold."},
    {"name": "Markets Research", "reason_codes": ["R_TERMINALITY_LT3", "R_UNCERTAIN_CITATIONS"],
     "note": "Fewer than three record-checkable terminal tasks."},
]


def division_obj(key: str, vendor: dict, arith_override: float | None = None,
                 seat_override: tuple[list[int], float] | None = None) -> dict:
    d = DIVS[key]
    lo, hi = d["cost"]
    lo += vendor["cost_shift"]
    hi += vendor["cost_shift"]
    det = round(min(1.0, max(0.0, d["det"] + vendor["det_shift"])), 2)
    if seat_override is not None:
        (lo, hi), det = seat_override
    addr = round(((lo + hi) / 2.0) * det, 2)
    if arith_override is not None:
        addr = arith_override
    a1 = [{"regime": r, "jurisdiction": j, "citation": c} for (r, j, c) in d["a1"]] if d["a1"] else None
    a2 = None
    if d["a2"]:
        b, f, fy, li = d["a2"]
        a2 = [{"bank": b, "filing": f, "fiscal_year": fy, "line_item": li}]
    a3 = None
    if d["a3"]:
        p, s, v, u, asof = d["a3"]
        a3 = [{"publisher": p, "series": s, "value": v, "unit": u, "as_of": asof}]
    tasks = [{"task": t, "input_records": i, "terminal_state": ts, "evidence_record": e}
             for (t, i, ts, e) in d["tasks"]]
    return {
        "a1_regulatory": a1, "a2_segment": a2, "a3_market_size": a3,
        "a4_seat": {"function": d["function"], "headcount_range": d["headcount"], "cost_per_seat": [lo, hi],
                    "cost_source": "Synthetic Compensation Survey 2024 (fictional)",
                    "determinable_fraction": det, "relational_fraction": round(1 - det, 2),
                    "addressable_seat_cost": addr, "terminality": tasks},
        "name": vendor["names"][key],
        "axis": d["axis"],
        "confidence": 0.8,
    }


def response(model: str, idx: int) -> dict:
    v = VENDORS[model]
    divs = []
    for key in v["samples"][idx]:
        override, seat = None, None
        if key == "market_risk_control" and model == "alpha-lm-1.0":
            # model arithmetic wrong by >5% (recomputed 229500) -> ARITH_MISMATCH flagged, still admitted
            override, seat = 260000.0, ([200000, 340000], 0.85)
        if key == "market_risk_control" and model == "gamma-analyst-3":
            override = 210000.0     # model claims above threshold; recomputed 151200 -> demoted server-side
        divs.append(division_obj(key, v, override, seat))
    rej = REJECTED[: 2 + (idx % 3)]
    return {"divisions": divs, "rejected": rej}


def write_fixture(model: str, idx: int, raw: str, note: str) -> None:
    v = VENDORS[model]
    out = {"model_id": model, "vendor": v["vendor"], "response_raw": raw,
           "usage": {"input_tokens": 4200, "output_tokens": len(raw) // 4},
           "params": {"temperature": 0.2, "top_p": 1.0, "max_tokens": 16000, "seed": 1000 + idx},
           "note": note}
    p = HERE / model / f"{idx}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    for model in VENDORS:
        for idx in range(3):
            write_fixture(model, idx, json.dumps(response(model, idx), indent=2), "SYNTHETIC schema-valid response")
    # extra sample 3 for alpha: INVALID (truncated JSON)
    good = json.dumps(response("alpha-lm-1.0", 0), indent=2)
    write_fixture("alpha-lm-1.0", 3, good[: len(good) // 2] + "\n", "SYNTHETIC INVALID response (truncated JSON)")
    # extra sample 3 for beta: schema-valid but contains self-assessment / gap language (I7 -> INVALID by G8)
    obj = response("beta-reasoner-2", 0)
    obj["divisions"][0]["a4_seat"]["cost_source"] = (
        "Synthetic Compensation Survey 2024 (fictional). Note: this division is under-served by tooling and "
        "language models are weak at the reconciliation tasks here.")
    write_fixture("beta-reasoner-2", 3, json.dumps(obj, indent=2), "SYNTHETIC response seeded with self-assessment language")


if __name__ == "__main__":
    main()
