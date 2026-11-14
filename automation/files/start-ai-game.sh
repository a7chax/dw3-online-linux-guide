#!/usr/bin/env bash
set -euo pipefail
umask 077
game_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
mkdir -p "$game_dir/linux/ai-sessions"
session_dir=$(mktemp -d "$game_dir/linux/ai-sessions/session.XXXXXXXX")
ln -s "$session_dir" "$game_dir/linux/ai-sessions/.latest-$$"
mv -Tf "$game_dir/linux/ai-sessions/.latest-$$" "$game_dir/linux/ai-sessions/latest"
export DW3_PRINT_STATE=1
export DW3_STATE_FILE="$session_dir/state.json"
export DW3_CONTROL_SOCKET="$session_dir/control.sock"
printf 'State file: %s\n' "$DW3_STATE_FILE"
exec "$game_dir/DW3-Online-Linux" "$@"
