_STALE_THRESHOLD_SECONDS = 30.0


def is_stale(age_seconds: float) -> bool:
    return age_seconds > _STALE_THRESHOLD_SECONDS
