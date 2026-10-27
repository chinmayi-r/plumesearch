"""Smoke tests for plume.py. Run: python -m pytest tests/ -q"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from plume import FilamentPlume, PlumeParams


def test_puffs_move_downwind_and_get_culled():
    pl = FilamentPlume(PlumeParams(seed=1, meander_std=0.0, puff_noise_std=0.0))
    pl.step(int(2.0 / pl.p.dt))
    assert len(pl.state.age) > 0
    # With no noise every puff sits on the centerline, moved downwind by age*wind.
    assert np.allclose(pl.state.xy[:, 1], 0.0)
    assert np.allclose(pl.state.xy[:, 0], pl.state.age * pl.p.wind_speed, atol=1e-6)
    pl.step(int(60.0 / pl.p.dt))
    assert pl.state.xy[:, 0].max() <= pl.p.domain[1]


def test_concentration_is_intermittent_downwind():
    pl = FilamentPlume(PlumeParams(seed=0))
    pl.warmup(40.0)
    xy = np.array([4.0, 0.0])
    trace = np.array([(pl.step(), pl.concentration(xy))[1] for _ in range(int(120 / pl.p.dt))])
    frac = (trace > pl.p.detect_threshold).mean()
    # A real plume: whiffs are rare but present, and there are long zero stretches.
    assert 0.02 < frac < 0.5, frac
    assert (trace < 1e-3).mean() > 0.2  # smooth-cone bug gave 0.0


def test_concentration_shapes():
    pl = FilamentPlume(PlumeParams(seed=0))
    pl.warmup(5.0)
    assert np.ndim(pl.concentration(np.array([1.0, 0.0]))) == 0
    assert pl.concentration(np.zeros((7, 2))).shape == (7,)
    X, Y, C = pl.concentration_grid(nx=30, ny=10)
    assert C.shape == (10, 30) and (C >= 0).all()
