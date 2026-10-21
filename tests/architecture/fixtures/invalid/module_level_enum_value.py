from enum import StrEnum


class Policy(StrEnum):
    LOCAL = "local"


POLICY_TOKEN = Policy.LOCAL.value
