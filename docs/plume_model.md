# 01. plume.py

What it is: a 2D filament plume (Farrell et al. 2002 family), the same model class Singh et al. 2023 trained on. Puffs released by a Poisson process, advected by wind, per-puff random walk, radius grows diffusively, 3D Gaussian kernel sampled in the sensor plane.

Two things that went wrong on the way, kept here because they are the kind of mistake that silently makes a search policy look good:

1. 2D kernel (q / 2 pi r^2) and release rate 20/s: old puffs never faded and overlapped along the axis. Fixed sensor at 4 m downwind: whiff 100% of the time, no gaps. A search agent in that plume just climbs the gradient.
2. 3D kernel but no meander: still 100%. Arithmetic: puffs 6 cm apart along the axis, radius 18 cm at 4 m, so they always overlap on the centerline. Real centerline intermittency comes from the whole plume snaking sideways, not from per-puff jitter.

Fix: shared Ornstein-Uhlenbeck crosswind meander (std 0.25 m/s, tau 3 s) plus release 5/s. Fixed sensor now: whiff 11-34% of the time depending on seed, median gap ~1 s, max gaps 10-30 s. That is the regime the one-clock policies are designed for.

Open: parameters are hand-set to look plausible, not fit to data. Before results go in a writeup, calibrate against a published plume statistic (whiff duration and blank duration distributions in Celani, Villermaux, Vergassola 2014, or the DNS data from Piro et al. if they share it).
