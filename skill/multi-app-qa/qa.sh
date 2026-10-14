#!/usr/bin/env bash
# Universal entry point. Works on any app suite, any persona.
#
#   ./qa.sh ./export                      # bootstrap config, then check
#   ./qa.sh ./export brief.md             # use the brief as ground truth
#   ./qa.sh ./export brief.md qa-config.json   # reuse an edited config
#
# Stops after bootstrapping so you can adjudicate the config before the
# findings depend on it. Re-run with the config path to continue.

set -euo pipefail

EXPORT="${1:?usage: ./qa.sh <export-dir> [brief] [config]}"
BRIEF="${2:-}"
CONFIG="${3:-}"
OUT="${OUT:-./qa-run}"
PY="${PYTHON:-python3}"

cd "$(dirname "$0")"
mkdir -p "$OUT"

if [ -z "$CONFIG" ]; then
  CONFIG="$OUT/qa-config.json"
  echo "→ bootstrapping config from the environment"
  if [ -n "$BRIEF" ]; then
    $PY scripts/bootstrap_config.py --in "$EXPORT" --brief "$BRIEF" --out "$CONFIG"
  else
    $PY scripts/bootstrap_config.py --in "$EXPORT" --out "$CONFIG"
  fi
  cat <<EOF

Draft config written to $CONFIG

Work the "_confirm" list at the top of that file before continuing. The two
that always matter:

  persona_start / environment_today  — inferred from the data's own min and
      max, which means any out-of-window record silently widened the window
      it was supposed to violate. Set these from the brief.

  roster kinds  — entries left as "unknown" are invisible to the
      category-mismatch check.

Then run:
  ./qa.sh "$EXPORT" "${BRIEF:-}" "$CONFIG"
EOF
  exit 0
fi

echo "→ running checks with $CONFIG"
$PY scripts/run_all.py --in "$EXPORT" --config "$CONFIG" --out "$OUT"

cat <<EOF

Automated pass done. Manual passes remain — see RUNBOOK.md steps 4-8 for the
agent prompts (Chronologist, Voice Critic, Scrubber, UI Prober, Editor).
EOF
