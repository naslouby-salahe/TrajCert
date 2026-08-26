from __future__ import annotations

import phase2_coordinate_recovery as recovery


def main() -> None:
    recovery.recover_config_model()
    recovery.recover_registry()
    recovery.recover_plan()


if __name__ == "__main__":
    main()
