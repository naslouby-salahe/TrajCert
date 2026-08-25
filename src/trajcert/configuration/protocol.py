from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.protocol import ProtocolSchemaVersion


def protocol_schema_version(configuration: TrajCertConfiguration) -> ProtocolSchemaVersion:
    return ProtocolSchemaVersion(configuration.schema_version)
