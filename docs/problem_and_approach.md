# Problem and approach

## The problem

An odor source somewhere in a room with moving air. A small drone has to find it using a gas sensor and knowledge of the mean wind direction, with no map and no position information available to the controller.

This is hard because smell in moving air does not fade smoothly with distance. Turbulence tears the plume into filaments, so a sensor downwind reads nothing most of the time, then a brief burst, then nothing again. Consecutive readings carry no usable gradient. What does carry information is the statistics of the bursts and gaps over time, which depend on where the sensor is relative to the source.

## The controller

Rando, Heinonen, Qi and Seminara (2026, arXiv 2605.15938) train a tabular Q-learning agent whose entire internal state is a clock: the number of time steps since the last odor detection. The state space is 500 clock values; the action space is four moves defined relative to the mean wind (upwind, downwind, crosswind left, crosswind right). The policy is a 500 × 4 table. Trained in direct numerical simulations of turbulent channel flow, the agent learns a recovery behavior of upwind surge, crosswind casting and a delayed downwind return, and outperforms a tuned cast-and-surge heuristic across four plume sparsity levels. Piro, Carbone, Biferale and Cencini (2026, arXiv 2605.21329) extend the same agent with an onboard wind-direction estimate.

Both papers are simulation studies. The authors note that a mean-wind assumption is unrealistic for robots and that compressed-memory controllers may be sufficient for plume tracking, but no hardware implementation is reported in either paper. A search of arXiv for olfactory, turbulent, reinforcement learning and quadrotor (October 2026) returned one hardware paper, France et al. 2026 ("Chasing Ghosts", arXiv 2602.19577), which flies a different, hand-designed controller.

## What this project does

Implement the clock-state agent, reproduce the published simulation results, characterize how the policy degrades under realistic sensor dynamics, and fly it on a small quadrotor against the same baselines used in the paper.

Version 1 fixes the wind direction with a stationary fan, which matches the known-mean-wind setting of Rando et al. Wind estimation (Piro et al.) is treated as a later extension and studied in simulation only.

## Training environments

Two environments, used for different purposes.

**Direct numerical simulation data (primary).** The concentration field published with Rando et al. (Zenodo record 20001730): 2598 frames on a 123 × 27 grid, a 10× spatial downsample of a channel-flow DNS at about 0.4 m/s agent speed and 0.15 s per frame. This is real turbulence and is the environment the published numbers come from. It is used to reproduce those numbers and as the primary training set for the hardware policy. Sparsity, sensor response time and the control tick are all applied on top of the concentration trace, so they can be studied here. Its limits are a single wind speed and domain, a 6.5 minute record that training loops over, and no velocity field.

**Filament plume simulator (secondary).** An independent implementation of the puff-based dispersion model of Farrell et al. 2002, with Poisson puff release, per-puff random walk, diffusive puff growth, a 3D Gaussian concentration kernel and a shared crosswind meander following an Ornstein-Uhlenbeck process. It reproduces the qualitative intermittency of turbulent plumes (fixed-sensor whiff fraction 11 to 34%, median gap about 1 s, maximum gaps 10 to 30 s at the default parameters) and allows wind speed, domain size and source strength to be varied. It is used to check that a policy trained on the DNS record is not specific to that record, and to test conditions the record cannot represent. Its parameters are set by hand and have not yet been calibrated against published plume statistics; see `plume_model.md`.

## Evaluation

Three controllers on identical trials: the learned table, a cast-and-surge baseline implemented as in Rando et al. Algorithm 1 with its one angle parameter tuned per environment, and a random walk as a floor. Metrics follow the paper: success fraction within the horizon, normalized arrival time, and cumulative reward. In simulation these are swept against sensor response time and detection threshold. On hardware, position is recorded by an overhead camera and a fiducial marker for scoring only; the controller never sees it.

## Hardware plan (version 1)

- Quadrotor: DJI Tello or equivalent sub-100 g platform controlled from a laptop.
- Odor: one metal-oxide gas sensor on a small microcontroller, reporting at about 1 Hz.
- Wind: stationary fan, so the upwind direction is a fixed heading.
- Source: ethanol diffuser.
- Scoring: ceiling camera and printed marker.

Two prior projects have each flown one half of this sensor set on the same drone class: France et al. 2026 with gas sensors and no wind sensing, and Thomas, Bridges and Bergbreiter 2026 (arXiv 2601.15607) with a single flow sensor and no gas sensor. Neither flew a learned policy.

## References

- Rando, Heinonen, Qi, Seminara. Clock-state olfactory search in turbulent flows using Q-learning. arXiv 2605.15938, 2026.
- Rando, James, Verri, Rosasco, Seminara. Q-learning with temporal memory to navigate turbulence. eLife 102906 / arXiv 2404.17495, 2025.
- Piro, Carbone, Biferale, Cencini. Smart strategies to navigate turbulent odor plumes reorienting to local wind. arXiv 2605.21329, 2026.
- France, Daescu, Khan, Peddi. Chasing Ghosts: a simulation-to-real olfactory navigation stack. arXiv 2602.19577, 2026.
- Thomas, Bridges, Bergbreiter. Airflow source seeking on small quadrotors using a single flow sensor. arXiv 2601.15607, 2026.
- Farrell, Murlis, Long, Li, Cardé. Filament-based atmospheric dispersion model to achieve short time-scale structure of odor plumes. Environmental Fluid Mechanics, 2002.
