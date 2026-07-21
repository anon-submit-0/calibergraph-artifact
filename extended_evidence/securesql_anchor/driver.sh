#!/bin/zsh
# Sequential experiment driver (protocol.md v1.0 + Amendment 1).
# Each phase loops (bounded) until its resumable artifact is complete.
set -u
cd "$(dirname "$0")"

log() { echo "[driver $(date '+%H:%M:%S')] $*"; }

# ---------- phase 1: entity extraction (retry until all groups have non-error rows)
for pass in 1 2 3 4 5 6 7 8; do
  log "entities pass $pass"
  python3 perturb.py entities
  missing=$(python3 - <<'EOF'
import json, perturb, common
groups = set(perturb.groups_covering_subsample().keys())
done = {(r["db_id"], r["security_condition"]) for r in common.read_jsonl(perturb.ENTITIES_RAW) if not r.get("error")}
print(len(groups - done))
EOF
)
  log "entities missing=$missing"
  [ "$missing" = "0" ] && break
  sleep 30
done
[ "$missing" != "0" ] && { log "ENTITIES INCOMPLETE after retries — aborting honestly"; exit 2; }

# ---------- phase 2: apply perturbation (deterministic)
python3 perturb.py apply || { log "perturb apply failed"; exit 2; }

# ---------- phase 3: compiler canary (2/2 gate, retry pass on infra failure)
canary_ok=0
for pass in 1 2 3 4 5; do
  log "compiler canary pass $pass"
  if python3 compile_policies.py canary; then canary_ok=1; break; fi
  sleep 60
done
[ "$canary_ok" = "1" ] || { log "compiler canary gate failed"; exit 2; }

# ---------- phase 4: compile original + perturbed (resumable loops)
for target in compile compile-perturbed; do
  for pass in 1 2 3 4 5 6; do
    log "$target pass $pass"
    python3 compile_policies.py $target
    left=$(python3 - "$target" <<'EOF'
import json, sys
import common, compile_policies as cp
if sys.argv[1] == "compile":
    pairs = [(db, c) for db, c in cp.unique_conditions()]
    raw = "compile_original.jsonl"
else:
    pmap = json.loads((cp.HERE / "perturbation_map.json").read_text())
    pairs = [(v["db_id"], v["original_condition"]) for v in pmap.values()]
    raw = "compile_perturbed.jsonl"
done = {(r["db_id"], r["security_condition_key"]) for r in common.read_jsonl(cp.RAW / "compiler" / raw) if not r.get("error")}
print(sum(1 for p in pairs if p not in done))
EOF
)
    log "$target remaining=$left"
    [ "$left" = "0" ] && break
    sleep 30
  done
  [ "$left" != "0" ] && { log "$target INCOMPLETE — aborting honestly"; exit 2; }
done

# ---------- phase 5: deterministic checker
python3 checker.py original || exit 2
python3 checker.py perturbed || exit 2

# ---------- phase 6: arm B canary + runs
canary_ok=0
for pass in 1 2 3 4 5; do
  log "armB canary pass $pass"
  if python3 run_armB.py canary; then canary_ok=1; break; fi
  sleep 60
done
[ "$canary_ok" = "1" ] || { log "armB canary gate failed"; exit 2; }

for s in original perturbed; do
  for pass in 1 2 3 4 5 6; do
    log "armB $s pass $pass"
    python3 run_armB.py run --set $s
    left=$(python3 - "$s" <<'EOF'
import json, sys
import common
from common import HERE, RAW
ids = set(json.loads((HERE / "subsample_300.json").read_text())["ids"])
done = {r["id"] for r in common.read_jsonl(RAW / "armB" / f"{sys.argv[1]}.jsonl") if not r.get("error")}
print(len(ids - done))
EOF
)
    log "armB $s remaining=$left"
    [ "$left" = "0" ] && break
    sleep 30
  done
done

# ---------- phase 7: score (works with whatever completed; failures listed honestly)
python3 score.py || exit 2
log "DONE"
