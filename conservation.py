"""C.1 Conservation Constraints -- Domain-conditional physics enforcement.

Enforces physical conservation laws (energy, momentum, mass/continuity) on
operator atlases. Conservation constraints are active for physics domains
(turbulence, adsb, radar, combustion, atmosphere, vessel, airframe) and
deactivated for non-physics domains (har, geology, civic).

HAR was empirically shown to have conservation constraints destroy transfer
effectiveness (0.061 vs 0.330 for F.1-only), so it is explicitly excluded.

Signal format:
    (T, C) -- single signal, T timesteps, C channels
    (N, T, C) -- batch of N signals

Pure numpy module -- no PyTorch dependency.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ===== Inlined config + registry (originally from operator_discovery/core/config.py) =====
# Cloned from operator_discovery/modules/conservation.py and adapted for Markets
# standalone use (removed sys.path hack, inlined ConservationConfig +
# DOMAIN_REQUIRES_CONSERVATION).
@dataclass
class ConservationConfig:
    """C.1 Conservation Constraints config (inlined for Markets standalone)."""
    operator_dim: int = 69
    energy_tolerance: float = 0.05
    momentum_tolerance: float = 0.05
    mass_tolerance: float = 0.01
    mode: str = "project"
    projection_strength: float = 0.9
    active_domains: List[str] = field(default_factory=lambda: [
        "turbulence", "adsb", "radar", "combustion", "atmosphere",
        "vessel", "airframe",
    ])
    inactive_domains: List[str] = field(default_factory=lambda: [
        "har", "geology", "civic",
    ])
    dt: float = 0.02
    data_dir: str = r"E:\operator_discovery\data"
    results_dir: str = r"E:\operator_discovery\results\conservation"


# Maps domain name to whether it requires conservation enforcement.
# Derived from DOMAIN_REGISTRY in operator_discovery/core/config.py.
DOMAIN_REQUIRES_CONSERVATION: Dict[str, bool] = {
    "har": False,
    "turbulence": True,
    "adsb": True,
    "geology": False,
    "radar": True,
    "combustion": True,
    "civic": False,
    "atmosphere": True,
    "vessel": True,
    "airframe": True,
}


# =============================================
#  DOMAIN CHANNEL SEMANTICS
# =============================================

# Maps domain name to which channels contain velocity/speed/amplitude data
# and what integration mode to use for computing kinetic energy.
#
# Modes:
#   "velocity"     -- channels ARE velocity components, KE = 0.5 * sum(v^2)
#   "speed"        -- channels ARE scalar speed, KE = 0.5 * sum(s^2)
#   "amplitude"    -- channels are signal amplitudes, energy = sum(a^2)
#   "acceleration" -- channels are acceleration, integrate via cumsum to get velocity

CHANNEL_SEMANTICS = {
    "turbulence": {"velocity_channels": [0, 1, 2], "mode": "velocity"},      # u, v, w ARE velocity
    "adsb":       {"velocity_channels": [3, 4, 5], "mode": "velocity"},      # vx, vy, vz
    "radar":      {"velocity_channels": [0, 1],    "mode": "amplitude"},     # I, Q (energy = I^2+Q^2)
    "combustion": {"velocity_channels": [5, 6, 7], "mode": "velocity"},      # u, v, w
    "atmosphere": {"velocity_channels": [3, 4, 5], "mode": "velocity"},      # u, v, w
    "vessel":     {"velocity_channels": [2],       "mode": "speed"},         # SOG is speed
    "airframe":   {"velocity_channels": [3],       "mode": "speed",          # mach is speed proxy
                   "accel_channels": [11, 12]},                               # ax_g, az_g
}

# Default fallback: treat first 3 channels as velocity (backward compat)
_DEFAULT_SEMANTICS = {"velocity_channels": [0, 1, 2], "mode": "velocity"}


def _get_channel_config(domain: str) -> dict:
    """Look up channel semantics for a domain, with fallback."""
    return CHANNEL_SEMANTICS.get(domain.lower().strip(), _DEFAULT_SEMANTICS)


# =============================================
#  ENERGY CONSTRAINT
# =============================================

class EnergyConstraint:
    """Kinetic energy conservation check and projection.

    Computes KE based on domain-specific channel semantics:
      - velocity mode: KE = 0.5 * sum(v^2) directly from velocity channels
      - speed mode:    KE = 0.5 * sum(s^2) from scalar speed channels
      - amplitude mode: energy = sum(a^2) from amplitude channels (I/Q)
      - acceleration mode: integrate via cumsum then KE = 0.5 * sum(v^2)
    """

    def __init__(
        self,
        tolerance: float = 0.05,
        channel_config: Optional[dict] = None,
    ) -> None:
        self.tolerance = tolerance
        self._cfg = channel_config or _DEFAULT_SEMANTICS
        self._vel_ch = self._cfg["velocity_channels"]
        self._mode = self._cfg["mode"]
        self._accel_ch = self._cfg.get("accel_channels", None)

    def _velocity(self, signal: np.ndarray, dt: float) -> np.ndarray:
        """Extract or compute velocity-like quantity for energy computation.

        Parameters
        ----------
        signal : np.ndarray
            Shape (..., T, C).
        dt : float
            Sampling interval in seconds.

        Returns
        -------
        np.ndarray
            Velocity-like array, shape (..., T, len(channels)).
        """
        if self._mode == "velocity":
            # Channels ARE velocity -- extract directly
            return signal[..., self._vel_ch]

        elif self._mode == "speed":
            # Channels ARE scalar speed -- extract directly
            return signal[..., self._vel_ch]

        elif self._mode == "amplitude":
            # Channels are signal amplitudes (I, Q) -- energy from sum of squares
            return signal[..., self._vel_ch]

        elif self._mode == "acceleration":
            # Integrate acceleration channels via cumulative sum
            accel = signal[..., self._vel_ch]
            velocity = np.cumsum(accel, axis=-2) * dt
            return velocity

        else:
            raise ValueError(f"Unknown channel mode '{self._mode}'")

    @staticmethod
    def _kinetic_energy(velocity: np.ndarray, mode: str) -> np.ndarray:
        """Compute total KE-like quantity from velocity/amplitude array.

        Parameters
        ----------
        velocity : np.ndarray
            Shape (..., T, n_channels).
        mode : str
            Channel mode determining the energy formula.

        Returns
        -------
        np.ndarray
            Scalar energy per sample (shape matches leading dims, or scalar).
        """
        if mode == "amplitude":
            # Energy = sum(a^2) -- no 0.5 factor for signal energy
            return np.sum(velocity ** 2, axis=(-2, -1))
        else:
            # KE = 0.5 * sum(v^2) for velocity, speed, acceleration modes
            return 0.5 * np.sum(velocity ** 2, axis=(-2, -1))

    def check(
        self,
        signal_before: np.ndarray,
        signal_after: np.ndarray,
        dt: float = 0.02,
    ) -> dict:
        """Check energy conservation between two signal states.

        Parameters
        ----------
        signal_before : np.ndarray
            Reference signal, shape (T, C) or (N, T, C).
        signal_after : np.ndarray
            Transformed signal, same shape as signal_before.
        dt : float
            Sampling interval.

        Returns
        -------
        dict
            'satisfied' : bool -- within tolerance
            'violation' : float -- relative energy change (unsigned)
            'energy_before' : float -- total KE before
            'energy_after' : float -- total KE after
        """
        vel_before = self._velocity(signal_before, dt)
        vel_after = self._velocity(signal_after, dt)

        ke_before_raw = self._kinetic_energy(vel_before, self._mode)
        ke_after_raw = self._kinetic_energy(vel_after, self._mode)

        # Aggregate across batch dimension if present
        ke_before = float(np.sum(ke_before_raw))
        ke_after = float(np.sum(ke_after_raw))

        if ke_before == 0.0:
            violation = 0.0 if ke_after == 0.0 else float("inf")
        else:
            violation = abs(ke_after - ke_before) / abs(ke_before)

        return {
            "constraint": "energy",
            "satisfied": violation <= self.tolerance,
            "violation": violation,
            "energy_before": ke_before,
            "energy_after": ke_after,
        }

    def project(
        self,
        signal: np.ndarray,
        reference: np.ndarray,
        strength: float = 0.9,
        dt: float = 0.02,
    ) -> np.ndarray:
        """Project signal to satisfy energy conservation.

        Scales only the relevant velocity/speed/amplitude channels so that
        the resulting kinetic energy matches the reference energy within
        tolerance. Non-velocity channels are left untouched.

        Parameters
        ----------
        signal : np.ndarray
            Signal to correct, shape (T, C) or (N, T, C).
        reference : np.ndarray
            Reference signal whose energy should be matched.
        strength : float
            Blending factor in [0, 1].
        dt : float
            Sampling interval.

        Returns
        -------
        np.ndarray
            Corrected signal with same shape as input.
        """
        vel_sig = self._velocity(signal, dt)
        vel_ref = self._velocity(reference, dt)

        ke_sig = self._kinetic_energy(vel_sig, self._mode)
        ke_ref = self._kinetic_energy(vel_ref, self._mode)

        # Avoid division by zero
        if np.all(ke_sig == 0.0):
            return signal.copy()

        # Compute per-sample scale factor: sqrt(KE_ref / KE_sig)
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = np.where(
                ke_sig > 0.0,
                np.sqrt(np.maximum(ke_ref, 0.0) / ke_sig),
                1.0,
            )

        # Reshape scale for broadcasting with (..., T, C)
        if signal.ndim == 3:
            scale = scale.reshape(-1, 1, 1)
        elif signal.ndim == 2:
            # scale is a scalar, expand to (1, 1) for broadcasting
            scale = np.atleast_1d(scale).reshape(1, 1)

        # Only scale the relevant channels, leave others unchanged
        result = signal.copy()
        channels = self._vel_ch
        corrected_ch = signal[..., channels] * scale
        blended_ch = signal[..., channels] + strength * (corrected_ch - signal[..., channels])
        result[..., channels] = blended_ch

        return result


# =============================================
#  MOMENTUM CONSTRAINT
# =============================================

class MomentumConstraint:
    """Net momentum conservation check and projection.

    Momentum computation is domain-aware:
      - velocity mode: momentum = sum(v * dt) over time (impulse from velocity)
      - speed mode: momentum = sum(s * dt) over time (scalar impulse)
      - amplitude mode: momentum = sum(a * dt) over time per channel
      - acceleration mode: momentum = sum(accel * dt) over time (net impulse)
    """

    def __init__(
        self,
        tolerance: float = 0.05,
        channel_config: Optional[dict] = None,
    ) -> None:
        self.tolerance = tolerance
        self._cfg = channel_config or _DEFAULT_SEMANTICS
        self._vel_ch = self._cfg["velocity_channels"]
        self._mode = self._cfg["mode"]

    def _net_momentum(self, signal: np.ndarray, dt: float) -> np.ndarray:
        """Compute net momentum (impulse) from domain-appropriate channels.

        Parameters
        ----------
        signal : np.ndarray
            Shape (..., T, C).
        dt : float
            Sampling interval.

        Returns
        -------
        np.ndarray
            Shape (..., n_channels) -- net momentum per channel.
        """
        data = signal[..., self._vel_ch]
        # Integrate: sum(data * dt) over time axis
        momentum = np.sum(data, axis=-2) * dt
        return momentum

    def check(
        self,
        signal_before: np.ndarray,
        signal_after: np.ndarray,
        dt: float = 0.02,
    ) -> dict:
        """Check momentum conservation between two signal states.

        Parameters
        ----------
        signal_before : np.ndarray
            Reference signal, shape (T, C) or (N, T, C).
        signal_after : np.ndarray
            Transformed signal, same shape.
        dt : float
            Sampling interval.

        Returns
        -------
        dict
            'satisfied', 'violation', 'momentum_before', 'momentum_after'
        """
        mom_before = self._net_momentum(signal_before, dt)
        mom_after = self._net_momentum(signal_after, dt)

        mag_before = float(np.sum(np.abs(mom_before)))
        mag_after = float(np.sum(np.abs(mom_after)))

        diff = float(np.sum(np.abs(mom_after - mom_before)))

        if mag_before == 0.0:
            violation = 0.0 if diff == 0.0 else float("inf")
        else:
            violation = diff / mag_before

        return {
            "constraint": "momentum",
            "satisfied": violation <= self.tolerance,
            "violation": violation,
            "momentum_before": mom_before.tolist() if mom_before.ndim <= 1 else mag_before,
            "momentum_after": mom_after.tolist() if mom_after.ndim <= 1 else mag_after,
        }

    def project(
        self,
        signal: np.ndarray,
        reference: np.ndarray,
        strength: float = 0.9,
        dt: float = 0.02,
    ) -> np.ndarray:
        """Adjust signal to conserve momentum.

        Subtracts the excess per-channel momentum uniformly across all
        timesteps so that the integrated impulse matches the reference.
        Only modifies the domain-relevant channels.

        Parameters
        ----------
        signal : np.ndarray
            Signal to correct, shape (T, C) or (N, T, C).
        reference : np.ndarray
            Reference signal.
        strength : float
            Blending factor.
        dt : float
            Sampling interval.

        Returns
        -------
        np.ndarray
            Corrected signal.
        """
        mom_sig = self._net_momentum(signal, dt)
        mom_ref = self._net_momentum(reference, dt)

        # Excess momentum per channel
        excess = mom_sig - mom_ref  # shape (..., n_channels)

        T = signal.shape[-2]

        # Distribute correction uniformly over all timesteps
        correction_per_step = excess / T  # (..., n_channels)

        result = signal.copy()
        channels = self._vel_ch

        if signal.ndim == 2:
            # (T, C) -- correct only relevant channels
            result[:, channels] -= strength * correction_per_step[np.newaxis, :]
        elif signal.ndim == 3:
            # (N, T, C)
            result[:, :, channels] -= strength * correction_per_step[:, np.newaxis, :]

        return result


# =============================================
#  MASS / CONTINUITY CONSTRAINT
# =============================================

class MassConstraint:
    """Mass/continuity conservation check and projection.

    Checks for large discontinuities in the signal that would indicate
    non-physical mass creation or destruction.  Projects by smoothing
    discontinuities with local averaging.
    """

    def __init__(self, tolerance: float = 0.01) -> None:
        self.tolerance = tolerance

    @staticmethod
    def _max_discontinuity(signal: np.ndarray) -> float:
        """Compute maximum absolute difference between consecutive timesteps.

        Parameters
        ----------
        signal : np.ndarray
            Shape (..., T, C).

        Returns
        -------
        float
            Maximum absolute step-to-step change (normalized by signal RMS).
        """
        diff = np.diff(signal, axis=-2)
        max_jump = float(np.max(np.abs(diff)))

        # Normalize by signal RMS to get a relative measure
        rms = float(np.sqrt(np.mean(signal ** 2)))
        if rms == 0.0:
            return 0.0
        return max_jump / rms

    def check(
        self,
        signal_before: np.ndarray,
        signal_after: np.ndarray,
    ) -> dict:
        """Check mass/continuity conservation.

        Compares the maximum discontinuity in signal_after against the
        tolerance relative to signal_before's scale.

        Parameters
        ----------
        signal_before : np.ndarray
            Reference signal, shape (T, C) or (N, T, C).
        signal_after : np.ndarray
            Transformed signal, same shape.

        Returns
        -------
        dict
            'satisfied', 'violation', 'max_discontinuity_before',
            'max_discontinuity_after'
        """
        disc_before = self._max_discontinuity(signal_before)
        disc_after = self._max_discontinuity(signal_after)

        if disc_before == 0.0:
            violation = 0.0 if disc_after == 0.0 else disc_after
        else:
            violation = max(0.0, disc_after - disc_before) / max(disc_before, 1e-12)

        return {
            "constraint": "mass",
            "satisfied": violation <= self.tolerance,
            "violation": violation,
            "max_discontinuity_before": disc_before,
            "max_discontinuity_after": disc_after,
        }

    def project(
        self,
        signal: np.ndarray,
        reference: np.ndarray,
        strength: float = 0.9,
    ) -> np.ndarray:
        """Smooth discontinuities to restore continuity.

        Applies a local 3-point moving average selectively at timesteps
        where the discontinuity exceeds the reference discontinuity level.

        Parameters
        ----------
        signal : np.ndarray
            Signal to correct, shape (T, C) or (N, T, C).
        reference : np.ndarray
            Reference signal (used to determine acceptable jump level).
        strength : float
            Blending factor.

        Returns
        -------
        np.ndarray
            Smoothed signal.
        """
        ref_rms = float(np.sqrt(np.mean(reference ** 2)))
        if ref_rms == 0.0:
            return signal.copy()

        ref_disc = self._max_discontinuity(reference)
        threshold = ref_disc * (1.0 + self.tolerance) * ref_rms

        result = signal.copy()

        # Compute per-timestep jumps
        diff = np.diff(result, axis=-2)  # (..., T-1, C)
        jump_magnitudes = np.max(np.abs(diff), axis=-1)  # (..., T-1)

        # Iterative smoothing: apply 3-point average at discontinuity locations
        max_iterations = 5
        for _ in range(max_iterations):
            diff = np.diff(result, axis=-2)
            jump_magnitudes = np.max(np.abs(diff), axis=-1)

            # Find locations exceeding threshold
            if np.max(jump_magnitudes) <= threshold:
                break

            if result.ndim == 2:
                # (T, C)
                T = result.shape[0]
                for t in range(1, T - 1):
                    if jump_magnitudes[min(t, len(jump_magnitudes) - 1)] > threshold:
                        smoothed = (result[t - 1] + result[t] + result[t + 1]) / 3.0
                        result[t] = result[t] + strength * (smoothed - result[t])
            elif result.ndim == 3:
                # (N, T, C)
                T = result.shape[1]
                for t in range(1, T - 1):
                    mask = jump_magnitudes[:, min(t, jump_magnitudes.shape[1] - 1)] > threshold
                    if np.any(mask):
                        smoothed = (
                            result[mask, t - 1] + result[mask, t] + result[mask, t + 1]
                        ) / 3.0
                        result[mask, t] = (
                            result[mask, t] + strength * (smoothed - result[mask, t])
                        )

        return result


# =============================================
#  CONSERVATION ENFORCER (Orchestrator)
# =============================================

class ConservationEnforcer:
    """Main orchestrator that applies domain-conditional conservation constraints.

    For physics domains (turbulence, adsb, radar, combustion, atmosphere,
    vessel, airframe), all three constraints (energy, momentum, mass) are
    checked and enforced using domain-specific channel semantics.
    For non-physics domains (har, geology, civic), conservation is inactive
    and signals pass through unchanged.

    Two enforcement modes:
        - "filter" : reject signals that violate any constraint
        - "project" : modify signals to satisfy constraints
    """

    def __init__(self, config: ConservationConfig, domain: str) -> None:
        self.config = config
        self.domain = domain.lower().strip()

        # Determine whether conservation is active for this domain
        self._active = DOMAIN_REQUIRES_CONSERVATION.get(self.domain, False)

        # Look up domain-specific channel semantics
        self._channel_config = _get_channel_config(self.domain)

        # Build constraint list if active
        self._constraints: List[Tuple[str, object]] = []
        if self._active:
            self._constraints = [
                ("energy", EnergyConstraint(
                    tolerance=config.energy_tolerance,
                    channel_config=self._channel_config,
                )),
                ("momentum", MomentumConstraint(
                    tolerance=config.momentum_tolerance,
                    channel_config=self._channel_config,
                )),
                ("mass", MassConstraint(tolerance=config.mass_tolerance)),
            ]

    def is_active(self) -> bool:
        """Whether conservation enforcement is active for this domain."""
        return self._active

    def check_all(
        self,
        signal_before: np.ndarray,
        signal_after: np.ndarray,
    ) -> dict:
        """Check all active constraints and return a combined report.

        Parameters
        ----------
        signal_before : np.ndarray
            Reference signal, shape (T, C) or (N, T, C).
        signal_after : np.ndarray
            Transformed signal, same shape.

        Returns
        -------
        dict
            'active' : bool
            'domain' : str
            'all_satisfied' : bool
            'constraints' : dict mapping constraint name to check result
        """
        if not self._active:
            return {
                "active": False,
                "domain": self.domain,
                "all_satisfied": True,
                "constraints": {},
            }

        results: Dict[str, dict] = {}
        all_ok = True

        for name, constraint in self._constraints:
            if name == "mass":
                check = constraint.check(signal_before, signal_after)
            else:
                check = constraint.check(
                    signal_before, signal_after, dt=self.config.dt
                )
            results[name] = check
            if not check["satisfied"]:
                all_ok = False

        return {
            "active": True,
            "domain": self.domain,
            "all_satisfied": all_ok,
            "constraints": results,
        }

    def enforce(
        self,
        signal: np.ndarray,
        reference: np.ndarray,
    ) -> dict:
        """Enforce all active conservation constraints.

        Parameters
        ----------
        signal : np.ndarray
            Signal to enforce constraints on, shape (T, C) or (N, T, C).
        reference : np.ndarray
            Reference signal for computing conservation targets.

        Returns
        -------
        dict
            'signal' : np.ndarray -- modified (or original) signal
            'applied' : list[str] -- names of constraints that were applied
            'violations' : dict -- constraint name -> violation value
            'mode' : str -- "filter", "project", or "inactive"
        """
        if not self._active:
            return {
                "signal": signal.copy(),
                "applied": [],
                "violations": {},
                "mode": "inactive",
            }

        mode = self.config.mode
        strength = self.config.projection_strength
        dt = self.config.dt

        # First, check current violation state
        check_report = self.check_all(reference, signal)
        violations: Dict[str, float] = {}
        for name, info in check_report["constraints"].items():
            violations[name] = info["violation"]

        if mode == "filter":
            # Reject signal if any constraint is violated
            if check_report["all_satisfied"]:
                return {
                    "signal": signal.copy(),
                    "applied": [],
                    "violations": violations,
                    "mode": "filter",
                }
            else:
                # Return the reference signal (reject the transformed one)
                violated = [
                    name
                    for name, info in check_report["constraints"].items()
                    if not info["satisfied"]
                ]
                return {
                    "signal": reference.copy(),
                    "applied": violated,
                    "violations": violations,
                    "mode": "filter",
                }

        elif mode == "project":
            # Project signal to satisfy each constraint sequentially
            corrected = signal.copy()
            applied: List[str] = []

            for name, constraint in self._constraints:
                # Check this specific constraint
                if name == "mass":
                    check = constraint.check(reference, corrected)
                else:
                    check = constraint.check(reference, corrected, dt=dt)

                if not check["satisfied"]:
                    # Project to satisfy
                    if name == "mass":
                        corrected = constraint.project(
                            corrected, reference, strength=strength
                        )
                    else:
                        corrected = constraint.project(
                            corrected, reference, strength=strength, dt=dt
                        )
                    applied.append(name)

            # Re-check violations after projection
            final_check = self.check_all(reference, corrected)
            final_violations: Dict[str, float] = {}
            for name, info in final_check["constraints"].items():
                final_violations[name] = info["violation"]

            return {
                "signal": corrected,
                "applied": applied,
                "violations": final_violations,
                "mode": "project",
            }

        else:
            raise ValueError(
                f"Unknown enforcement mode '{mode}'. Use 'filter' or 'project'."
            )


# =============================================
#  NUMPY BOUNDARY FUNCTIONS
# =============================================

def check_conservation(
    signal_before: np.ndarray,
    signal_after: np.ndarray,
    domain: str,
    config: Optional[ConservationConfig] = None,
) -> dict:
    """Check all conservation constraints for a signal pair.

    Convenience function that creates a ConservationEnforcer internally
    and returns the full check report.

    Parameters
    ----------
    signal_before : np.ndarray
        Reference signal, shape (T, C) or (N, T, C).
    signal_after : np.ndarray
        Transformed signal, same shape.
    domain : str
        Domain name (e.g. "turbulence", "har").
    config : ConservationConfig, optional
        Configuration. Uses defaults if not provided.

    Returns
    -------
    dict
        Combined check report from ConservationEnforcer.check_all().
    """
    if config is None:
        config = ConservationConfig()

    enforcer = ConservationEnforcer(config, domain)
    return enforcer.check_all(signal_before, signal_after)


def enforce_conservation(
    signal: np.ndarray,
    reference: np.ndarray,
    domain: str,
    config: Optional[ConservationConfig] = None,
) -> np.ndarray:
    """Enforce conservation constraints and return corrected signal.

    Convenience function that creates a ConservationEnforcer internally
    and returns just the corrected signal array.

    Parameters
    ----------
    signal : np.ndarray
        Signal to enforce constraints on, shape (T, C) or (N, T, C).
    reference : np.ndarray
        Reference signal for computing conservation targets.
    domain : str
        Domain name (e.g. "turbulence", "har").
    config : ConservationConfig, optional
        Configuration. Uses defaults if not provided.

    Returns
    -------
    np.ndarray
        Corrected signal (or unchanged if domain is inactive).
    """
    if config is None:
        config = ConservationConfig()

    enforcer = ConservationEnforcer(config, domain)
    result = enforcer.enforce(signal, reference)
    return result["signal"]
