#!/usr/bin/env bash
# Prepare a private runtime if needed, fetch source without Git, install one host.
set -euo pipefail
source_dir=""
managed=0
forward=()
while (($#)); do
  case "$1" in
    --source) source_dir="$2"; shift 2 ;;
    --managed-python) managed=1; shift ;;
    *) forward+=("$1"); shift ;;
  esac
done
runtime_root="${GOALPILOT_RUNTIME_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/goalpilot/runtime}"
python_exec=""
if ((managed == 0)); then
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if found="$("$candidate" -c 'import sys; sys.exit(1) if sys.version_info<(3,11) else print(sys.executable)' 2>/dev/null)"; then
        python_exec="$found"; break
      fi
    fi
  done
fi
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
if [[ -z "$python_exec" ]]; then
  mkdir -p "$runtime_root/bin"
  if command -v uv >/dev/null 2>&1; then
    uv_exec="$(command -v uv)"
  elif [[ -x "$runtime_root/bin/uv" ]]; then
    uv_exec="$runtime_root/bin/uv"
  else
    curl --fail --silent --show-error --location https://astral.sh/uv/install.sh --output "$scratch/uv-install.sh"
    UV_INSTALL_DIR="$runtime_root/bin" UV_NO_MODIFY_PATH=1 sh "$scratch/uv-install.sh" >&2
    uv_exec="$runtime_root/bin/uv"
  fi
  export UV_PYTHON_INSTALL_DIR="$runtime_root/python"
  "$uv_exec" python install 3.12 --quiet >&2
  python_exec="$("$uv_exec" python find --managed-python 3.12)"
fi
if [[ -z "$source_dir" ]]; then
  curl --fail --silent --show-error --location https://github.com/InfinitySpeed/goalpilot/archive/refs/heads/main.tar.gz --output "$scratch/source.tar.gz"
  mkdir "$scratch/source"
  tar -xzf "$scratch/source.tar.gz" -C "$scratch/source" --strip-components=1
  source_dir="$scratch/source"
fi
export PYTHONUTF8=1
"$python_exec" -X utf8 "$source_dir/install.py" "${forward[@]}"
