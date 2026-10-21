def local(frame: object) -> tuple[object, ...]:
    return tuple(frame.to_dicts())
