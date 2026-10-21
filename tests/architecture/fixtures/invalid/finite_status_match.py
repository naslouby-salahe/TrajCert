def is_complete(status: object) -> bool:
    match status:
        case "done":
            return True
        case _:
            return False
