"""Backwards-compatible entry point: `python3 main.py "<query>" [--json] [--ppt]`.

The real CLI lives in `src/kasa_agent/cli.py` and is installed as the
`kasa-report` console script (`pip install -e .`). This shim keeps the old
invocation working from a plain source checkout without an install.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from kasa_agent.cli import main

if __name__ == "__main__":
    main()
