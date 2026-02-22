"""
DSC288 Server Management

Usage:
    python src/server/manage.py start      Start LiteLLM proxy (background)
    python src/server/manage.py start -f   Start in foreground
    python src/server/manage.py stop       Stop the running server
    python src/server/manage.py restart    Restart the server
    python src/server/manage.py status     Check if the server is running
    python src/server/manage.py test       Run test suite against the proxy
    python src/server/manage.py logs       Show recent server logs
    python src/server/manage.py logs -n 20 Show last N lines
    python src/server/manage.py models     List available models
    python src/server/manage.py health     Quick health check
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent          # repo root
SERVE_SCRIPT = SCRIPT_DIR / "_serve.py"
PID_FILE = BASE_DIR / ".litellm.pid"
LOG_FILE = BASE_DIR / "logs" / "litellm.log"
KEY_FILE = BASE_DIR / ".key"
CONFIG_FILE = BASE_DIR / "litellm_config.yaml"
LITELLM_PKG = r"C:\litellm_pkg"

PROXY_URL = "http://localhost:4000"
MASTER_KEY = "sk-ds288r"


# ── Helpers ─────────────────────────────────────────────────────────

def load_keys():
    """Parse the .key file (KEY=VALUE per line) into a dict."""
    if not KEY_FILE.exists():
        print("[ERROR] .key file not found at repo root.")
        sys.exit(1)
    keys = {}
    for line in KEY_FILE.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    return keys


def load_api_key():
    keys = load_keys()
    key = keys.get("OPENAI_API_KEY", "")
    if not key.startswith("sk-"):
        print("[ERROR] .key does not contain a valid OPENAI_API_KEY.")
        sys.exit(1)
    return key


def get_running_pid():
    """Return the PID from the pidfile if the process is actually alive."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None

    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True,
            )
            if str(pid) not in r.stdout:
                PID_FILE.unlink(missing_ok=True)
                return None
        else:
            os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def _server_env():
    return {
        **os.environ,
        "OPENAI_API_KEY": load_api_key(),
        "PYTHONPATH": LITELLM_PKG + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "PYTHONIOENCODING": "utf-8",
    }


def wait_for_server(timeout=45):
    """Wait until the proxy responds."""
    import urllib.request, urllib.error

    endpoints = [f"{PROXY_URL}/health", f"{PROXY_URL}/v1/models", f"{PROXY_URL}/"]
    start = time.time()
    while time.time() - start < timeout:
        for url in endpoints:
            try:
                req = urllib.request.Request(
                    url, headers={"Authorization": f"Bearer {MASTER_KEY}"},
                )
                resp = urllib.request.urlopen(req, timeout=3)
                if resp.status == 200:
                    return True
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                pass
        time.sleep(2)
    return False


def _proxy_get(path, timeout=5):
    """GET a proxy endpoint, return parsed JSON or None."""
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(
            f"{PROXY_URL}{path}",
            headers={"Authorization": f"Bearer {MASTER_KEY}"},
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except Exception:
        return None


# ── Commands ────────────────────────────────────────────────────────

def cmd_start(args):
    pid = get_running_pid()
    if pid:
        print(f"[INFO] Server already running (PID {pid})")
        print(f"       {PROXY_URL}")
        return

    env = _server_env()
    cmd = [sys.executable, str(SERVE_SCRIPT)]

    if args.foreground:
        print("[INFO] Starting in foreground (Ctrl+C to stop)...")
        proc = subprocess.run(cmd, env=env, cwd=str(BASE_DIR))
        sys.exit(proc.returncode)

    print("[INFO] Starting LiteLLM proxy server...")

    if sys.platform == "win32":
        proc = subprocess.Popen(
            cmd, env=env, cwd=str(BASE_DIR),
            stdout=open(LOG_FILE, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        proc = subprocess.Popen(
            cmd, env=env, cwd=str(BASE_DIR),
            stdout=open(LOG_FILE, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    PID_FILE.write_text(str(proc.pid))
    print(f"[INFO] Server PID: {proc.pid}")
    print("[INFO] Waiting for server to be ready...", end="", flush=True)

    if wait_for_server(timeout=45):
        print(" ready!")
        print()
        print(f"  URL    : {PROXY_URL}")
        print(f"  Key    : {MASTER_KEY}")
        print(f"  PID    : {proc.pid}")
        print(f"  Logs   : python src/server/manage.py logs")
        print(f"  Stop   : python src/server/manage.py stop")
    else:
        print(" timeout.")
        print("[WARN] Server may still be starting. Check: python src/server/manage.py logs")


def cmd_stop(args):
    pid = get_running_pid()
    if not pid:
        print("[INFO] Server is not running.")
        return

    print(f"[INFO] Stopping server (PID {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                os.kill(pid, signal.SIGKILL)
    except Exception as e:
        print(f"[WARN] Could not kill process: {e}")

    PID_FILE.unlink(missing_ok=True)
    print("[INFO] Server stopped.")


def cmd_restart(args):
    cmd_stop(args)
    time.sleep(2)
    cmd_start(args)


def cmd_status(args):
    pid = get_running_pid()
    if not pid:
        print("Status : STOPPED")
        print(f"URL    : {PROXY_URL}")
        return

    print("Status : RUNNING")
    print(f"PID    : {pid}")
    print(f"URL    : {PROXY_URL}")
    print(f"Key    : {MASTER_KEY}")

    data = _proxy_get("/v1/models")
    if data:
        print(f"Health : OK ({len(data.get('data', []))} models loaded)")
    else:
        print("Health : UNKNOWN (could not reach proxy)")


def cmd_test(args):
    """Run completion + embedding tests through the proxy."""
    pid = get_running_pid()
    if not pid:
        print("[ERROR] Server is not running. Start first: python src/server/manage.py start")
        sys.exit(1)

    pkg_path = LITELLM_PKG + os.pathsep + os.environ.get("PYTHONPATH", "")
    if LITELLM_PKG not in sys.path:
        sys.path.insert(0, LITELLM_PKG)

    from openai import OpenAI
    client = OpenAI(base_url=PROXY_URL, api_key=MASTER_KEY)

    results = {}

    def _test_chat(name, model, prompt):
        print(f"\n{'='*60}")
        print(f"Testing: {name} ({model})")
        print(f"{'='*60}")
        print(f"Prompt: {prompt}\n")
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            print(f"Response: {r.choices[0].message.content}")
            print(f"Tokens:   {r.usage.prompt_tokens}+{r.usage.completion_tokens}={r.usage.total_tokens}")
            print(f"Model:    {r.model}")
            results[name] = True
        except Exception as e:
            print(f"[ERROR] {e}")
            results[name] = False

    def _test_embed(name, model, text):
        print(f"\n{'='*60}")
        print(f"Testing: {name} ({model})")
        print(f"{'='*60}")
        try:
            r = client.embeddings.create(model=model, input=text)
            dim = len(r.data[0].embedding)
            print(f"Dimension: {dim}")
            print(f"Tokens:    {r.usage.total_tokens}")
            results[name] = True
        except Exception as e:
            print(f"[ERROR] {e}")
            results[name] = False

    print("=" * 60)
    print("LITELLM PROXY TEST SUITE")
    print(f"Proxy: {PROXY_URL}  |  Key: {MASTER_KEY}")
    print("=" * 60)

    _test_chat("gpt-5.2", "gpt-5.2",
               "You are a financial analyst. In one sentence, what does a bullish SMA crossover indicate?")
    _test_chat("agent-fast", "agent-fast",
               "In one sentence, what is a buy/hold/sell signal?")
    _test_embed("embedder", "embedder",
                "Apple reported strong quarterly earnings, beating analyst expectations.")

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    for name, ok in results.items():
        print(f"  {name:25s} {'PASS' if ok else 'FAIL'}")
    passed = all(results.values())
    print(f"\n{'All tests passed!' if passed else 'Some tests FAILED.'}")
    if not passed:
        sys.exit(1)


def cmd_logs(args):
    if not LOG_FILE.exists():
        print("[INFO] No log file found. Start the server first.")
        return

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = args.lines or 50
    to_show = lines[-tail:]

    print(f"--- Last {len(to_show)} lines of {LOG_FILE.name} ---")
    for line in to_show:
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
    print(f"--- End ({len(lines)} total lines) ---")


def cmd_models(args):
    import yaml
    if not CONFIG_FILE.exists():
        print(f"[ERROR] Config not found: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE, "r") as f:
        config = yaml.safe_load(f)

    models = config.get("model_list", [])
    aliases, direct, embeddings = [], [], []

    for m in models:
        name = m.get("model_name", "")
        target = m.get("litellm_params", {}).get("model", "").replace("openai/", "")
        if name.startswith("agent-") or name == "embedder":
            aliases.append((name, target))
        elif "embedding" in name:
            embeddings.append((name, target))
        else:
            direct.append((name, target))

    print("=" * 55)
    print("AVAILABLE MODELS")
    print("=" * 55)
    print("\nProject Aliases (use these in agent code):")
    for n, t in aliases:
        print(f"  {n:22s} -> {t}")
    print(f"\nDirect Models ({len(direct)}):")
    for n, t in direct:
        print(f"  {n:22s}    {t}")
    print(f"\nEmbedding Models ({len(embeddings)}):")
    for n, t in embeddings:
        print(f"  {n:30s}  {t}")
    print(f"\nTotal: {len(models)} model entries")
    print(f"Proxy: {PROXY_URL}  |  Key: {MASTER_KEY}")


def cmd_health(args):
    import urllib.request, urllib.error

    for endpoint in ["/health", "/v1/models"]:
        data = _proxy_get(endpoint)
        if data is None:
            continue

        if endpoint == "/health":
            print("[OK] Proxy is healthy")
            for ep in data.get("healthy_endpoints", [])[:10]:
                tag = "OK" if ep.get("healthy") else "FAIL"
                print(f"  [{tag:4s}] {ep.get('model', '?')}")
        else:
            models = data.get("data", [])
            print(f"[OK] Proxy is responding ({len(models)} models loaded)")
            for m in models[:10]:
                print(f"  [OK  ] {m.get('id', '?')}")
            if len(models) > 10:
                print(f"  ... and {len(models) - 10} more")
        return

    print(f"[FAIL] Cannot reach proxy at {PROXY_URL}")
    sys.exit(1)


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DSC288 Server Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start LiteLLM proxy server")
    p_start.add_argument("-f", "--foreground", action="store_true",
                         help="Run in foreground (don't daemonize)")

    sub.add_parser("stop", help="Stop the running server")

    p_restart = sub.add_parser("restart", help="Restart the server")
    p_restart.add_argument("-f", "--foreground", action="store_true")

    sub.add_parser("status", help="Check server status")
    sub.add_parser("test", help="Run test suite against the proxy")

    p_logs = sub.add_parser("logs", help="Show recent server logs")
    p_logs.add_argument("-n", "--lines", type=int, default=50,
                        help="Number of lines to show (default: 50)")

    sub.add_parser("models", help="List available models")
    sub.add_parser("health", help="Quick health check")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "test": cmd_test,
        "logs": cmd_logs,
        "models": cmd_models,
        "health": cmd_health,
    }[args.command](args)


if __name__ == "__main__":
    main()
