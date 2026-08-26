"""Shared fixtures: an honest, fully built workspace + §9 package on synthetic data (network-free)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from lat import canary as canary_mod
from lat import holdout as holdout_mod
from lat import manifest as manifest_mod
from lat.crypto import SigningKey
from lat.fixtures import generate
from lat.lineage import build_lineage, write_jsonl
from lat.package import build_package
from lat.ratios import ratios_bytes
from lat.lineage import load_atoms
from lat.redact import redact_corpus
from lat.workspace import Workspace

VAULT_KEY_HEX = "11" * 32


def build_workspace(root: Path, n_docs: int = 10, seed: int = 1, package_id: str = "PKG1", recipient: str = "buyer-one",
                    detector=None, register_canary: bool = True, build_pkg: bool = True):
    """Run the whole seller pipeline via the library API. Returns (ws, vault, pkg_path)."""
    root.mkdir(parents=True, exist_ok=True)
    generate(root, n_docs=n_docs, seed=seed)
    ws = Workspace(root)
    key_file = root / "vault.key"
    key_file.write_text(VAULT_KEY_HEX + "\n")
    vault = ws.vault(str(key_file), create=True)
    docs = ws.docs()
    m = manifest_mod.build_manifest([d.doc_id for d in docs])
    manifest_mod.write_manifest(m, ws.root)
    manifest_mod.write_anchor(m, ws.root)
    det = detector or ws.detector()
    redact_corpus(docs, det, vault, ws.work)
    atoms, episodes = build_lineage(ws.episodes_spec(), docs, ws.work, ws.work.load_roots())
    write_jsonl(ws.work.path / "lineage.jsonl", [a.to_dict() for a in atoms])
    write_jsonl(ws.work.path / "episodes.jsonl", [e.to_dict() for e in episodes])
    vault.signing_key.sign_file(ws.work.path / "lineage.jsonl")
    (ws.work.path / "ratios.json").write_bytes(ratios_bytes(load_atoms(ws.work.path / "lineage.jsonl")))
    vault.signing_key.sign_file(ws.work.path / "ratios.json")
    items = json.loads((ws.source / "holdout_items.json").read_text())
    public, secret = holdout_mod.make_commit(items["holdout_id"], items["items"])
    vault.save_holdout(items["holdout_id"], secret)
    holdout_mod.write_commit(public, ws.holdout_dir)
    if register_canary:
        from lat.lineage import read_jsonl
        c = canary_mod.new_canary(package_id, recipient, read_jsonl(ws.work.path / "lineage.jsonl"), manifest_mod.utc_now())
        ws.registry.append(c, vault.signing_key)
    pkg = None
    if build_pkg:
        pkg, _ = build_package(ws, package_id, recipient, vault, run_gate_checks=False)
    return ws, vault, pkg


@pytest.fixture(scope="session")
def honest(tmp_path_factory):
    root = tmp_path_factory.mktemp("honest")
    ws, vault, pkg = build_workspace(root)
    return {"ws": ws, "vault": vault, "pkg": pkg, "root": root}


@pytest.fixture
def pkg_copy(honest, tmp_path):
    """A fresh mutable copy of the honest package for tamper tests."""
    dst = tmp_path / "pkg-copy"
    shutil.copytree(honest["pkg"], dst)
    return dst


@pytest.fixture(scope="session")
def examiner_key():
    return SigningKey.generate()
