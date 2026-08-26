"""`lat` CLI — SPEC-02 §11."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import canary as canary_mod
from . import holdout as holdout_mod
from . import manifest as manifest_mod
from .classes import DATE_POLICIES, Gazetteer
from .crypto import SigningKey
from .encoding import pretty_json
from .gates import GateContext, run_gates
from .lineage import LineageBuildError, build_lineage, check_lineage, load_atoms, read_jsonl, write_jsonl
from .models import MODE_PSEUDONYMISE, MODE_SYNTHESISE
from .package import PackageBuildError, build_package
from .pkgio import Package
from .ratios import compute_ratios, ratios_bytes
from .redact import redact_corpus
from .residual import scan as residual_scan
from .vault import NonceVault, resolve_vault_key
from .verify import examine, render_report_md, verify_buyer
from .workspace import Workspace

ws_opt = click.option("-w", "--workspace", default=".", show_default=True, type=click.Path(), help="seller workspace dir")
key_opt = click.option("--vault-key-file", default=None, type=click.Path(), help="vault key file (else LAT_VAULT_KEY[_FILE])")


def _echo_json(obj):
    click.echo(pretty_json(obj).rstrip())


def _status_exit(overall: str):
    click.echo(f"overall: {overall}")
    if overall != "PASS":
        sys.exit(1)


@click.group()
@click.version_option("0.1.0", prog_name="lat")
def main():
    """Lineage Attestation Toolkit (SPEC-02)."""


# ---------------------------------------------------------------------------------------- keys / vault

@main.command()
@click.option("--out", required=True, type=click.Path(), help="private key file (base64 seed); .pub written alongside")
def keygen(out):
    """Generate an Ed25519 key pair (e.g. for the examiner)."""
    k = SigningKey.generate()
    k.save(out)
    k.public().save(str(out) + ".pub")
    click.echo(f"wrote {out} and {out}.pub")


@main.group()
def vault():
    """Nonce vault (encrypted at rest; never shipped)."""


@vault.command("init")
@ws_opt
@key_opt
def vault_init(workspace, vault_key_file):
    """Create the vault: K_pseud + seller signing key; key file created if absent."""
    ws = Workspace(workspace)
    v = ws.vault(vault_key_file, create=True)
    click.echo(f"vault at {v.path}; seller pubkey {v.path / 'seller.pub'}")


# ---------------------------------------------------------------------------------------- fixtures

@main.group()
def fixtures():
    """Synthetic fixtures (no real data)."""


@fixtures.command("generate")
@ws_opt
@click.option("--n-docs", default=12, show_default=True)
@click.option("--seed", default=1, show_default=True)
@click.option("--n-episodes", default=8, show_default=True)
def fixtures_generate(workspace, n_docs, seed, n_episodes):
    from .fixtures import generate
    _echo_json(generate(workspace, n_docs, seed, n_episodes))


# ---------------------------------------------------------------------------------------- manifest

@main.group()
def manifest():
    """Manifest build / verify / anchor."""


@manifest.command("build")
@ws_opt
@click.option("--prev", type=click.Path(exists=True), default=None, help="previous manifest (superset/subset check)")
@click.option("--allow-subset", is_flag=True)
@click.option("--anchor/--no-anchor", default=True, help="write OpenTimestamps STUB proof")
def manifest_build(workspace, prev, allow_subset, anchor):
    ws = Workspace(workspace)
    docs = ws.docs()
    prev_m = json.loads(Path(prev).read_text()) if prev else None
    m = manifest_mod.build_manifest([d.doc_id for d in docs], prev_m, allow_subset)
    mp, sp = manifest_mod.write_manifest(m, ws.root)
    if anchor:
        manifest_mod.write_anchor(m, ws.root)
    click.echo(f"manifest v{m['version']}: {len(m['docs'])} docs, merkle_root {m['merkle_root'][:16]}…, sha {sp.read_text().strip()[:16]}…")


@manifest.command("verify")
@click.option("--dir", "directory", default=".", type=click.Path(exists=True), help="dir with manifest.json/.sha")
def manifest_verify(directory):
    m, sha = manifest_mod.load_manifest(directory)
    r = manifest_mod.verify_manifest(m, sha, manifest_mod.load_anchor(directory))
    _echo_json(r)
    if not r["ok"]:
        sys.exit(1)


@manifest.command("anchor")
@ws_opt
@click.option("--provider", default="opentimestamps-stub", show_default=True)
def manifest_anchor(workspace, provider):
    """Write an anchor proof (STUB provider only in v0.1: no network)."""
    ws = Workspace(workspace)
    m, _ = manifest_mod.load_manifest(ws.root)
    p = manifest_mod.write_anchor(m, ws.root, provider)
    click.echo(f"wrote {p} (stub; not broadcast)")


@main.group()
def anchor():
    """Anchor proof verification."""


@anchor.command("verify")
@click.option("--dir", "directory", default=".", type=click.Path(exists=True))
def anchor_verify(directory):
    m, _ = manifest_mod.load_manifest(directory)
    proof = manifest_mod.load_anchor(directory)
    if proof is None:
        click.echo("no anchor proof present")
        sys.exit(2)
    ok, info = manifest_mod.get_anchor_provider(proof.get("provider", "")).verify(bytes.fromhex(m["merkle_root"]), proof)
    click.echo(f"{'OK' if ok else 'FAIL'}: {info}")
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------------------- redact

@main.command()
@ws_opt
@key_opt
@click.option("--mode", type=click.Choice(["pseudonymise", "synthesise"]), default="pseudonymise", show_default=True)
@click.option("--docs", multiple=True, help="restrict to these source filenames")
@click.option("--date-policy", type=click.Choice(DATE_POLICIES), default="shift_per_doc_v1", show_default=True)
@click.option("--redact-amounts", is_flag=True, help="redact AMOUNT_EXACT (banded); default keeps amounts (§4)")
def redact(workspace, vault_key_file, mode, docs, date_policy, redact_amounts):
    """Segment + commit + pseudonymise source docs into work/ (vault updated)."""
    ws = Workspace(workspace)
    v = ws.vault(vault_key_file, create=True)
    srcs = ws.docs()
    if docs:
        srcs = [d for d in srcs if d.name in set(docs)]
    m = MODE_PSEUDONYMISE if mode == "pseudonymise" else MODE_SYNTHESISE
    res = redact_corpus(srcs, ws.detector(redact_amounts), v, ws.work, m, date_policy)
    n_red = sum(len(r.entries) for r in res)
    click.echo(f"{len(res)} docs processed in {m} mode; {n_red} REDACT segments; roots.json signed")


# ---------------------------------------------------------------------------------------- lineage / ratios

@main.group()
def lineage():
    """Lineage atoms / episodes."""


@lineage.command("build")
@ws_opt
@key_opt
@click.option("--spec", type=click.Path(exists=True), default=None, help="episodes spec (default source/episodes_spec.json)")
def lineage_build(workspace, vault_key_file, spec):
    ws = Workspace(workspace)
    spec_obj = json.loads(Path(spec).read_text()) if spec else ws.episodes_spec()
    try:
        atoms, episodes = build_lineage(spec_obj, ws.docs(), ws.work, ws.work.load_roots())
    except LineageBuildError as e:
        raise click.ClickException(str(e))
    write_jsonl(ws.work.path / "lineage.jsonl", [a.to_dict() for a in atoms])
    write_jsonl(ws.work.path / "episodes.jsonl", [e.to_dict() for e in episodes])
    ws.vault(vault_key_file).signing_key.sign_file(ws.work.path / "lineage.jsonl")
    r = check_lineage(atoms, episodes, ws.work)
    click.echo(f"{len(atoms)} atoms in {len(episodes)} episodes; self-check {'OK' if r['ok'] else 'FAILED'}")
    if not r["ok"]:
        _echo_json(r)
        sys.exit(1)


@main.command()
@ws_opt
@key_opt
@click.option("--tier-floor", default=0.80, show_default=True)
def ratios(workspace, vault_key_file, tier_floor):
    """Compute ratios.json (canonical JSON) from work/lineage.jsonl and sign it."""
    ws = Workspace(workspace)
    atoms = load_atoms(ws.work.path / "lineage.jsonl")
    (ws.work.path / "ratios.json").write_bytes(ratios_bytes(atoms, tier_floor))
    ws.vault(vault_key_file).signing_key.sign_file(ws.work.path / "ratios.json")
    r = compute_ratios(atoms, tier_floor)
    click.echo(f"tier {r['tier']}; by_bytes pct {r['by_bytes']['pct']}")


# ---------------------------------------------------------------------------------------- canary

@main.group()
def canary():
    """Per-recipient salted canaries."""


@canary.command("register")
@ws_opt
@key_opt
@click.option("--package-id", required=True)
@click.option("--recipient", "recipient_id", required=True)
def canary_register(workspace, vault_key_file, package_id, recipient_id):
    ws = Workspace(workspace)
    atoms = read_jsonl(ws.work.path / "lineage.jsonl")
    if not atoms:
        raise click.ClickException("work/lineage.jsonl missing; run `lat lineage build` first")
    c = canary_mod.new_canary(package_id, recipient_id, atoms, manifest_mod.utc_now())
    try:
        line = ws.registry.append(c, ws.vault(vault_key_file).signing_key)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"registered canary tag {line['entry']['tag']} for {package_id}/{recipient_id} ({len(c.positions)} carriers)")


@canary.command("apply")
@ws_opt
@click.option("--package-id", required=True)
@click.option("--recipient", "recipient_id", required=True)
@click.option("--in", "in_path", type=click.Path(exists=True), default=None, help="lineage.jsonl (default work/)")
@click.option("--out", "out_path", type=click.Path(), required=True)
def canary_apply(workspace, package_id, recipient_id, in_path, out_path):
    ws = Workspace(workspace)
    line = ws.registry.find(package_id, recipient_id)
    if line is None:
        raise click.ClickException("no registered canary; run `lat canary register`")
    atoms = read_jsonl(in_path or ws.work.path / "lineage.jsonl")
    write_jsonl(out_path, canary_mod.apply_canary(atoms, canary_mod.Canary.from_dict(line["entry"])))
    click.echo(f"wrote {out_path}")


@canary.command("detect")
@click.argument("path", type=click.Path(exists=True))
@click.option("--registry", "registry_path", type=click.Path(exists=True), default=None)
@click.option("--registry-entry", type=click.Path(exists=True), default=None, help="a package's registry_entry.json")
def canary_detect(path, registry_path, registry_entry):
    """Recover recipient from >=3 surviving carriers in FILE or directory."""
    reg = canary_mod.Registry(registry_path) if registry_path else None
    r = canary_mod.detect_path(path, reg)
    if r.detected and registry_entry and not r.recipient_id:
        e = json.loads(Path(registry_entry).read_text())["entry"]
        if e["tag"] == r.tag:
            r.recipient_id, r.package_id = e["recipient_id"], e["package_id"]
    _echo_json(r.to_dict())
    if not r.detected:
        sys.exit(1)


# ---------------------------------------------------------------------------------------- holdout

@main.group()
def holdout():
    """Sealed holdout commit / reveal / verify."""


@holdout.command("commit")
@ws_opt
@key_opt
@click.option("--items", type=click.Path(exists=True), default=None, help="default source/holdout_items.json")
def holdout_commit(workspace, vault_key_file, items):
    ws = Workspace(workspace)
    obj = json.loads(Path(items or ws.source / "holdout_items.json").read_text(encoding="utf-8"))
    public, secret = holdout_mod.make_commit(obj["holdout_id"], obj["items"])
    ws.vault(vault_key_file, create=True).save_holdout(obj["holdout_id"], secret)
    p = holdout_mod.write_commit(public, ws.holdout_dir)
    click.echo(f"holdout {obj['holdout_id']}: {public['n_items']} items committed {public['items_commit'][:16]}… -> {p}")


@holdout.command("reveal")
@ws_opt
@key_opt
@click.option("--holdout-id", required=True)
@click.option("--out", "out_path", type=click.Path(), required=True)
def holdout_reveal(workspace, vault_key_file, holdout_id, out_path):
    ws = Workspace(workspace)
    sec = ws.vault(vault_key_file).load_holdout(holdout_id)
    if sec is None:
        raise click.ClickException("no such holdout in vault")
    Path(out_path).write_text(pretty_json({"holdout_id": holdout_id, "nonce_h": sec["nonce_h"], "items": sec["items"]}))
    click.echo(f"wrote {out_path} (items+answers+nonce_h: distribute only after evaluation closes)")


@holdout.command("verify")
@click.option("--commit", "commit_path", type=click.Path(exists=True), required=True)
@click.option("--reveal", "reveal_path", type=click.Path(exists=True), required=True)
def holdout_verify(commit_path, reveal_path):
    ok, msg = holdout_mod.verify_reveal(holdout_mod.load_commit(commit_path), json.loads(Path(reveal_path).read_text()))
    click.echo(f"{'OK' if ok else 'FAIL'}: {msg}")
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------------------- verify / report / gates

@main.command()
@click.option("--mode", type=click.Choice(["buyer", "examiner"]), required=True)
@click.option("--package", "package_path", type=click.Path(exists=True), required=True)
@click.option("--vault", "vault_path", type=click.Path(), default=None, help="vault dir (examiner)")
@key_opt
@click.option("--sample", type=int, default=None, help="examiner: sample N commitments (default all)")
@click.option("--seed", type=int, default=0, show_default=True)
@click.option("--examiner-key", type=click.Path(exists=True), default=None, help="examiner Ed25519 key (lat keygen)")
@click.option("--examiner-id", default="examiner", show_default=True)
@click.option("--gazetteers", type=click.Path(exists=True), default=None, help="gazetteer dir for E3/E6 predicates")
@click.option("--out", "out_dir", type=click.Path(), default=None, help="output dir (default: package dir)")
def verify(mode, package_path, vault_path, vault_key_file, sample, seed, examiner_key, examiner_id, gazetteers, out_dir):
    """Buyer (V1–V7, no vault) or examiner (E1–E7, with vault) verification."""
    if mode == "buyer":
        r = verify_buyer(package_path, Path(out_dir) / "verify_buyer.json" if out_dir else None)
        for c in r["checks"]:
            click.echo(f"{c['id']}: {c['status']}")
        _status_exit(r["overall"])
        return
    if not vault_path:
        raise click.ClickException("--vault required in examiner mode")
    key = resolve_vault_key(vault_key_file, Path(vault_path).parent)
    v = NonceVault(vault_path, key)
    gaz = Gazetteer.load(gazetteers) if gazetteers else None
    ek = SigningKey.load(examiner_key) if examiner_key else None
    r = examine(package_path, v, sample, seed, gaz, ek, out_dir, examiner_id)
    for c in r["checks"]:
        click.echo(f"{c['id']}: {c['status']}")
    click.echo(r["statement"])
    _status_exit(r["overall"])


@main.command()
@click.option("--package", "package_path", type=click.Path(exists=True), required=True)
def report(package_path):
    """Re-render report.md from an examiner report.json in the package dir."""
    p = Path(package_path) / "report.json"
    if not p.exists():
        raise click.ClickException("report.json not found; run `lat verify --mode examiner` first")
    md = render_report_md(json.loads(p.read_text(encoding="utf-8")))
    (Path(package_path) / "report.md").write_text(md, encoding="utf-8")
    click.echo(md)


@main.group()
def gate():
    """Runnable gates G1–G9."""


@gate.command("all")
@ws_opt
@key_opt
@click.option("--package", "package_path", type=click.Path(exists=True), required=True)
@click.option("--redact-amounts", is_flag=True, help="must match the flag used at redact time (G8)")
def gate_all(workspace, vault_key_file, package_path, redact_amounts):
    ws = Workspace(workspace)
    v = ws.vault(vault_key_file)
    ctx = GateContext(vault=v, source_docs=ws.docs(), registry=ws.registry, audit_log=ws.audit_log(),
                      gazetteer=ws.gazetteer(), detector=ws.detector(redact_amounts))
    r = run_gates(package_path, ctx, write=True)
    for g in r["gates"]:
        click.echo(f"{g['id']} {g['name']}: {g['status']}")
    _status_exit(r["overall"])


@main.group()
def residual():
    """Residual scan (§7, heuristic)."""


@residual.command("scan")
@ws_opt
@click.option("--package", "package_path", type=click.Path(exists=True), default=None, help="default: work/")
def residual_scan_cmd(workspace, package_path):
    ws = Workspace(workspace)
    pkg = Package(package_path) if package_path else Package(ws.work.path)
    eps = pkg.episodes() if pkg.exists("episodes.jsonl") else None
    rs = residual_scan(pkg, ws.gazetteer(), ws.detector(), eps, holdout_commit=pkg.holdout_commit())
    _echo_json(rs.to_dict())


# ---------------------------------------------------------------------------------------- package

@main.group()
def package():
    """Package build (§9)."""


@package.command("build")
@ws_opt
@key_opt
@click.option("--package-id", required=True)
@click.option("--recipient", "recipient_id", required=True)
@click.option("--marketed-tier", type=click.Choice(["VERIFIED", "MIXED"]), default="VERIFIED", show_default=True)
@click.option("--institutions", default=None, help="comma-separated declared institutions (default: from vault origins)")
@click.option("--period-start", default=None)
@click.option("--period-end", default=None)
@click.option("--out", "out_dir", type=click.Path(), default=None)
@click.option("--redact-amounts", is_flag=True, help="must match the flag used at redact time (G8)")
def package_build(workspace, vault_key_file, package_id, recipient_id, marketed_tier, institutions, period_start,
                  period_end, out_dir, redact_amounts):
    ws = Workspace(workspace)
    v = ws.vault(vault_key_file)
    scope = None
    if institutions or period_start or period_end:
        scope = {"institutions": [s.strip() for s in (institutions or "").split(",") if s.strip()],
                 "period_start": period_start or "", "period_end": period_end or ""}
    try:
        out, rep = build_package(ws, package_id, recipient_id, v, marketed_tier, scope,
                                 Path(out_dir) if out_dir else None, True, redact_amounts)
    except PackageBuildError as e:
        raise click.ClickException(str(e))
    click.echo(f"package written to {out}")
    for g in rep["gates"]:
        click.echo(f"{g['id']} {g['name']}: {g['status']}")
    _status_exit(rep["overall"])


if __name__ == "__main__":
    main()
