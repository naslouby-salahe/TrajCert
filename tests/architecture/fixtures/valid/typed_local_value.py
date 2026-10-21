from trajcert.types import ClientId, SensitivityBudget


def local(client_id: ClientId, rho: SensitivityBudget) -> tuple[ClientId, SensitivityBudget]:
    return client_id, rho
