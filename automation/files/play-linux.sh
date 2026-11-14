#!/usr/bin/env bash
set -euo pipefail

game_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$game_dir"

fail() { printf '%s\n' "$*" >&2; exit 1; }

[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] ||
    fail 'This launcher includes native libraries for Linux x86_64 only.'

java_bin=java
if [[ -n ${JAVA_HOME:-} ]]; then
    java_bin="$JAVA_HOME/bin/java"
fi
command -v "$java_bin" >/dev/null 2>&1 ||
    fail 'Install a Linux Java 17 or newer runtime, or set JAVA_HOME.'
java_version=$("$java_bin" -version 2>&1) || fail 'Java could not start.'
java_major=$(sed -nE 's/.*version "([0-9]+).*/\1/p' <<< "$java_version" | head -n1)
[[ $java_major =~ ^[0-9]+$ ]] && ((java_major >= 17)) ||
    fail 'This game requires Linux Java 17 or newer.'

[[ -f app/client.jar && -f data/data.pak ]] ||
    fail 'Keep this launcher beside the original app/ and data/ directories.'

classpath=''
for jar in "$game_dir"/app/*.jar; do
    case "$jar" in *-natives-windows*.jar) continue ;; esac
    classpath+="${classpath:+:}$jar"
done
for module in lwjgl lwjgl-glfw lwjgl-jemalloc lwjgl-openal lwjgl-opengl lwjgl-opengles lwjgl-stb; do
    jar="$game_dir/linux/lib/$module-3.3.3-natives-linux.jar"
    [[ -f $jar ]] || fail "Missing Linux dependency: $jar"
    classpath+=":$jar"
done

[[ -f linux/lib/libdwcofre.so && -f linux/lib/dw3-android-bridge.jar ]] || fail \
'The APK native adapter is missing. Rebuild it with:
    uv run --locked python linux/native/build.py
See README-LINUX.md for requirements.'
classpath="$game_dir/linux/lib/dw3-android-bridge.jar:$classpath"

if [[ ${1:-} == --check ]]; then
    exec "$java_bin" "-Djava.library.path=$game_dir/linux/lib" \
        -cp "$classpath" dw3.linux.NativeCheck
fi

[[ -n ${DISPLAY:-} || -n ${WAYLAND_DISPLAY:-} ]] ||
    fail 'Launch this game from a graphical Linux desktop.'

# The Java bootstrap reserves a separate persistent home for each open client.
mkdir -p "$game_dir/.linux-home"
exec "$java_bin" \
    "-Duser.home=$game_dir/.linux-home" \
    "-Djava.library.path=$game_dir/linux/lib:$game_dir/app" \
    -Djpackage.app-version=1.0.0 \
    -XX:+DisableAttachMechanism \
    -cp "$classpath" dw3.linux.DesktopLauncher "$@"
