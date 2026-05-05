"""
@ai-context: Quality Assurance script. Runs strict mypy type checking and ruff linting/formatting
across the entire codebase to guarantee production-ready code.
"""
import subprocess
import sys


def run_step(step_name: str, command: list[str]) -> bool:
    """
    Runs a single QA step and prints the result.

    Args:
        step_name: A human-readable label for the step.
        command: The command to execute as a list of strings.

    Returns:
        True if the step passed, False otherwise.
    """
    print(f"\n{'=' * 60}")
    print(f"  >> {step_name}")
    print(f"     Komut: {' '.join(command)}")
    print(f"{'=' * 60}")

    result: subprocess.CompletedProcess[bytes] = subprocess.run(command)

    if result.returncode != 0:
        print(f"\n  [X] BASARISIZ: {step_name} (Cikis kodu: {result.returncode})")
        return False

    print(f"  [OK] BASARILI: {step_name}")
    return True


def main() -> None:
    """Runs all QA steps in sequence. Stops on first failure."""
    print("=" * 60)
    print("  Kod Kalite Denetimi Baslatiliyor...")
    print("=" * 60)

    steps: list[tuple[str, list[str]]] = [
        ("Ruff Format (Otomatik Duzeltme)", [sys.executable, "-m", "ruff", "format", "src/"]),
        ("Ruff Check (Lint Denetimi)", [sys.executable, "-m", "ruff", "check", "src/"]),
        ("Mypy (Kati Tip Kontrolu)", [sys.executable, "-m", "mypy", "src/"]),
    ]

    for step_name, command in steps:
        passed: bool = run_step(step_name, command)
        if not passed:
            print("\n" + "=" * 60)
            print("  [!] Denetim DURDURULDU. Lutfen yukaridaki hatalari duzeltin.")
            print("=" * 60)
            sys.exit(1)

    print("\n" + "=" * 60)
    print("  Tum denetimler BASARILI! Kod uretime hazir.")
    print("=" * 60)


if __name__ == "__main__":
    main()
