"""MICRODUCK_TOTAL_MASS_KG rescales the model without touching its contract."""

import mujoco
import numpy as np
import pytest

import mjlab_microduck.tasks  # noqa: F401
from mjlab_microduck.robot import microduck_constants as mc

# NOTE: `mjlab_microduck.tasks` must be imported before `microduck_constants`.
# `mjlab/__init__` auto-loads the `mjlab.tasks` entry point, which imports the
# task package; if `microduck_constants` is the process's FIRST mjlab-touching
# import, that load hits a partially-initialized module, warns, and leaves the
# task registry empty for the rest of the session (breaks every registry test).


def _raw_walk_model():
    return mujoco.MjSpec.from_file(str(mc.MICRODUCK_WALK_XML)).compile()


def test_unset_is_upstream_bit_for_bit(monkeypatch):
    monkeypatch.delenv(mc.MASS_CALIBRATION_ENV_VAR, raising=False)
    assert mc.total_mass_kg() is None
    model = mc.get_walk_spec().compile()
    reference = _raw_walk_model()
    np.testing.assert_array_equal(model.body_mass, reference.body_mass)
    np.testing.assert_array_equal(model.body_inertia, reference.body_inertia)
    assert model.body_mass.sum() == pytest.approx(0.7372, abs=1e-4)


def test_scale_hits_target_mass_and_preserves_shape(monkeypatch):
    monkeypatch.setenv(mc.MASS_CALIBRATION_ENV_VAR, "0.850")
    model = mc.get_walk_spec().compile()
    reference = _raw_walk_model()
    assert model.body_mass.sum() == pytest.approx(0.850, abs=1e-6)
    # Uniform scale: every body's mass and inertia share one ratio.
    mask = reference.body_mass > 0.0
    ratio = model.body_mass[mask] / reference.body_mass[mask]
    np.testing.assert_allclose(ratio, ratio[0], rtol=1e-9)
    np.testing.assert_allclose(
        model.body_inertia[mask], reference.body_inertia[mask] * ratio[0], rtol=1e-9
    )
    np.testing.assert_array_equal(model.body_mass[~mask], reference.body_mass[~mask])
    # CoM / body frames are untouched.
    np.testing.assert_array_equal(
        model.body_ipos, reference.body_ipos
    )


def test_scale_does_not_change_the_policy_contract(monkeypatch):
    monkeypatch.setenv(mc.MASS_CALIBRATION_ENV_VAR, "0.850")
    model = mc.get_walk_spec().compile()
    assert model.nu == 14
    servo_joints = [
        model.joint(i).name
        for i in range(model.njnt)
        if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE
        and not model.joint(i).name.startswith("passive_")
    ]
    assert servo_joints == [
        "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle",
        "neck_pitch", "head_pitch", "head_yaw", "head_roll",
        "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle",
    ]


def test_backlash_and_allcollisions_variants_are_scaled(monkeypatch):
    for getter in (
        mc.get_standup_spec,
        mc.get_backlash_spec,
        mc.get_walk_backlash_spec,
        mc.get_rollers_backlash_spec,
    ):
        monkeypatch.delenv(mc.MASS_CALIBRATION_ENV_VAR, raising=False)
        before = getter().compile().body_mass.sum()
        monkeypatch.setenv(mc.MASS_CALIBRATION_ENV_VAR, "0.850")
        assert getter().compile().body_mass.sum() == pytest.approx(0.850, abs=1e-6)
        assert before != pytest.approx(0.850, abs=1e-6)


def test_ball_prop_is_never_rescaled(monkeypatch):
    monkeypatch.setenv(mc.MASS_CALIBRATION_ENV_VAR, "0.850")
    assert mc.get_ball_spec().compile().body_mass.sum() == pytest.approx(0.015, abs=1e-9)


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number", " "])
def test_bad_values_are_rejected(monkeypatch, value):
    monkeypatch.setenv(mc.MASS_CALIBRATION_ENV_VAR, value)
    if not value.strip():
        assert mc.total_mass_kg() is None
        return
    with pytest.raises(ValueError):
        mc.total_mass_kg()
