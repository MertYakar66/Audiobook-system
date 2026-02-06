#!/usr/bin/env python3
"""
TTS Diagnostic Script

This script helps diagnose Tortoise TTS installation issues.
Run: python -m scripts.diagnose_tts
"""

import sys
import subprocess
from pathlib import Path


def print_header(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_python_info():
    print_header("Python Environment")
    print(f"  Python version: {sys.version}")
    print(f"  Python executable: {sys.executable}")
    print(f"  Python path: {sys.prefix}")


def check_pip_packages():
    print_header("Installed Packages")

    packages_to_check = [
        "torch", "torchaudio", "transformers", "tokenizers",
        "tortoise-tts", "einops", "rotary-embedding-torch"
    ]

    # Get list of installed packages
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True, text=True
        )
        installed = {}
        for line in result.stdout.strip().split("\n"):
            if "==" in line:
                name, version = line.split("==")
                installed[name.lower()] = version
    except Exception as e:
        print(f"  Error getting pip list: {e}")
        return

    for pkg in packages_to_check:
        pkg_lower = pkg.lower()
        if pkg_lower in installed:
            print(f"  {pkg}: {installed[pkg_lower]}")
        else:
            print(f"  {pkg}: NOT INSTALLED")


def check_tortoise_location():
    print_header("Tortoise Package Location")

    # Try to find where tortoise-tts was installed
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "tortoise-tts"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.startswith("Location:") or line.startswith("Name:"):
                    print(f"  {line}")
        else:
            print("  tortoise-tts package not found via pip show")
    except Exception as e:
        print(f"  Error: {e}")

    # Check if the tortoise directory exists in site-packages
    import site
    print()
    print("  Site-packages directories:")
    for sp in site.getsitepackages():
        print(f"    - {sp}")
        tortoise_dir = Path(sp) / "tortoise"
        if tortoise_dir.exists():
            print(f"      Found 'tortoise' folder here!")
            # List contents
            contents = list(tortoise_dir.iterdir())[:5]
            for item in contents:
                print(f"        - {item.name}")

    # Check user site-packages
    user_site = site.getusersitepackages()
    print(f"    - {user_site} (user)")
    if Path(user_site).exists():
        tortoise_dir = Path(user_site) / "tortoise"
        if tortoise_dir.exists():
            print(f"      Found 'tortoise' folder here!")


def test_imports():
    print_header("Import Tests")

    tests = [
        ("torch", "import torch; print(f'torch {torch.__version__}')"),
        ("torchaudio", "import torchaudio; print(f'torchaudio {torchaudio.__version__}')"),
        ("transformers", "import transformers; print(f'transformers {transformers.__version__}')"),
        ("tortoise", "import tortoise; print('tortoise OK')"),
        ("tortoise.api", "from tortoise.api import TextToSpeech; print('TextToSpeech OK')"),
    ]

    for name, test_code in tests:
        try:
            exec(test_code)
            print(f"  {name}: OK")
        except ImportError as e:
            print(f"  {name}: FAILED - {e}")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")


def suggest_fixes():
    print_header("Suggested Fixes")

    print("""
  If tortoise-tts is installed but 'import tortoise' fails:

  1. ENSURE MATCHING PYTHON:
     Make sure you're using the same Python for pip and running scripts:

     # Check which python pip uses
     pip -V

     # Should match
     python --version

  2. TRY UNINSTALL AND REINSTALL:
     pip uninstall tortoise-tts -y
     pip install git+https://github.com/neonbjb/tortoise-tts.git

  3. CHECK FOR MULTIPLE PYTHON INSTALLATIONS:
     # On Windows, try using 'py' launcher
     py -3.13 -m pip install tortoise-tts
     py -3.13 -c "from tortoise.api import TextToSpeech"

  4. TRY IN A FRESH VIRTUAL ENVIRONMENT:
     python -m venv tts_env
     tts_env\\Scripts\\activate
     pip install torch torchaudio
     pip install git+https://github.com/neonbjb/tortoise-tts.git
     python -c "from tortoise.api import TextToSpeech; print('OK')"

  5. CHECK SYSTEM PATH:
     The pip warning about 'Scripts' not on PATH means Windows can't find
     your Python Scripts folder. This shouldn't affect imports but can
     indicate Python installation issues.
""")


def main():
    print()
    print("TTS DIAGNOSTIC TOOL")
    print("=" * 60)

    check_python_info()
    check_pip_packages()
    check_tortoise_location()
    test_imports()
    suggest_fixes()

    print()
    print("=" * 60)
    print("  Diagnostic complete. Check results above.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
