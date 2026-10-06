#!/usr/bin/env python3
"""Package only reviewed source and locked dependencies; remote Azure build installs wheels."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = Path(__file__).resolve().parents[1] / "azure/function-relay"
args.output.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(args.output, "w", ZIP_DEFLATED) as archive:
    for name in ("function_app.py", "host.json", "requirements.txt"):
        archive.write(source / name, name)
print(f"Relay source package: {args.output.resolve()}")
