"""CLI entry point: `python -m schedule`.

Kept separate from gate.py itself (rather than a `if __name__ ==
"__main__":` block in that file) specifically so `python -m schedule`
doesn't double-import gate.py under two different module names — that
happens when a package's `__init__.py` already imports a submodule that
the same submodule is then also run as `__main__` for. Using the
package's own `__main__.py` as the run target avoids that entirely.

Avoids embedding multi-line Python inside the workflow YAML, which is
fragile to indentation/quoting — prints "true" or "false" to stdout, which
the workflow step captures directly.
"""

import json
import os

from schedule.gate import should_run_full_scan

if __name__ == "__main__":
    trigger = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch")
    with open("schedule_config.json", encoding="utf-8") as f:
        config = json.load(f)
    print("true" if should_run_full_scan(trigger, config) else "false")
