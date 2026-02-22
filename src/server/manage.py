"""
DSC288 Server Management (LiteLLM + Neo4j)

Usage:
    python src/server/manage.py start           Start both LiteLLM and Neo4j
    python src/server/manage.py start litellm   Start only LiteLLM
    python src/server/manage.py start neo4j     Start only Neo4j (Docker)
    python src/server/manage.py stop            Stop both
    python src/server/manage.py stop litellm    Stop only LiteLLM
    python src/server/manage.py status          Show status of both
    python src/server/manage.py restart [litellm|neo4j]  Restart one or both
    python src/server/manage.py neo4j reset    Wipe Neo4j database
    python src/server/manage.py neo4j shell    Print Neo4j browser URL
    python src/server/manage.py test            Run test suite (LiteLLM)
    python src/server/manage.py logs [-n N]     LiteLLM logs
    python src/server/manage.py models          List LiteLLM models
    python src/server/manage.py health         LiteLLM health check
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
CONFIG_FILE = BASE_DIR / "config" / "litellm_config.yaml"
NEO4J_CONFIG = BASE_DIR / "config" / "neo4j.yaml"
NEO4J_DATA = BASE_DIR / "data" / "neo4j"
NEO4J_CONTAINER = "dsc288-neo4j"
LITELLM_PKG = r"C:\litellm_pkg"

PROXY_URL = "http://localhost:4000"
MASTER_KEY = "sk-ds288r"
NEO4J_BROWSER_URL = "http://localhost:7474"


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


# ── Neo4j helpers ───────────────────────────────────────────────────

def _neo4j_running():
    """Return True if Neo4j container is running."""
    r = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={NEO4J_CONTAINER}"],
        capture_output=True, text=True, cwd=str(BASE_DIR),
    )
    return bool(r.stdout.strip())


def _neo4j_start():
    """Start Neo4j in Docker. Idempotent if already running."""
    if _neo4j_running():
        print(f"[INFO] Neo4j already running (container {NEO4J_CONTAINER})")
        return
    NEO4J_DATA.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "-d",
        "--name", NEO4J_CONTAINER,
        "-p", "7474:7474", "-p", "7687:7687",
        "-e", "NEO4J_AUTH=neo4j/dsc288graph",
        "-v", f"{NEO4J_DATA.absolute()}:/data",
        "neo4j:latest",
    ]
    r = subprocess.run(cmd, cwd=str(BASE_DIR))
    if r.returncode != 0:
        print("[ERROR] Failed to start Neo4j. Is Docker running?")
        sys.exit(1)
    print(f"[INFO] Neo4j starting (container {NEO4J_CONTAINER})")
    print(f"       Browser: {NEO4J_BROWSER_URL}  Bolt: bolt://localhost:7687")
    # Wait for bolt to be ready
    for _ in range(30):
        time.sleep(1)
        if _neo4j_bolt_ok():
            print("[INFO] Neo4j bolt ready.")
            return
    print("[WARN] Neo4j may still be starting. Try: python src/server/manage.py status")


def _neo4j_bolt_ok():
    """Return True if Neo4j bolt port accepts connections."""
    try:
        import yaml
        from neo4j import GraphDatabase
        cfg = yaml.safe_load(NEO4J_CONFIG.read_text()) if NEO4J_CONFIG.exists() else {}
        uri = cfg.get("uri", "bolt://localhost:7687")
        user = cfg.get("user", "neo4j")
        password = cfg.get("password", "dsc288graph")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


def _neo4j_stop():
    """Stop and remove Neo4j container."""
    if not _neo4j_running():
        print("[INFO] Neo4j is not running.")
        return
    subprocess.run(["docker", "stop", NEO4J_CONTAINER], capture_output=True, cwd=str(BASE_DIR))
    subprocess.run(["docker", "rm", NEO4J_CONTAINER], capture_output=True, cwd=str(BASE_DIR))
    print("[INFO] Neo4j stopped.")


# ── Commands ────────────────────────────────────────────────────────

def _service_target(args):
    """Return 'litellm', 'neo4j', or 'all' from args.service."""
    s = getattr(args, "service", None) or "all"
    if s not in ("litellm", "neo4j", "all"):
        return "all"
    return s


def _start_litellm(foreground=False):
    pid = get_running_pid()
    if pid:
        print(f"[INFO] LiteLLM already running (PID {pid})")
        return
    env = _server_env()
    cmd = [sys.executable, str(SERVE_SCRIPT)]
    if foreground:
        print("[INFO] Starting LiteLLM in foreground (Ctrl+C to stop)...")
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
    print(f"[INFO] LiteLLM PID: {proc.pid}")
    print("[INFO] Waiting for LiteLLM...", end="", flush=True)
    if wait_for_server(timeout=45):
        print(" ready!")
        print(f"  URL    : {PROXY_URL}  Key: {MASTER_KEY}")
    else:
        print(" timeout. Check: python src/server/manage.py logs")


def cmd_start(args):
    target = _service_target(args)
    if target in ("litellm", "all"):
        _start_litellm(foreground=getattr(args, "foreground", False))
    if target in ("neo4j", "all"):
        _neo4j_start()
    if target == "all":
        print()
        print("  Stop both: python src/server/manage.py stop")
        print("  Status:   python src/server/manage.py status")


def _stop_litellm():
    pid = get_running_pid()
    if not pid:
        print("[INFO] LiteLLM is not running.")
        return
    print(f"[INFO] Stopping LiteLLM (PID {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
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
    print("[INFO] LiteLLM stopped.")


def cmd_stop(args):
    target = _service_target(args)
    if target in ("litellm", "all"):
        _stop_litellm()
    if target in ("neo4j", "all"):
        _neo4j_stop()


def cmd_restart(args):
    target = _service_target(args)
    if target in ("litellm", "all"):
        _stop_litellm()
    if target in ("neo4j", "all"):
        _neo4j_stop()
    time.sleep(2)
    if target in ("litellm", "all"):
        _start_litellm(foreground=getattr(args, "foreground", False))
    if target in ("neo4j", "all"):
        _neo4j_start()


def cmd_status(args):
    print("=" * 50)
    print("LiteLLM")
    print("=" * 50)
    pid = get_running_pid()
    if not pid:
        print("  Status : STOPPED")
        print(f"  URL    : {PROXY_URL}")
    else:
        print("  Status : RUNNING")
        print(f"  PID    : {pid}")
        print(f"  URL    : {PROXY_URL}")
        print(f"  Key    : {MASTER_KEY}")
        data = _proxy_get("/v1/models")
        if data:
            print(f"  Health : OK ({len(data.get('data', []))} models)")
        else:
            print("  Health : UNKNOWN")
    print()
    print("Neo4j")
    print("=" * 50)
    if not _neo4j_running():
        print("  Status : STOPPED")
        print(f"  Browser: {NEO4J_BROWSER_URL}  Bolt: bolt://localhost:7687")
    else:
        print("  Status : RUNNING")
        print(f"  Container : {NEO4J_CONTAINER}")
        print(f"  Browser   : {NEO4J_BROWSER_URL}")
        print(f"  Bolt      : bolt://localhost:7687")
        if _neo4j_bolt_ok():
            print("  Health    : OK")
        else:
            print("  Health    : starting...")


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


def cmd_neo4j_reset(args):
    """Wipe Neo4j database (delete all nodes and relationships)."""
    if not _neo4j_running():
        print("[ERROR] Neo4j is not running. Start with: python src/server/manage.py start neo4j")
        sys.exit(1)
    try:
        import yaml
        from neo4j import GraphDatabase
        cfg = yaml.safe_load(NEO4J_CONFIG.read_text()) if NEO4J_CONFIG.exists() else {}
        uri = cfg.get("uri", "bolt://localhost:7687")
        user = cfg.get("user", "neo4j")
        password = cfg.get("password", "dsc288graph")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("[INFO] Neo4j database wiped.")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def cmd_neo4j_shell(args):
    """Print Neo4j browser URL."""
    print(f"Neo4j Browser: {NEO4J_BROWSER_URL}")
    print("Bolt: bolt://localhost:7687  (user: neo4j, password: dsc288graph)")


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DSC288 Server Management (LiteLLM + Neo4j)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start LiteLLM and/or Neo4j")
    p_start.add_argument("service", nargs="?", default="all",
                         choices=["litellm", "neo4j", "all"],
                         help="Which service to start (default: all)")
    p_start.add_argument("-f", "--foreground", action="store_true",
                         help="Run LiteLLM in foreground (don't daemonize)")

    p_stop = sub.add_parser("stop", help="Stop LiteLLM and/or Neo4j")
    p_stop.add_argument("service", nargs="?", default="all",
                        choices=["litellm", "neo4j", "all"],
                        help="Which service to stop (default: all)")

    p_restart = sub.add_parser("restart", help="Restart LiteLLM and/or Neo4j")
    p_restart.add_argument("service", nargs="?", default="all",
                           choices=["litellm", "neo4j", "all"])
    p_restart.add_argument("-f", "--foreground", action="store_true")

    sub.add_parser("status", help="Check status of both servers")

    sub.add_parser("test", help="Run test suite against LiteLLM proxy")

    p_logs = sub.add_parser("logs", help="Show recent LiteLLM logs")
    p_logs.add_argument("-n", "--lines", type=int, default=50,
                        help="Number of lines to show (default: 50)")

    sub.add_parser("models", help="List available LiteLLM models")
    sub.add_parser("health", help="Quick LiteLLM health check")

    p_neo4j = sub.add_parser("neo4j", help="Neo4j subcommands")
    neo4j_sub = p_neo4j.add_subparsers(dest="neo4j_command")
    neo4j_sub.add_parser("reset", help="Wipe Neo4j database")
    neo4j_sub.add_parser("shell", help="Print Neo4j browser URL")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "neo4j":
        if not getattr(args, "neo4j_command", None):
            p_neo4j.print_help()
            sys.exit(0)
        if args.neo4j_command == "reset":
            cmd_neo4j_reset(args)
        elif args.neo4j_command == "shell":
            cmd_neo4j_shell(args)
        return

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
