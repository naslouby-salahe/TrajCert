from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", min_length=1)]


class LocalCertificateIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    client_id: Identifier
    action_channel_id: Identifier
    epoch_id: Identifier
