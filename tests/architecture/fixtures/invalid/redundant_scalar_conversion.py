from trajcert.types import ClientId, Count


def local(count: Count, client_id: ClientId) -> tuple[Count, ClientId]:
    return int(count), str(client_id)
