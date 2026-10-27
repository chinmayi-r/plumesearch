"""
plume.py: a 2D filament (puff) model of a turbulent odor plume.

Why this model
--------------
Real turbulent plumes are intermittent: an agent downwind sees nothing for
seconds, then a burst of odor, then nothing again. Grid-based diffusion models
smear that out into a smooth cone and make search look much easier than it is.
The filament model (Farrell, Murlis, Long, Li, Carde 2002, "Filament-based
atmospheric dispersion model to achieve short time-scale structure of odor
plumes") keeps the intermittency by representing the plume as many discrete
puffs that each wander with the wind. Singh, van Breugel, Rao and Brunton
(2023, Nature Machine Intelligence) trained their plume-tracking agents on a
simulator of this type. This file is an independent implementation of the
model as described, not their code.

The model
---------
A source at `source_xy` releases puffs as a Poisson process with rate
`release_rate` (puffs per second). Each puff carries a fixed amount of odor
and has a radius that grows with age. Every puff moves each step by

    dx = (wind_u + noise_u) * dt
    dy = (wind_v + noise_v) * dt

where (wind_u, wind_v) is the mean wind plus a meander term, and the noise is
a per-puff random walk with std `puff_noise_std * sqrt(dt)` that spreads the
plume into a cone. The meander term is a crosswind velocity shared by all
puffs that follows an Ornstein-Uhlenbeck process with std `meander_std` and
correlation time `meander_tau`:

    dv_m = -(v_m / tau) dt + std * sqrt(2 dt / tau) * N(0, 1)

Without it the centerline sensor never leaves the plume (first version of
this file: whiff fraction 100%). With it the plume snakes and a fixed sensor
sees bursts separated by gaps of seconds, which is the intermittency the
one-clock policies are built around. Puff radius grows as

    r(t)^2 = r0^2 + 2 * D * t

(diffusive growth; D is `puff_growth`). Puffs are 3D Gaussian blobs and the
sensor plane is z = 0 through their centers, so the concentration at a point is

    c(p) = sum_i (q / ((2 pi)^1.5 r_i^3)) * exp(-|p - x_i|^2 / (2 r_i^2))

The r^3 (not r^2) matters: it is what makes old puffs fade, so that far from
the source the sensor sees sharp bursts separated by near-zero gaps rather
than a smooth cone. An earlier 2D version of this file produced a plume with
no gaps at all, which would have made every search policy look better than
it is.

Puffs older than `max_age` or outside `domain` are removed.

Coordinates
-----------
x is downwind for a wind blowing in +x. y is crosswind. Units are meters and
seconds. Nothing here knows about the agent; see sensor.py for turning a
concentration into a whiff event, and agent.py for moving in the plume.

Run this file directly to render a snapshot and an intermittency trace:

    python plume.py --out plume_demo.png
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np


@dataclass
class PlumeParams:
    source_xy: tuple[float, float] = (0.0, 0.0)
    domain: tuple[float, float, float, float] = (-1.0, 10.0, -5.0, 5.0)  # xmin, xmax, ymin, ymax
    wind_speed: float = 0.5          # m/s, mean wind magnitude (Singh et al. used 0.5)
    wind_angle: float = 0.0          # rad, direction the wind blows toward (0 = +x)
    release_rate: float = 5.0        # puffs per second
    puff_q: float = 1.0              # odor amount per puff (arbitrary units)
    puff_r0: float = 0.03            # m, initial puff radius
    puff_growth: float = 0.002       # m^2/s, D in r^2 = r0^2 + 2 D t
    puff_noise_std: float = 0.15     # m/s^0.5, per-puff random-walk strength
    meander_std: float = 0.25        # m/s, std of the shared crosswind meander velocity
    meander_tau: float = 3.0         # s, correlation time of the meander
    detect_threshold: float = 3.0    # concentration above which a sensor reports a whiff
    max_age: float = 60.0            # s, drop puffs older than this
    dt: float = 0.05                 # s, internal time step
    seed: int = 0


@dataclass
class PlumeState:
    """Arrays of live puffs. Kept separate from params so it can be saved/reset."""
    xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    age: np.ndarray = field(default_factory=lambda: np.zeros(0))
    t: float = 0.0


class FilamentPlume:
    """Stateful plume simulator. Call step() to advance, concentration() to sample."""

    def __init__(self, params: PlumeParams | None = None):
        self.p = params or PlumeParams()
        self.rng = np.random.default_rng(self.p.seed)
        self.state = PlumeState()
        self.meander_v = 0.0  # current shared crosswind meander velocity (m/s)
        self.set_wind(self.p.wind_speed, self.p.wind_angle)

    # ---- wind -----------------------------------------------------------
    def set_wind(self, speed: float, angle: float) -> None:
        """Change the mean wind. Angle is the direction the wind blows toward."""
        self.wind_speed = float(speed)
        self.wind_angle = float(angle)
        self.wind_uv = np.array([speed * np.cos(angle), speed * np.sin(angle)])

    # ---- dynamics -------------------------------------------------------
    def step(self, n_steps: int = 1) -> None:
        for _ in range(n_steps):
            self._step_once()

    def current_wind(self) -> np.ndarray:
        """Mean wind plus the instantaneous meander, as a 2D velocity (m/s)."""
        # Meander is crosswind: perpendicular to the mean wind direction.
        perp = np.array([-np.sin(self.wind_angle), np.cos(self.wind_angle)])
        return self.wind_uv + self.meander_v * perp

    def _step_once(self) -> None:
        p, s, dt = self.p, self.state, self.p.dt

        # 0. Advance the meander (Ornstein-Uhlenbeck).
        if p.meander_std > 0:
            self.meander_v += (-(self.meander_v / p.meander_tau) * dt
                               + p.meander_std * np.sqrt(2.0 * dt / p.meander_tau) * self.rng.normal())
        wind_now = self.current_wind()

        # 1. Release new puffs. Poisson with mean release_rate*dt; small dt so
        #    we draw the count directly rather than carrying fractions.
        n_new = self.rng.poisson(p.release_rate * dt)
        if n_new > 0:
            # Spread new puffs uniformly over the step so release is not bursty
            # at the step clock. They start at the source plus one partial
            # advection step.
            frac = self.rng.uniform(0.0, 1.0, size=n_new)
            new_xy = np.asarray(p.source_xy)[None, :] + wind_now[None, :] * (frac * dt)[:, None]
            s.xy = np.vstack([s.xy, new_xy])
            s.age = np.concatenate([s.age, frac * dt])

        if len(s.age) == 0:
            s.t += dt
            return

        # 2. Advect by mean wind plus per-puff random walk.
        noise = self.rng.normal(0.0, p.puff_noise_std * np.sqrt(dt), size=s.xy.shape)
        s.xy = s.xy + (wind_now[None, :] * dt) + noise
        s.age = s.age + dt
        s.t += dt

        # 3. Cull puffs that left the domain or got too old.
        xmin, xmax, ymin, ymax = p.domain
        keep = (
            (s.xy[:, 0] >= xmin) & (s.xy[:, 0] <= xmax)
            & (s.xy[:, 1] >= ymin) & (s.xy[:, 1] <= ymax)
            & (s.age <= p.max_age)
        )
        if not keep.all():
            s.xy = s.xy[keep]
            s.age = s.age[keep]

    # ---- sampling -------------------------------------------------------
    def radii(self) -> np.ndarray:
        return np.sqrt(self.p.puff_r0 ** 2 + 2.0 * self.p.puff_growth * self.state.age)

    def concentration(self, points: np.ndarray) -> np.ndarray:
        """
        Concentration at one or many points.

        points: shape (2,) or (N, 2). Returns shape () or (N,).
        Cost is O(N * n_puffs); fine for a handful of sensors, use
        concentration_grid for images.
        """
        pts = np.atleast_2d(np.asarray(points, dtype=float))
        if len(self.state.age) == 0:
            out = np.zeros(len(pts))
            return out[0] if np.ndim(points) == 1 else out
        r = self.radii()                                          # (P,)
        r2 = r ** 2
        d2 = ((pts[:, None, :] - self.state.xy[None, :, :]) ** 2).sum(-1)  # (N, P)
        norm = self.p.puff_q / ((2.0 * np.pi) ** 1.5 * r ** 3)   # 3D Gaussian peak
        c = norm[None, :] * np.exp(-d2 / (2.0 * r2)[None, :])
        out = c.sum(axis=1)
        return out[0] if np.ndim(points) == 1 else out

    def concentration_grid(self, nx: int = 220, ny: int = 120) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Concentration on a regular grid over the domain, for plotting. Returns (X, Y, C)."""
        xmin, xmax, ymin, ymax = self.p.domain
        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        X, Y = np.meshgrid(xs, ys)
        pts = np.stack([X.ravel(), Y.ravel()], axis=1)
        # Chunk to bound memory: (N, P) can be large.
        C = np.empty(len(pts))
        for i in range(0, len(pts), 4096):
            C[i:i + 4096] = self.concentration(pts[i:i + 4096])
        return X, Y, C.reshape(ny, nx)

    def warmup(self, seconds: float) -> None:
        """Run the plume with no observer until it has filled the domain."""
        self.step(int(round(seconds / self.p.dt)))


# -------------------------------------------------------------------------
# Demo / smoke test
# -------------------------------------------------------------------------
def _demo(out_path: str, seed: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plume = FilamentPlume(PlumeParams(seed=seed))
    plume.warmup(40.0)  # ~ domain length / wind speed (10 m / 0.5 m/s) + margin

    # Snapshot
    X, Y, C = plume.concentration_grid()

    # Intermittency trace: a fixed sensor 4 m downwind on the centerline,
    # sampled every step for 60 s.
    sensor_xy = np.array([4.0, 0.0])
    n = int(60.0 / plume.p.dt)
    trace = np.empty(n)
    for i in range(n):
        plume.step()
        trace[i] = plume.concentration(sensor_xy)
    t = np.arange(n) * plume.p.dt
    thresh = plume.p.detect_threshold
    above = trace > thresh
    frac_detect = float(above.mean())
    # Lengths of gaps between whiffs, the statistic the one-clock policies live on.
    gaps, run = [], 0
    for a in above:
        if a:
            if run:
                gaps.append(run * plume.p.dt)
            run = 0
        else:
            run += 1
    gaps = np.array(gaps) if gaps else np.array([0.0])

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [2, 1]})
    ax = axes[0]
    ax.pcolormesh(X, Y, np.log10(C + 1e-6), shading="auto", cmap="magma", vmin=-3, vmax=np.log10(thresh) + 1.5)
    ax.contour(X, Y, C, levels=[thresh], colors="cyan", linewidths=0.6)
    ax.plot(*plume.p.source_xy, "c*", ms=14, label="source")
    ax.plot(*sensor_xy, "wo", ms=8, mfc="none", label="fixed sensor")
    ax.set_aspect("equal")
    ax.set_xlabel("x (m), downwind")
    ax.set_ylabel("y (m)")
    ax.set_title(f"Filament plume, log10 concentration, t={plume.state.t:.0f}s, {len(plume.state.age)} puffs, wind {plume.p.wind_speed} m/s")
    ax.legend(loc="upper right")

    ax = axes[1]
    ax.plot(t, trace, lw=0.8)
    ax.axhline(thresh, color="r", lw=0.8, ls="--",
               label=f"whiff threshold {thresh}; whiff {100*frac_detect:.0f}% of time; median gap {np.median(gaps):.1f}s, max gap {gaps.max():.1f}s")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("concentration at sensor")
    ax.set_title("Intermittency at the fixed sensor: this is what the agent has to work with")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)
    print(f"saved {out_path}; puffs alive={len(plume.state.age)}; sensor mean={trace.mean():.3g}, max={trace.max():.3g}; "
          f"whiff fraction={frac_detect:.2f}; median gap={np.median(gaps):.2f}s; max gap={gaps.max():.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="plume_demo.png")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    _demo(args.out, args.seed)
