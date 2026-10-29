#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/regtest/docker-compose.yml"
EVIDENCE_FILE="${EVIDENCE_FILE:-$ROOT/regtest-evidence.json}"
export COMPOSE_PROJECT_NAME="sovereign_l402_regtest"

dc() { docker compose -f "$COMPOSE_FILE" "$@"; }
btc() { dc exec -T bitcoind bitcoin-cli -regtest -rpcuser=regtest -rpcpassword=regtest-only "$@"; }
ln() { local node="$1"; shift; dc exec -T "$node" lncli --network=regtest "$@"; }
field() { python -c 'import json,sys; v=json.load(sys.stdin); print(v[sys.argv[1]])' "$1"; }
hexfield() { python -c 'import base64,json,sys; print(base64.b64decode(json.load(sys.stdin)[sys.argv[1]]).hex())' "$1"; }
cleanup() { dc down --volumes --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

wait_for() {
  local label="$1"; shift
  for _ in $(seq 1 120); do "$@" >/dev/null 2>&1 && return 0; sleep 1; done
  echo "timeout waiting for $label" >&2; return 1
}

init_wallet() {
  local node="$1"
  if ln "$node" getinfo >/dev/null 2>&1; then return; fi
  dc exec -T "$node" sh -c "printf 'regtest-only-password\nregtest-only-password\nn\n\n\n' | lncli --network=regtest create >/dev/null 2>&1"
  wait_for "$node wallet" ln "$node" getinfo
}

invoice_state() { ln "$1" lookupinvoice "$2" | field state; }
lnd1_funded() { [[ "$(ln lnd1 walletbalance | field confirmed_balance)" -gt 0 ]]; }
active_channel() {
  ln lnd1 listchannels | python -c 'import json,sys; raise SystemExit(0 if any(c["active"] for c in json.load(sys.stdin)["channels"]) else 1)'
}
wait_state() {
  local node="$1" hash="$2" expected="$3"
  for _ in $(seq 1 90); do
    [[ "$(invoice_state "$node" "$hash" 2>/dev/null || true)" == "$expected" ]] && return 0
    sleep 1
  done
  echo "invoice $hash did not reach $expected" >&2; return 1
}

cleanup
dc pull
dc up -d
wait_for bitcoind btc getblockchaininfo
[[ "$(btc getblockchaininfo | field chain)" == "regtest" ]] || { echo "refusing non-regtest chain" >&2; exit 1; }
init_wallet lnd1
init_wallet lnd2
[[ "$(ln lnd1 getinfo | python -c 'import json,sys; print(json.load(sys.stdin)["chains"][0]["network"])')" == "regtest" ]] || exit 1
[[ "$(ln lnd2 getinfo | python -c 'import json,sys; print(json.load(sys.stdin)["chains"][0]["network"])')" == "regtest" ]] || exit 1

miner="$(btc getnewaddress)"
btc generatetoaddress 110 "$miner" >/dev/null
addr1="$(ln lnd1 newaddress p2wkh | field address)"
btc sendtoaddress "$addr1" 0.02 >/dev/null
btc generatetoaddress 6 "$miner" >/dev/null
wait_for lnd1_funds lnd1_funded

pub2="$(ln lnd2 getinfo | field identity_pubkey)"
ln lnd1 connect "${pub2}@lnd2:9735" >/dev/null
ln lnd1 openchannel --node_key "$pub2" --local_amt 1000000 --push_amt 200000 >/dev/null
btc generatetoaddress 6 "$miner" >/dev/null
wait_for active_channel active_channel

ordinary="$(ln lnd2 addinvoice --amt 1000)"
ordinary_request="$(printf '%s' "$ordinary" | field payment_request)"
ordinary_hash="$(printf '%s' "$ordinary" | hexfield r_hash)"
ln lnd1 payinvoice --force "$ordinary_request" >/dev/null
wait_state lnd2 "$ordinary_hash" SETTLED

preimage1=000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
hash1=630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd
hold1="$(ln lnd2 invoices addholdinvoice "$hash1" --amt 1000)"
hold_request1="$(printf '%s' "$hold1" | field payment_request)"
(ln lnd1 payinvoice --force --timeout 60s "$hold_request1" >/dev/null 2>&1 || true) &
pay_pid1=$!
wait_state lnd2 "$hash1" ACCEPTED
ln lnd2 invoices settleinvoice "$preimage1" >/dev/null
wait "$pay_pid1"
wait_state lnd2 "$hash1" SETTLED

hash2=72dbb7336c76780023f83da4c355f2eeea85733b13d3477697917790c1229084
hold2="$(ln lnd2 invoices addholdinvoice "$hash2" --amt 1000)"
hold_request2="$(printf '%s' "$hold2" | field payment_request)"
(ln lnd1 payinvoice --force --timeout 60s "$hold_request2" >/dev/null 2>&1 || true) &
pay_pid2=$!
wait_state lnd2 "$hash2" ACCEPTED
ln lnd2 invoices cancelinvoice "$hash2" >/dev/null
wait "$pay_pid2" || true
wait_state lnd2 "$hash2" CANCELED

python "$ROOT/regtest/write_evidence.py" "$EVIDENCE_FILE" "$(git -C "$ROOT" rev-parse HEAD)"
python -m sovereign_l402.evidence "$EVIDENCE_FILE"
echo "real-node regtest evidence: PASS"

