"""SPEC-02 §11 fixtures — synthetic banking-operations documents (emails / chat / notes).

Everything here is invented: names, counterparties, systems, ids, IBAN-like strings, e-mails
(.test TLD), phone numbers (+000 prefix). No real data, no real institutions.
"""
from __future__ import annotations

import datetime as _dt
import json
import random
from pathlib import Path

from .classes import Gazetteer
from .encoding import pretty_json
from .ner import RuleDetector

FIRST = ["Marta", "Tobias", "Ingrid", "Ravi", "Selin", "Kwame", "Anouk", "Dmitri", "Priya", "Lars", "Yara", "Oskar",
         "Nadia", "Emeka", "Sofie", "Hiro"]
LAST = ["Kowalczyk", "Brenner", "Solheim", "Natarajan", "Aydin", "Mensah", "Verhoeven", "Petrov", "Raghavan", "Lindqvist",
        "Haddad", "Nyström", "Farouk", "Okafor", "Dahl", "Tanaka"]
COUNTERPARTIES = ["Norvale Capital", "Brightmoor Securities", "Kestrel Ridge Bank", "Halvard Trading", "Silvermere Partners",
                  "Quillon Asset Management", "Tarnwick Global Markets", "Orrin & Vale"]
CLIENTS = ["Pellucid Pension Fund", "Ambergate Family Office", "Corvid Logistics Treasury", "Meridale Insurance",
           "Thornbury Endowment"]
SYSTEMS = ["TRADEHUB", "SETTLR", "OMS-FALCON", "RECON-9", "LEDGERLINE", "MARGINVIEW"]
LOCATIONS = ["Port Ellery", "Vanmoor", "Castlebridge", "Harrowgate Quay", "Lindenhall"]
PRODUCTS = ["FX forward", "interest rate swap", "cross-currency swap", "repo", "equity block", "credit default swap",
            "FX spot", "bond forward"]
VENUES = ["Aurelia Exchange", "Northgate MTF", "Ceres OTC", "Ridgeway Clearing"]
ALLOWLIST = ["Trade Support", "Middle Office", "Back Office", "Kind Regards", "Best Regards", "Settlement Date",
             "Value Date", "Trade Date", "Operations Team", "Please Confirm", "Standing Settlement Instructions",
             "Net Settlement", "Reference Data", "Confirmation Status", "Position Control", "Cash Management",
             "Collateral Desk", "Margin Call", "Payment Investigation", "Sanctions Screening", "Trade Capture"]
CCY = ["USD", "EUR", "GBP", "CHF"]
INSTITUTIONS = ["INST-A", "INST-B"]

CLEAN_SENTENCES = [
    "please confirm the booking once the reconciliation break has been cleared.",
    "the break is a timing difference and will roll off at the next batch.",
    "we still need the signed confirmation before the cut-off this afternoon.",
    "settlement instructions were amended after the counterparty updated its standing details.",
    "the position control team has flagged a residual balance on the omnibus account.",
    "this needs a four-eyes check before release; the second approver is out until tomorrow.",
    "the fail is on their side according to the custodian, so no interest claim from us.",
    "we escalated the aged item to the supervisor as per the operations procedure.",
    "the payment was returned by the beneficiary bank because of an incomplete purpose code.",
    "margin was called this morning and the collateral pledge is pending acceptance.",
    "please treat as urgent; the client has asked for a status update by close of business.",
    "the affirmation was rejected because the notional did not match the term sheet.",
]


def _name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _date(rng, base: _dt.date):
    d = base + _dt.timedelta(days=rng.randint(0, 150))
    fmt = rng.choice(["%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y", "%d %b %Y"])
    return d.strftime(fmt)


def _amount(rng):
    v = rng.choice([12500, 250000, 1750000, 8000000, 42000000, 95000])
    return rng.choice([f"{rng.choice(CCY)} {v:,.2f}", f"{v/1e6:.1f}m {rng.choice(CCY)}", f"{rng.choice(['$','€','£'])}{v:,}"])


def _ids(rng):
    return {"trade": f"TRD-2024-{rng.randint(10000, 99999)}", "acct": f"ACC-{rng.randint(100000, 999999)}",
            "iban": f"XX{rng.randint(10, 99)} FAKE {rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(10, 99)}",
            "email": f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}@{rng.choice(['examplebank', 'fakecorp', 'testfund'])}.test",
            "phone": f"+000 {rng.randint(100, 999)} {rng.randint(1000, 9999)} {rng.randint(100, 999)}"}


def _entity_sentences(rng, base):
    ids = _ids(rng)
    p, cp, cl, sy, lo, pr, ve = (_name(rng), rng.choice(COUNTERPARTIES), rng.choice(CLIENTS), rng.choice(SYSTEMS),
                                 rng.choice(LOCATIONS), rng.choice(PRODUCTS), rng.choice(VENUES))
    return [
        f"{p} confirmed that {cp} will settle {ids['trade']} on {_date(rng, base)}.",
        f"the {pr} with {cp} for {_amount(rng)} was booked in {sy} on {_date(rng, base)}.",
        f"client {cl} asked to move the cash to account {ids['acct']} ({ids['iban']}).",
        f"please reach {p} at {ids['email']} or {ids['phone']} regarding the {pr} executed on {ve}.",
        f"the {lo} branch of {cp} sent revised settlement details for value date {_date(rng, base)}.",
        f"{sy} shows the trade as pending; {p} will chase {cl} tomorrow.",
    ]


def _doc(rng, kind: str, base: _dt.date) -> str:
    author, to = _name(rng), _name(rng)
    ent = _entity_sentences(rng, base)
    clean = rng.sample(CLEAN_SENTENCES, 4)
    body = [rng.choice(ent), clean[0], rng.choice(ent), clean[1], rng.choice(ent), clean[2], clean[3]]
    if kind == "email":
        return (f"From: {author}\nTo: {to}\nSubject: settlement query {rng.choice(SYSTEMS)} / {rng.choice(PRODUCTS)}\n\n"
                f"Hi {to.split()[0]},\n\n" + "\n".join(s[0].upper() + s[1:] for s in body[:4]) +
                f"\n\nKind Regards,\n{author}\n{rng.choice(['Middle Office', 'Trade Support', 'Back Office'])}\n")
    if kind == "chat":
        lines = []
        for i, s in enumerate(body):
            who = author if i % 2 == 0 else to
            lines.append(f"[{rng.randint(8, 17):02d}:{rng.randint(0, 59):02d}] {who}: {s}")
        return "\n".join(lines) + "\n"
    return (f"Operations note — {rng.choice(['fails review', 'break investigation', 'onboarding check'])}\n"
            f"Author: {author}\n\n" + "\n".join(f"- {s[0].upper() + s[1:]}" for s in body) + "\n")


def build_gazetteer() -> Gazetteer:
    return Gazetteer(set(COUNTERPARTIES), set(CLIENTS), set(SYSTEMS), set(LOCATIONS),
                     {f"{f} {l}" for f in FIRST for l in LAST} | set(FIRST), set(ALLOWLIST), set(PRODUCTS), set(VENUES))


def generate(out: str | Path, n_docs: int = 12, seed: int = 1, n_episodes: int = 8, n_holdout: int = 5) -> dict:
    """Write source/docs, origins.json, gazetteers, episodes_spec.json, holdout_items.json, audit_log.json."""
    rng = random.Random(seed)
    out = Path(out)
    docs_dir = out / "source" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    gaz = build_gazetteer()
    gaz.save(out / "gazetteers")
    detector = RuleDetector(gaz)
    base = _dt.date(2024, 1, 8)
    origins, texts = {}, {}
    for i in range(n_docs):
        kind = ["email", "chat", "note"][i % 3]
        name = f"doc-{i:03d}-{kind}.txt"
        text = _doc(rng, kind, base)
        (docs_dir / name).write_text(text, encoding="utf-8")
        texts[name] = text
        origins[name] = {"institution_code": INSTITUTIONS[i % 2], "period_start": "2024-01-01", "period_end": "2024-06-30",
                         "channel": kind}
    (out / "source" / "origins.json").write_text(pretty_json(origins), encoding="utf-8")

    # episodes: QUOTE spans in detection-free regions, PSEUDONYMISE spans over entity-bearing lines
    episodes = []
    names = sorted(texts)
    for e in range(n_episodes):
        name = names[e % len(names)]
        text = texts[name]
        dets = detector.detect(text)
        lines, pos = [], 0
        for ln in text.split("\n"):
            lines.append((pos, pos + len(ln), ln))
            pos += len(ln) + 1
        clean = [(s, t) for s, t, ln in lines if len(ln) > 30 and not any(d.start < t and d.end > s for d in dets)]
        dirty = [(s, t) for s, t, ln in lines if len(ln) > 30 and any(d.start < t and d.end > s for d in dets)]
        atoms = []
        for s, t in clean[:3]:
            atoms.append({"op": "QUOTE", "doc": name, "start": s, "end": t})
        for s, t in dirty[:3]:
            atoms.append({"op": "PSEUDONYMISE", "doc": name, "start": s, "end": t})
        atoms.append({"op": "PARAPHRASE", "content": "Analyst asked the counterparty to confirm the amended instructions."})
        if e % 3 == 0:
            atoms.append({"op": "SYNTHESISE", "content": "Synthetic guidance: escalate fails older than five days."})
        episodes.append({"episode_id": f"ep-{e:04d}", "task_id": f"task-{e % 4:02d}",
                         "task_text": f"Resolve the settlement break described in the thread and state the next action ({e})."
                                      f" {rng.choice(CLEAN_SENTENCES)}",
                         "trace_ref": f"traces/ep-{e:04d}.json", "verifier_ref": "verifiers/settlement-v1", "atoms": atoms})
    (out / "source" / "episodes_spec.json").write_text(pretty_json({"episodes": episodes}), encoding="utf-8")

    holdout = {"holdout_id": "HOLD-2024Q3", "items": [
        {"item_id": f"HITEM-{i:04d}",
         "task_text": f"Holdout task {i}: identify the root cause of the returned payment and propose the correction. "
                      f"{rng.choice(CLEAN_SENTENCES)} {rng.choice(CLEAN_SENTENCES)}",
         "answer": f"Answer {i}: purpose code missing; resend with corrected code.", "source_doc_ids": []}
        for i in range(n_holdout)]}
    (out / "source" / "holdout_items.json").write_text(pretty_json(holdout), encoding="utf-8")
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    audit = [{"event": "corpus_imported", "ts": (now - _dt.timedelta(days=2)).isoformat().replace("+00:00", "Z")},
             {"event": "external_review", "ts": (now + _dt.timedelta(days=30)).isoformat().replace("+00:00", "Z"),
              "note": "scheduled buyer-counsel review (synthetic)"}]
    (out / "source" / "audit_log.json").write_text(pretty_json(audit), encoding="utf-8")
    return {"docs": len(texts), "episodes": len(episodes), "holdout_items": n_holdout}
