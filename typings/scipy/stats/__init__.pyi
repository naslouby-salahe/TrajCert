class _FrozenDistribution:
    def ppf(self, q: float, *args: float) -> float: ...

norm: _FrozenDistribution
beta: _FrozenDistribution
