#!/usr/bin/env bash
set -euo pipefail

game_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd -- "$game_dir"

gcc -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
    -o DW3-Online-Linux linux/native/launcher.c

runtime_needs_build=true
if [[ -x linux/runtime/bin/java ]]; then
    runtime_modules=$(linux/runtime/bin/java --list-modules)
    if [[ $'\n'"$runtime_modules" == *$'\n'jdk.charsets@* ]]; then
        runtime_needs_build=false
    fi
fi

if [[ $runtime_needs_build == true ]]; then
    if [[ -e linux/runtime && ! -x linux/runtime/bin/java ]]; then
        printf '%s\n' 'linux/runtime exists but has no executable bin/java. Move that incomplete directory aside, then rebuild.' >&2
        exit 1
    fi
    if [[ $(jlink --version) != 21.* ]]; then
        printf '%s\n' 'Use a JDK 21 jlink on PATH to build the bundled Java 21 runtime.' >&2
        exit 1
    fi
    runtime_build=$(mktemp -d "$game_dir/linux/.runtime-build.XXXXXX")
    trap 'rm -rf -- "$runtime_build"' EXIT
    jlink --add-modules \
        java.base,java.datatransfer,java.xml,java.prefs,java.desktop,java.logging,java.management,java.net.http,java.transaction.xa,java.sql,jdk.charsets,jdk.crypto.ec,jdk.unsupported \
        --strip-debug --no-header-files --no-man-pages --compress=zip-6 \
        --output "$runtime_build/runtime"
    uv run --locked python - "$runtime_build/runtime" "$game_dir/linux/runtime" <<'PY'
import ctypes
import os
from pathlib import Path
import sys
import uuid

candidate, destination = map(Path, sys.argv[1:])
if destination.exists():
    # Exchange directories atomically. Running clients keep their existing files,
    # and new launches always see a complete runtime at the usual path.
    library = ctypes.CDLL(None, use_errno=True)
    exchange = library.renameat2
    exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    exchange.restype = ctypes.c_int
    if exchange(-100, os.fsencode(candidate), -100, os.fsencode(destination), 2) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    backup = destination.with_name("runtime.previous-" + uuid.uuid4().hex[:12])
    os.rename(candidate, backup)
    print("Previous runtime retained at", backup)
else:
    os.rename(candidate, destination)
PY
fi

./DW3-Online-Linux --check
printf 'Built DW3-Online-Linux with a bundled Linux Java runtime.\n'
