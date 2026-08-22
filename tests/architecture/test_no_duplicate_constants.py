from trajcert.analysis.claims import FRAMEWORK_NAME
from trajcert.configuration.loading import load_configuration


def test_framework_name_has_one_configuration_independent_authority() -> None:
    configuration = load_configuration()
    assert FRAMEWORK_NAME.startswith("TrajCert")
    assert configuration.schema_version == 1
