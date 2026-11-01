# Engineering challenges and how each is being handled

The simulation agent assumes an instant, exact odor reading every tick, a known mean wind, a point agent moving one grid cell per step on a plane, and an episode that ends when the agent enters a source circle. None of these hold on hardware. This document lists each gap between the simulation and a flying drone, what is known about it, and the plan for closing or bounding it. Status is updated as work proceeds.

## 1. Gas sensor response time

**Gap.** Metal-oxide sensors heat a bead and read its resistance. Reported behavior is a rise over roughly a second and a recovery over several seconds. The clock-state policy assumes a crisp whiff/no-whiff signal every tick; a slow sensor merges puffs that arrive within its recovery time, and the clock then undercounts blanks.

**What is known.** France et al. 2026 flew the MICS-6814 at 1 Hz sampling and found an ethanol source in every trial, so the sensor is adequate for some search method. Its response and recovery time in flight have not been published.

**Plan.**
- Bench test first: step exposure to ethanol vapor, logged at 10 Hz, repeated, to measure rise time, recovery time and noise. This is the first hardware task and gates the rest.
- Define a whiff on the rising edge of the signal (rate of change above a threshold) rather than on its level. Onset is sharp even when recovery is slow.
- Model the measured response as a filter in simulation and train the table with that filter in the loop, so the policy is learned for the sensor it will actually use.
- Match the control tick to the sensor's resolvable event rate and retrain at that tick.
- Sweep the response time in simulation to produce a degradation curve for each controller. The hardware result then sits as one point on a known curve.
- If the measured response is too slow for any of the above, faster sensor classes exist (photoionization detectors) at higher cost and weight.

**Status.** Open. Parts not yet ordered.

## 2. Detection threshold and plume sparsity

**Gap.** In the papers, plume sparsity is set by the detection threshold, and a table trained at one sparsity generalizes poorly to another (Rando et al. 2026, Fig. 4). On hardware, the threshold is a choice made against the sensor's noise floor and the room's actual plume.

**Plan.** Record fixed-position sensor traces in the test room before any flights, compute the whiff fraction and blank-length distribution at candidate thresholds, and choose the threshold that places the room in the sparsity band the table was trained for. Report the measured room statistics alongside flight results.

**Status.** Open.

## 3. Time step and spatial step

**Gap.** In the DNS record one step is 0.15 s and one cell is about 6 cm. On the drone, the sensor sets the tick (about 1 s) and the flight controller sets how far the drone moves per command.

**Plan.** Retrain in simulation at the hardware tick by subsampling the DNS frames and moving the agent the corresponding number of cells per decision. Verify the retrained table's success rate before flying it.

**Status.** Open.

## 4. Wind direction

**Gap.** The policy's actions are defined relative to the mean wind. Measuring wind from a hovering quadrotor is difficult: rotor downwash is often stronger than the ambient flow, and Thomas et al. 2026 report about 20° error and a minimum detectable flow speed with a dedicated fin sensor.

**Plan for version 1.** Use a stationary fan so the upwind direction is a fixed heading. The drone holds that heading using its own attitude estimate, checked against the overhead camera between trials. This removes wind estimation from the hardware experiment and matches the known-mean-wind setting of Rando et al.

**Later.** Piro et al.'s exponentially filtered wind estimate studied in simulation; on hardware, either a flow sensor or an estimate from the drone's lean angle. Both are outside the version 1 scope.

**Status.** Decided for version 1.

## 5. Termination

**Gap.** The simulation episode ends when the agent enters a source region of radius 2 cells. The table has no stop action, and the drone has no position.

**Plan.** Candidate stop rules: a concentration threshold; the maximum-concentration confidence estimator used by France et al. 2026; or termination by the scoring camera (acceptable for measuring time-to-source, but then the controller is not deciding on its own). The choice will be stated with the results.

**Status.** Open.

## 6. Altitude

**Gap.** The policy is two-dimensional. A real plume has vertical structure.

**Plan.** Hold a fixed altitude at the plume centreline height using the drone's barometric hold, and state this as a limitation. The 2D assumption is inherited from the source paper.

**Status.** Decided.

## 7. Starting position

**Gap.** The agent must start where it will eventually detect odor; the stimulus-response strategy has no behavior for a region with no odor information (Rando et al. 2025, Discussion). The published training distribution is uniform over cells that ever exceed the sparsest threshold.

**Plan.** Choose start positions inside the plume's envelope as measured in task 2, and report them.

**Status.** Open.

## 8. Position for scoring

**Gap.** Trials need time-to-source and trajectories. France et al. 2026 report that inertial odometry on the Tello became unusable once the sensor payload biased the IMU.

**Plan.** Overhead webcam and a printed fiducial marker on the drone. Used for scoring only; never fed to the controller.

**Status.** Decided.

## 9. Trial throughput

**Gap.** Each trial needs the plume to develop and the room to be vented afterwards. France et al. 2026 ran five trials per configuration for this reason.

**Plan.** Treat the simulation sweep as the primary quantitative result and the flights as confirmation of selected points, with a trial count fixed in advance. Budget flight time accordingly.

**Status.** Planned.

## 10. Transfer between environments

**Gap.** A table trained on one DNS record may be specific to it. The record is 6.5 minutes long and training loops over it.

**Plan.** Evaluate every trained table in both environments (DNS record and filament simulator) and report both. A policy that only works in the environment it was trained in is reported as such.

**Status.** Planned.
