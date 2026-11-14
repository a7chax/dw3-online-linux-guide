#!/usr/bin/env bash
set -euo pipefail

game_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export DW3_PRINT_STATE=1
exec "$game_dir/DW3-Online-Linux" "$@"
