"""Additive float64 native decoders. No fitted weights or control-trunk changes.

Coordinates are fractions of one declared session; values are USD movements.
Quantile order is P10/P50/P90. Auxiliary tails detach the median and native state.
"""
from dataclasses import dataclass
import torch
from torch import nn
from torch.nn import functional as F

try:
    from .forecast_contract import HashedContract, finite_number
except ImportError:
    from forecast_contract import HashedContract, finite_number


@dataclass(frozen=True)
class KnotPolicy(HashedContract):
    quantum_ns: int
    max_interior: int

    def __post_init__(self):
        if type(self.quantum_ns) is not int or self.quantum_ns < 1:
            raise ValueError('positive timestamp quantum required')
        if type(self.max_interior) is not int or self.max_interior < 0:
            raise ValueError('nonnegative interior budget required')


class NativeForecastHeads(nn.Module):
    def __init__(self, d_model, hidden):
        super().__init__()
        if any(type(n) is not int or n < 1 for n in (d_model, hidden)):
            raise ValueError('positive declared decoder dimensions required')
        self.d_model, self.hidden = d_model, hidden
        def mlp(width, output):
            return nn.Sequential(nn.Linear(width, hidden, dtype=torch.float64), nn.Tanh(),
                                 nn.Linear(hidden, output, dtype=torch.float64))
        self.gap_median = mlp(d_model, 1)
        self.gap_tails = mlp(d_model, 2)
        self.path_median = mlp(d_model + 2, 1)
        self.path_tails = mlp(d_model + 2, 2)
        self.time_decoder = mlp(d_model + 2, 2)
        self.session_projection = nn.Linear(4, d_model, bias=False, dtype=torch.float64)

    def freeze_medians(self):
        """Enforce the staged auxiliary-fit boundary, including stale gradients.

        The control trunk remains external; callers must also freeze that trunk.
        This method does not fit anything or create an optimizer.
        """
        for module in (self.gap_median, self.path_median, self.time_decoder, self.session_projection):
            for parameter in module.parameters():
                parameter.requires_grad_(False)
                parameter.grad = None

    def condition(self, z, session_features):
        """Known session metadata: time-to-open/duration in days, USD scale, tick.

        These are declared forecast coordinates, not transformations of raw input.
        """
        self._state(z)
        if (type(session_features) is not tuple or len(session_features) != 4):
            raise ValueError('four declared session features required')
        for value in session_features:
            finite_number(value, 'session feature')
        result = z + self.session_projection(z.new_tensor(session_features))
        self._state(result)
        return result

    def _state(self, z):
        if (not isinstance(z, torch.Tensor) or z.shape != (self.d_model,)
                or z.dtype != torch.float64 or not torch.isfinite(z).all()
                or any(p.dtype != z.dtype or p.device != z.device for p in self.parameters())):
            raise ValueError('finite float64 decision representation required on decoder device')

    @staticmethod
    def _ordered(median, widths):
        result = torch.stack((median.detach() - widths[0], median,
                              median.detach() + widths[1]))
        if not torch.isfinite(result).all():
            raise ValueError('nonfinite native quantiles')
        return result

    def gap(self, z):
        self._state(z)
        return self._ordered(self.gap_median(z).squeeze(-1), F.softplus(self.gap_tails(z.detach())))

    def path(self, z, query, *, anchor=0., anchor_usd=0.):
        self._state(z)
        for name, value in (('query', query), ('anchor', anchor), ('anchor_usd', anchor_usd)):
            finite_number(value, name)
        if not 0 <= anchor <= query <= 1:
            raise ValueError('query must be in the remaining session')
        features = torch.cat((z, z.new_tensor([query, anchor])))
        origin = torch.cat((z, z.new_tensor([anchor, anchor])))
        # Residual at the certified anchor is exactly zero. Every other value
        # is evaluated at its own coordinate, independently of the daily net.
        median = (self.path_median(features) - self.path_median(origin)).squeeze(-1) + anchor_usd
        widths = F.softplus(self.path_tails(features.detach())) * (query - anchor)
        return self._ordered(median, widths)

    def next_time(self, z, previous, previous_delay):
        self._state(z)
        features = torch.cat((z, z.new_tensor([previous, previous_delay])))
        raw = self.time_decoder(features)
        # STOP is a timing decision, unrelated to forecast ranking/confidence.
        return torch.stack((torch.sigmoid(raw[0]), raw[1]))

    def knots(self, z, *, duration_ns, start_ns, policy):
        self._state(z)
        if (not isinstance(policy, KnotPolicy) or type(duration_ns) is not int
                or type(start_ns) is not int or not 0 <= start_ns < duration_ns
                or duration_ns > 2**53 or duration_ns % policy.quantum_ns
                or start_ns % policy.quantum_ns):
            raise ValueError('session offsets must be exactly representable on the locked quantum')
        times = [start_ns]; previous_delay = 0.
        while True:
            step = self.next_time(z, times[-1] / duration_ns, previous_delay)
            if step.shape != (2,) or not torch.isfinite(step).all():
                raise ValueError('nonfinite or malformed time output')
            delay, stop = step.detach().tolist()
            if stop >= 0:
                return (*times, duration_ns)
            if len(times) - 1 >= policy.max_interior:
                raise ValueError('knot budget exhausted before STOP')
            if not 0 < delay < 1:
                raise ValueError('next-time fraction must be strictly between zero and one')
            raw = times[-1] + delay * (duration_ns - times[-1])
            next_ns = round(raw / policy.quantum_ns) * policy.quantum_ns
            if not times[-1] < next_ns < duration_ns:
                raise ValueError('duplicate or unrepresentable endogenous timestamp')
            previous_delay = (next_ns - times[-1]) / duration_ns
            times.append(next_ns)
