#!/usr/bin/env bash
# Install Ears for this user: a Python venv, the launchers and the Claude Code skill.
# No sudo. Works on macOS and Linux. Missing optional tools are skipped and named.
#
#   ./install.sh                 # launchers in ~/.claude/bin, skill in ~/.claude/skills/ears
#   EARS_BIN=~/bin ./install.sh  # put the launchers somewhere else
#   ./install.sh --with-uv       # no venv/pip and no sudo: fetch uv into .tools/ first
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd)
bin=${EARS_BIN:-$HOME/.claude/bin}
skills=${EARS_SKILLS:-$HOME/.claude/skills}
venv="$repo/.venv"
missing=()

say() { printf 'ears install: %s\n' "$*"; }

# 0. Optional: with --with-uv, fetch uv into this folder (.tools/) when there is no uv and no
#    working venv/pip (for example Debian/Ubuntu without the python3-venv package, and no sudo).
if [[ "${1:-}" == "--with-uv" ]] && ! command -v uv >/dev/null 2>&1; then
  case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) t=x86_64-unknown-linux-gnu ;;
  Linux-aarch64) t=aarch64-unknown-linux-gnu ;;
  Darwin-arm64) t=aarch64-apple-darwin ;;
  Darwin-x86_64) t=x86_64-apple-darwin ;;
  *) say "--with-uv: no uv build known for $(uname -sm)"; exit 1 ;;
  esac
  mkdir -p "$repo/.tools"
  say "fetching uv ($t) into $repo/.tools"
  curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-$t.tar.gz" |
    tar -xz -C "$repo/.tools" --strip-components 1
  export PATH="$repo/.tools:$PATH" UV_CACHE_DIR="$repo/.tools/cache"
fi
[[ -x "$repo/.tools/uv" ]] && export PATH="$repo/.tools:$PATH" UV_CACHE_DIR="$repo/.tools/cache"

# 1. Python venv. Prefer uv (fast, can fetch a Python); else the newest python3 with venv.
if [[ ! -x "$venv/bin/python" ]]; then
  if command -v uv >/dev/null 2>&1; then
    say "making the venv with uv"
    uv venv -q "$venv"
  else
    py=""
    for c in python3.13 python3.12 python3.14 python3.11 python3; do
      if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys, venv, ensurepip; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
        py=$c
        break
      fi
    done
    if [[ -z "$py" ]]; then
      say "no Python 3.9+ with venv/ensurepip found. Install Python 3 with venv, or uv,"
      say "or run ./install.sh --with-uv to fetch uv into this folder (no sudo)."
      exit 1
    fi
    say "making the venv with $py"
    "$py" -m venv "$venv"
  fi
fi
say "installing Python packages (numpy, scipy, soundfile, matplotlib, pyloudnorm)"
if command -v uv >/dev/null 2>&1; then
  uv pip install -q -p "$venv/bin/python" -r "$repo/requirements.txt"
else
  "$venv/bin/python" -m pip install -q --upgrade pip
  "$venv/bin/python" -m pip install -q -r "$repo/requirements.txt"
fi
"$venv/bin/python" -c "import numpy, scipy, soundfile, matplotlib, pyloudnorm" || {
  say "the Python packages did not import. See the errors above."
  exit 1
}

# 2. Launchers.
mkdir -p "$bin"
write() { # name, command line
  printf '#!/usr/bin/env bash\n# Ears launcher (made by %s/install.sh)\nexec %s "$@"\n' "$repo" "$2" >"$bin/$1"
  chmod +x "$bin/$1"
}
write ears "\"$venv/bin/python\" \"$repo/ears.py\""
write ears-adb "\"$repo/ears-adb\""
if command -v node >/dev/null 2>&1; then
  write ears-page "node \"$repo/ears-page.mjs\""
else
  missing+=("node (needed only for ears-page)")
fi
say "launchers in $bin: ears, ears-adb$([[ -x $bin/ears-page ]] && echo ', ears-page')"

# 3. Claude Code skill.
mkdir -p "$skills/ears"
cp "$repo/skill/SKILL.md" "$skills/ears/SKILL.md"
say "skill in $skills/ears/SKILL.md"

# 4. Optional tools: report what is missing.
command -v ffmpeg >/dev/null 2>&1 || missing+=("ffmpeg (for .mp3 and other files soundfile cannot read; .wav/.ogg/.flac work without it)")
if command -v node >/dev/null 2>&1; then
  if ! node -e 'require.resolve("playwright-core")' >/dev/null 2>&1 &&
    ! node -e 'require.resolve("playwright")' >/dev/null 2>&1 &&
    [[ -z "${EARS_PLAYWRIGHT:-}" ]] &&
    ! ls "$(npm root -g 2>/dev/null)"/playwright* >/dev/null 2>&1; then
    missing+=("Playwright for ears-page (npm i -g playwright-core, or set EARS_PLAYWRIGHT)")
  fi
fi
command -v adb >/dev/null 2>&1 || missing+=("adb (for ears-adb)")
command -v scrcpy >/dev/null 2>&1 || missing+=("scrcpy 2.0+ (for ears-adb)")
if ((${#missing[@]})); then
  say "skipped, not found:"
  for m in "${missing[@]}"; do printf '  - %s\n' "$m"; done
fi
case ":$PATH:" in
*":$bin:"*) ;;
*) say "note: $bin is not on your PATH. Add: export PATH=\"$bin:\$PATH\"" ;;
esac
say "done. Try: ears $repo/examples/tick.wav"
