from trajcert.config import TrajCertConfig, active_config


def run(config: TrajCertConfig) -> None:
    _ = active_config.set(config)
