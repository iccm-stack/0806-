from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Global AI Weekly report")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--no-email", action="store_true", help="Generate report without sending email")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    report_path = run(args.root.resolve(), send_mail=not args.no_email)
    print(report_path)


if __name__ == "__main__":
    main()

