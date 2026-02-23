"""Entry point: python -m dlp [--dry-run]"""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dlp",
        description="DLP Control Panel - Data Loss Prevention TUI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate all actions without modifying the system",
    )
    args = parser.parse_args()

    # Load config early for logging setup
    from dlp.config import DLPConfig

    config_path = Path(__file__).parent.parent.parent / "config" / "default.toml"
    if config_path.exists():
        config = DLPConfig.from_toml(config_path)
    else:
        config = DLPConfig()

    # Configure logging from config before anything else
    from dlp.log_setup import setup_logging

    setup_logging(level=config.logging.level, log_file=config.logging.file)

    from dlp.app import DLPApp

    app = DLPApp(dry_run=args.dry_run, config=config)
    app.run()


if __name__ == "__main__":
    main()
