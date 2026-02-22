"""
Internal LiteLLM server process — spawned by manage.py, not called directly.
"""

import os
import sys
from pathlib import Path

LITELLM_PKG = r"C:\litellm_pkg"
if LITELLM_PKG not in sys.path:
    sys.path.insert(0, LITELLM_PKG)

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = BASE_DIR / "litellm_config.yaml"


def main():
    print("=" * 60)
    print("LITELLM PROXY SERVER")
    print("=" * 60)
    print(f"Config : {CONFIG_FILE}")
    print(f"Port   : 4000")
    print(f"Master : sk-ds288r")
    print(f"URL    : http://localhost:4000")
    print()
    print("Project aliases:")
    print("  agent-reasoning  -> gpt-5.2")
    print("  agent-fast       -> gpt-5-mini")
    print("  agent-bulk       -> gpt-5-nano")
    print("  embedder         -> text-embedding-3-small")
    print("=" * 60)

    sys.argv = [
        "litellm",
        "--config", str(CONFIG_FILE),
        "--port", "4000",
        "--host", "0.0.0.0",
    ]

    from litellm.proxy.proxy_cli import run_server
    run_server()


if __name__ == "__main__":
    main()
