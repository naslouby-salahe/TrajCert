from trajcert.configuration.models import TrajCertConfiguration


def protocol_schema_version(configuration: TrajCertConfiguration) -> int:
    return configuration.schema_version
