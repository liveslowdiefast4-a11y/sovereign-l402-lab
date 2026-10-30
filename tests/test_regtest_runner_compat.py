import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "regtest" / "run.sh"


def bash_path():
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    return str(candidate) if candidate.exists() else (shutil.which("bash") or "bash")


FAKE_DOCKER = r'''#!/usr/bin/env python
import json, os, sys, time
from pathlib import Path

state_path = Path(os.environ["FAKE_DOCKER_STATE"])

def load():
    try:
        return json.loads(state_path.read_text())
    except Exception:
        return {"wallet": False, "getinfo": {}, "invoices": {}}

def save(s):
    state_path.write_text(json.dumps(s))

args = sys.argv[1:]
s = load()
if args == ["--version"]:
    print("Docker version fake")
    raise SystemExit(0)
if args[:2] == ["volume", "ls"]:
    raise SystemExit(0)
if args[:2] == ["image", "inspect"]:
    image = args[-1]
    print(image + "@sha256:" + ("1" * 64))
    raise SystemExit(0)
if not args or args[0] != "compose":
    raise SystemExit(2)
rest = args[1:]
if "-f" in rest:
    i = rest.index("-f")
    rest = rest[:i] + rest[i+2:]
if rest[:1] == ["version"]:
    print("Docker Compose version fake")
    raise SystemExit(0)
if rest[:1] in (["pull"], ["up"], ["down"]):
    raise SystemExit(0)
if rest[:2] == ["ps", "-q"]:
    raise SystemExit(0)
if rest[:3] == ["config", "--format", "json"]:
    print(json.dumps({"services": {
        "bitcoind": {"command": ["-regtest=1"]},
        "lnd1": {"command": ["--bitcoin.regtest"]},
        "lnd2": {"command": ["--bitcoin.regtest"]}
    }}))
    raise SystemExit(0)
if rest[:2] != ["exec", "-T"]:
    raise SystemExit(2)
service, cmd = rest[2], rest[3:]
if service == "bitcoind":
    op = next((part for part in cmd[1:] if not part.startswith("-")), "")
    if op == "getblockchaininfo":
        print('{"chain":"regtest"}')
    elif op == "getwalletinfo":
        if not s["wallet"]:
            raise SystemExit(1)
        print("{}")
    elif op == "createwallet":
        s["wallet"] = True; save(s); print("{}")
    elif op == "getnewaddress":
        if not s["wallet"]:
            raise SystemExit(18)
        print("bcrt1fake")
    elif op == "sendtoaddress":
        print("txid")
    else:
        print("[]")
    raise SystemExit(0)
if cmd[:1] == ["sh"]:
    print("interactive create forbidden", file=sys.stderr)
    raise SystemExit(1)
if "lncli" not in cmd:
    raise SystemExit(2)
op_index = cmd.index("lncli") + 2
op = cmd[op_index] if len(cmd) > op_index else ""
tail = cmd[op_index+1:]
node = service
if op == "getinfo":
    n = s["getinfo"].get(node, 0)
    s["getinfo"][node] = n + 1; save(s)
    if n == 0:
        raise SystemExit(1)
    print(json.dumps({"identity_pubkey": "02" + "2"*64, "chains": [{"network":"regtest"}]}))
elif op == "walletbalance":
    print('{"confirmed_balance":"1000000"}')
elif op == "newaddress":
    print('{"address":"bcrt1lnd"}')
elif op == "listchannels":
    print('{"channels":[{"active":true}]}')
elif op in ("connect", "openchannel"):
    print("{}")
elif op == "addinvoice":
    print(json.dumps({"payment_request":"ordinary","r_hash":"ab"*32}))
elif op == "addholdinvoice":
    h = tail[0]; name = {"63":"hold1","72":"hold2","ca":"hold0"}[h[:2]]
    s["invoices"][h] = "OPEN"; save(s)
    print(json.dumps({"payment_request":name}))
elif op == "payinvoice":
    req = tail[-1]
    if req == "ordinary":
        print("{}")
    else:
        h = "630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd" if req == "hold1" else "72dbb7336c76780023f83da4c355f2eeea85733b13d3477697917790c1229084"
        s["invoices"][h] = "ACCEPTED"; save(s)
        for _ in range(200):
            cur = load()["invoices"].get(h)
            if cur == "SETTLED":
                print("{}"); raise SystemExit(0)
            if cur == "CANCELED":
                raise SystemExit(1)
            time.sleep(0.01)
        raise SystemExit(1)
elif op == "lookupinvoice":
    h = tail[0]
    if len(h) != 64:
        raise SystemExit(1)
    if h == "ab"*32:
        print('{"state":"SETTLED"}')
    else:
        print(json.dumps({"state": load()["invoices"].get(h, "OPEN")}))
elif op == "settleinvoice":
    pre = tail[0]
    if pre.startswith("00"):
        h = "630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd"; s["invoices"][h] = "SETTLED"; save(s); print("{}")
    else:
        raise SystemExit(1)
elif op == "cancelinvoice":
    h = tail[0]; s["invoices"][h] = "CANCELED"; save(s); print("{}")
else:
    print("unsupported:" + op, file=sys.stderr)
    raise SystemExit(3)
'''


class RegtestRunnerCompatibilityTests(unittest.TestCase):
    def test_runner_handles_current_pinned_cli_and_writes_bound_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bindir = tmp / "bin"
            bindir.mkdir()
            docker = bindir / "docker"
            docker.write_text(FAKE_DOCKER, encoding="utf-8")
            docker.chmod(0o755)
            sleep = bindir / "sleep"
            sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            sleep.chmod(0o755)
            evidence = tmp / "evidence.json"
            env = os.environ.copy()
            env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
            env["FAKE_DOCKER_STATE"] = str(tmp / "state.json")
            env["EVIDENCE_FILE"] = str(evidence)
            result = subprocess.run(
                [bash_path(), str(RUNNER)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(report["network"], "regtest")
            self.assertEqual(report["result"], "PASS")
            self.assertEqual(len(report["events"]), 6)


if __name__ == "__main__":
    unittest.main()
