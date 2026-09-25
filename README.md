# TrajCert

TrajCert is the reference implementation for trajectory-aware partial-identification and sensitivity certification.

The planned core experiments generate synthetic data from the configured laws; TrajCert does not bundle a scientific dataset. An optional HITL-IoT retrospective replay reads an externally supplied CSV at the path in `configs/trajcert.yaml`. That replay is diagnostic-only and does not support external-validation or deployment claims.
