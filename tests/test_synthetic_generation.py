"""Synthetic generator (docs/DELIVERY_PLAN.md Commit 4, ADR-0003)."""

import json
import random

import pytest

from pucv_aq_qc.identity import rut
from pucv_aq_qc.privacy import forbidden
from pucv_aq_qc.synthetic import generate_world, persist_world
from pucv_aq_qc.synthetic.rut_generator import generate_unique_ruts
from pucv_aq_qc.synthetic.scenarios import Scenario, ScenarioConfig

SECRET = b"s" * 32


def test_generated_ruts_are_valid_and_unique():
    rng = random.Random(1)
    ruts = list(generate_unique_ruts(200, rng))
    assert len(ruts) == 200
    assert len(set(ruts)) == 200
    for r in ruts:
        assert rut.validate(r) is True


def test_generation_is_deterministic_under_seed():
    a = generate_world(secret=SECRET, n_subjects=20, seed=7)
    b = generate_world(secret=SECRET, n_subjects=20, seed=7)
    assert [s.person_uid_global for s in a.subjects] == [s.person_uid_global for s in b.subjects]
    assert [m.value for m in a.qc_measurements] == [m.value for m in b.qc_measurements]


def test_different_seed_differs():
    a = generate_world(secret=SECRET, n_subjects=20, seed=7)
    b = generate_world(secret=SECRET, n_subjects=20, seed=8)
    assert [s.person_uid_global for s in a.subjects] != [s.person_uid_global for s in b.subjects]


def test_world_has_expected_shape():
    world = generate_world(secret=SECRET, n_subjects=30, seed=3)
    counts = world.counts()
    assert counts["subjects"] == 30
    assert counts["samples"] >= 30
    assert counts["results"] > 0
    assert counts["qc_measurements"] > 0
    # every subject carries a puid pseudonym, none carries a rut-shaped attr
    for subj in world.subjects:
        assert subj.person_uid_global.startswith("puid_")


def test_no_raw_rut_in_generated_objects():
    world = generate_world(secret=SECRET, n_subjects=40, seed=5)
    # serialize everything the generator produced and scan it
    payload = {
        "subjects": [s.model_dump(mode="json") for s in world.subjects],
        "study_subjects": [s.model_dump(mode="json") for s in world.study_subjects],
        "samples": [s.model_dump(mode="json") for s in world.samples],
        "results": [r.model_dump(mode="json") for r in world.results],
        "qc": [m.model_dump(mode="json") for m in world.qc_measurements],
    }
    blob = json.dumps(payload)
    matches = forbidden.scan_text(blob)
    assert matches == [], [m.redacted for m in matches]
    # no model has a 'rut' attribute at all
    assert not hasattr(world.subjects[0], "rut")


def test_scenarios_inject_faults_that_move_qc_off_target():
    # With bias/outliers enabled, the flagged analytes show points well off target.
    world = generate_world(secret=SECRET, n_subjects=10, seed=11)
    glucose_l1 = [
        m for m in world.qc_measurements if m.analyte_code == "glucose" and m.control_level == "L1"
    ]
    # bias is injected on glucose L1: mean of z should be clearly shifted
    zs = [(m.value - m.target_mean) / m.target_sd for m in glucose_l1]
    assert sum(zs) / len(zs) > 1.0  # systematic positive shift present


def test_missing_scenario_produces_missing_values():
    cfg = ScenarioConfig(enabled={Scenario.missing}, missing_rate=0.5)
    world = generate_world(secret=SECRET, n_subjects=40, seed=2, scenarios=cfg)
    missing = [r for r in world.results if r.value is None]
    assert missing, "expected some missing analyte values"
    assert all("missing" in r.result_flags for r in missing)


def test_persist_world_writes_no_rut_to_db(tmp_path):
    from pucv_aq_qc.database.init_db import init_db
    from pucv_aq_qc.database.session import session_scope

    url = f"sqlite:///{tmp_path}/synth.db"
    init_db(url)
    world = generate_world(secret=SECRET, n_subjects=25, seed=9)
    with session_scope(url) as s:
        persist_world(world, s)

    # scan the raw sqlite file for RUT-shaped patterns
    matches = forbidden.scan_paths([tmp_path])
    assert matches == [], [m.redacted for m in matches]


@pytest.mark.parametrize("n", [1, 5, 50])
def test_various_sizes(n):
    world = generate_world(secret=SECRET, n_subjects=n, seed=n)
    assert world.counts()["subjects"] == n
