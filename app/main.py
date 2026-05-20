"""Command-line entrypoint for headless use (no dashboard).

  python -m app.main load     # (re)load dataset + seed scores
  python -m app.main run      # run the 90-day sim to completion (auto-approves)
  python -m app.main report   # print the success-criteria report
"""
from __future__ import annotations

import sys


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "load":
        from app.db.loader import load_all
        load_all(reset=True)

    elif cmd == "run":
        from app.sim import runner
        runner.AUTO_APPROVE = True
        print("Running 90-day simulation headless (auto-approving escalations)…")
        runner._run()
        from app.eval.report import print_report
        print_report()

    elif cmd == "report":
        from app.eval.report import print_report
        print_report()

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
