from __future__ import annotations


class TrajCertError(Exception):
    pass


class ConfigurationError(TrajCertError):
    pass


class InvalidScientificDataError(TrajCertError):
    pass


class InvalidProbabilityError(InvalidScientificDataError):
    pass


class InvalidPartitionError(InvalidScientificDataError):
    pass


class DataIntegrityError(InvalidScientificDataError):
    pass


class NumericalError(TrajCertError):
    pass


class RootSolveError(NumericalError):
    pass


class InvariantViolationError(TrajCertError):
    pass


class SerializationError(TrajCertError):
    pass