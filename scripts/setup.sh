#!/usr/bin/env bash
# Kumo setup: render infra configs (LiveKit + coturn) from .env.
# Run from anywhere: it resolves the repository root automatically.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example." >&2
  echo "Edit .env and fill in all secrets, then rerun ./scripts/setup.sh." >&2
  exit 1
fi

# Load KEY=value lines from .env (comments and blank lines are ignored).
set -a
# shellcheck disable=SC1091
source .env
set +a

# Escape backslashes, ampersands and the sed delimiter before substitution.
escape_sed() { printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'; }

sed \
  -e "s|\${LIVEKIT_API_KEY}|$(escape_sed "${LIVEKIT_API_KEY:-}")|g" \
  -e "s|\${LIVEKIT_API_SECRET}|$(escape_sed "${LIVEKIT_API_SECRET:-}")|g" \
  infra/livekit.yaml.example > infra/livekit.yaml

sed \
  -e "s|\${TURN_USERNAME}|$(escape_sed "${TURN_USERNAME:-}")|g" \
  -e "s|\${TURN_CREDENTIAL}|$(escape_sed "${TURN_CREDENTIAL:-}")|g" \
  infra/turnserver.conf.example > infra/turnserver.conf

chmod 600 infra/livekit.yaml infra/turnserver.conf

if [[ -z "${LIVEKIT_API_KEY:-}" || -z "${LIVEKIT_API_SECRET:-}" || -z "${TURN_CREDENTIAL:-}" ]]; then
  echo "warning: LIVEKIT_API_KEY / LIVEKIT_API_SECRET / TURN_CREDENTIAL are empty in .env;" >&2
  echo "         group audio and TURN relay will not work until they are set." >&2
fi

echo "Generated infra/livekit.yaml and infra/turnserver.conf from .env"
