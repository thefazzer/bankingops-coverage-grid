"""End-to-end through the `lat` CLI (click runner, in-process, network-free), plus manifest/anchor behaviour."""
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from lat import manifest as M
from lat.cli import main


@pytest.fixture(scope="module")
def cli_ws(tmp_path_factory):
    root = tmp_path_factory.mktemp("cliws")
    env = {"LAT_VAULT_KEY": "22" * 32}
    runner = CliRunner()

    def run(*args, ok=True):
        r = runner.invoke(main, list(args), env=env, catch_exceptions=False)
        if ok:
            assert r.exit_code == 0, r.output
        return r

    w = ["-w", str(root)]
    run("fixtures", "generate", *w, "--n-docs", "9", "--seed", "5")
    run("vault", "init", *w)
    run("manifest", "build", *w)
    run("redact", *w, "--mode", "pseudonymise")
    run("lineage", "build", *w)
    run("ratios", *w)
    run("canary", "register", *w, "--package-id", "CLI1", "--recipient", "buyer-cli")
    run("holdout", "commit", *w)
    out = run("package", "build", *w, "--package-id", "CLI1", "--recipient", "buyer-cli", "--institutions", "INST-A,INST-B",
              "--period-start", "2024-01-01", "--period-end", "2024-06-30")
    assert "overall: PASS" in out.output
    return {"root": root, "run": run, "env": env, "runner": runner, "pkg": root / "pkg-CLI1"}


def test_cli_buyer_examiner_gates_detect(cli_ws, tmp_path):
    run, pkg, root = cli_ws["run"], cli_ws["pkg"], cli_ws["root"]
    r = run("verify", "--mode", "buyer", "--package", str(pkg))
    assert "V7: PASS" in r.output and "overall: PASS" in r.output
    vb = json.loads((pkg / "verify_buyer.json").read_text())
    assert vb["overall"] == "PASS" and len(vb["checks"]) == 7
    run("keygen", "--out", str(tmp_path / "ex.key"))
    r = run("verify", "--mode", "examiner", "--package", str(pkg), "--vault", str(root / "vault"), "--sample", "25",
            "--seed", "3", "--examiner-key", str(tmp_path / "ex.key"), "--gazetteers", str(root / "gazetteers"))
    assert "E3: PASS" in r.output and "over sample 25 of" in r.output and "(seed 3)" in r.output
    rep = json.loads((pkg / "report.json").read_text())
    assert rep["overall"] == "PASS" and (pkg / "report.json.sig").exists() and (pkg / "report.md").exists()
    r = run("report", "--package", str(pkg))
    assert "# LAT examiner report" in r.output
    r = run("gate", "all", "-w", str(root), "--package", str(pkg))
    assert "G9 HOLDOUT_GATE: PASS" in r.output and json.loads((pkg / "gates_report.json").read_text())["overall"] == "PASS"
    r = run("canary", "detect", str(pkg / "lineage.jsonl"), "--registry", str(root / "canary" / "registry.jsonl"))
    d = json.loads(r.output)
    assert d["detected"] and d["recipient_id"] == "buyer-cli" and d["package_id"] == "CLI1"
    r = run("canary", "detect", str(pkg), "--registry-entry", str(pkg / "canary" / "registry_entry.json"))
    assert json.loads(r.output)["recipient_id"] == "buyer-cli"
    # buyer verify still passes with verifier outputs present in the package dir (no false V7 positives)
    r = run("verify", "--mode", "buyer", "--package", str(pkg))
    assert "overall: PASS" in r.output
    # README-VERIFY carries the exact commands
    readme = (pkg / "README-VERIFY.md").read_text()
    assert f"lat verify --mode buyer --package pkg-CLI1" in readme and "--mode examiner" in readme


def test_cli_tamper_exits_nonzero(cli_ws, tmp_path):
    import shutil
    run, pkg = cli_ws["run"], cli_ws["pkg"]
    bad = tmp_path / "bad"
    shutil.copytree(pkg, bad)
    doc = sorted((bad / "redacted").glob("*.txt"))[0]
    doc.write_bytes(doc.read_bytes().replace(b"the", b"THE", 1))
    r = run("verify", "--mode", "buyer", "--package", str(bad), ok=False)
    assert r.exit_code == 1 and "V2: FAIL" in r.output
    r = run("gate", "all", "-w", str(cli_ws["root"]), "--package", str(bad), ok=False)
    assert r.exit_code == 1 and "G3 MANIFEST_GATE: FAIL" in r.output
    # unregistered recipient cannot get a package (G2)
    r = run("package", "build", "-w", str(cli_ws["root"]), "--package-id", "CLI1", "--recipient", "stranger", ok=False)
    assert r.exit_code != 0 and "G2" in r.output


def test_cli_holdout_reveal_verify(cli_ws, tmp_path):
    run, root, pkg = cli_ws["run"], cli_ws["root"], cli_ws["pkg"]
    reveal = tmp_path / "reveal.json"
    run("holdout", "reveal", "-w", str(root), "--holdout-id", "HOLD-2024Q3", "--out", str(reveal))
    r = run("holdout", "verify", "--commit", str(pkg / "holdout" / "commit.json"), "--reveal", str(reveal))
    assert r.output.startswith("OK")
    d = json.loads(reveal.read_text())
    d["items"][0]["answer"] = "swapped"
    reveal.write_text(json.dumps(d))
    r = run("holdout", "verify", "--commit", str(pkg / "holdout" / "commit.json"), "--reveal", str(reveal), ok=False)
    assert r.exit_code == 1 and "mismatch" in r.output


def test_cli_manifest_verify_and_anchor(cli_ws):
    run, root, pkg = cli_ws["run"], cli_ws["root"], cli_ws["pkg"]
    r = run("manifest", "verify", "--dir", str(pkg))
    assert json.loads(r.output)["ok"] and "STUB" in json.loads(r.output)["anchor"]
    r = run("anchor", "verify", "--dir", str(pkg))
    assert r.output.startswith("OK: STUB")


def test_manifest_supersets_subsets_and_v0_import():
    v0 = M.import_v0(["ab" * 32, "cd" * 32], created_utc="2024-01-01T00:00:00Z", anchor={"chain": "btc", "txid": "x", "block": 1, "ts": "t"})
    assert v0["version"] == 0 and M.verify_manifest(v0, M.manifest_sha(v0))["ok"]
    sup = M.build_manifest(["ab" * 32, "cd" * 32, "ef" * 32], prev=v0)
    assert sup["version"] == 1 and sup["diff_log"] == {"prev_version": 0, "added": ["ef" * 32], "removed": [], "kind": "superset"}
    assert sup["prev_sha"] == M.manifest_sha(v0)
    with pytest.raises(ValueError):
        M.build_manifest(["ab" * 32], prev=sup)
    sub = M.build_manifest(["ab" * 32], prev=sup, allow_subset=True)
    assert sub["diff_log"]["kind"] == "subset" and sorted(sub["diff_log"]["removed"]) == ["cd" * 32, "ef" * 32]
    # tampered sha / root
    assert not M.verify_manifest(dict(sub, merkle_root="00" * 32), M.manifest_sha(sub))["ok"]
    assert "manifest.sha mismatch" in M.verify_manifest(sub, "00" * 32)["problems"]
    # anchor stub binds digest; wrong digest fails
    stub = M.OpenTimestampsStub()
    proof = stub.stamp(bytes.fromhex(sub["merkle_root"]))
    assert proof["status"] == "PENDING_STUB" and stub.verify(bytes.fromhex(sub["merkle_root"]), proof)[0]
    assert not stub.verify(bytes.fromhex(sup["merkle_root"]), proof)[0]
    assert not M.verify_manifest(sub, M.manifest_sha(sub), proof | {"digest": "00" * 32})["ok"]
