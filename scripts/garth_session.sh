#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

export GARTH_HOME="${GARTH_HOME:-$HOME/.garth-debug-garmin}"
OAUTH1="$GARTH_HOME/oauth1_token.json"
OAUTH2="$GARTH_HOME/oauth2_token.json"

usage() {
  cat <<'EOF'
Usage:
  scripts/garth_session.sh login
  scripts/garth_session.sh check
  scripts/garth_session.sh close
  scripts/garth_session.sh run <command...>

Behavior:
  - Uses GARTH_HOME if set, otherwise defaults to ~/.garth-debug-garmin
  - login: prompts credentials once and saves tokens
  - check: prints token sizes and validates garth.resume()
  - close: removes token files (explicit logout)
  - run: executes any command with the same GARTH_HOME exported
EOF
}

token_size() {
  local file="$1"
  if [ -f "$file" ]; then
    wc -c < "$file" | tr -d ' '
  else
    echo "0"
  fi
}

check_session() {
  if [ ! -f "$OAUTH1" ] || [ ! -f "$OAUTH2" ]; then
    return 1
  fi
  if [ "$(token_size "$OAUTH1")" -eq 0 ] || [ "$(token_size "$OAUTH2")" -eq 0 ]; then
    return 1
  fi
  env -u GARTH_HOME -u GARTH_TOKEN "$VENV_PY" -c "import garth; garth.resume('$GARTH_HOME')" >/dev/null 2>&1
}

cmd="${1:-}"
case "$cmd" in
  login)
    mkdir -p "$GARTH_HOME"
    if check_session; then
      echo "GARTH_SESSION_ALREADY_ACTIVE"
      echo "GARTH_HOME=$GARTH_HOME"
      exit 0
    fi
    env -u GARTH_HOME -u GARTH_TOKEN "$VENV_PY" -c "import garth,getpass; email=input('Email: '); password=getpass.getpass('Password: '); garth.login(email,password); garth.save('$GARTH_HOME'); print('GARTH_SAVED_OK')"
    if check_session; then
      echo "GARTH_SESSION_READY"
      echo "GARTH_HOME=$GARTH_HOME"
      echo "oauth1_bytes=$(token_size "$OAUTH1")"
      echo "oauth2_bytes=$(token_size "$OAUTH2")"
      exit 0
    fi
    echo "GARTH_SESSION_INVALID_AFTER_LOGIN"
    exit 1
    ;;
  check)
    mkdir -p "$GARTH_HOME"
    echo "GARTH_HOME=$GARTH_HOME"
    echo "oauth1_bytes=$(token_size "$OAUTH1")"
    echo "oauth2_bytes=$(token_size "$OAUTH2")"
    if check_session; then
      echo "GARTH_RESUME_OK"
      exit 0
    fi
    echo "GARTH_RESUME_ERR"
    exit 1
    ;;
  close)
    rm -f "$OAUTH1" "$OAUTH2"
    echo "GARTH_SESSION_CLOSED"
    echo "GARTH_HOME=$GARTH_HOME"
    ;;
  run)
    shift || true
    if [ "$#" -eq 0 ]; then
      usage
      exit 1
    fi
    exec env GARTH_HOME="$GARTH_HOME" "$@"
    ;;
  *)
    usage
    exit 1
    ;;
esac
