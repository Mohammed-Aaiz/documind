"""Phase 4D — Main runner.

Orchestrates all Phase 4D steps:
  1. Oracle & Baseline evaluation
  2. Training experiments
  3. Candidate evaluation
  4. Report generation

Usage::

    cd backend
    backend/venv/Scripts/python.exe -m phase4d
"""

from __future__ import annotations

import sys


def main() -> int:
    print("=" * 78)
    print("PHASE 4D — QA MODEL IMPROVEMENT")
    print("Controlled Fine-Tuning & Model Validation")
    print("=" * 78)
    print()

    steps = [
        ("Oracle & Baseline Evaluation", "phase4d.oracle_eval"),
        ("Training Experiments", "phase4d.train"),
        ("Candidate Evaluation", "phase4d.evaluate_candidates"),
        ("Report Generation", "phase4d.generate_report"),
    ]

    for step_name, module_name in steps:
        print(f"\n{'=' * 78}")
        print(f"STEP: {step_name}")
        print(f"{'=' * 78}\n")

        try:
            module = __import__(module_name, fromlist=["main"])
            result = module.main()
            if result != 0:
                print(f"\nWARNING: {step_name} returned {result}")
        except Exception as exc:
            print(f"\nERROR in {step_name}: {exc}")
            import traceback
            traceback.print_exc()
            return 1

    print("\n" + "=" * 78)
    print("PHASE 4D COMPLETE")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
