#!/usr/bin/env sh
set -eu

YES=0
if [ "${1:-}" = "-y" ] || [ "${1:-}" = "--yes" ]; then
  YES=1
fi

ask_yes_no() {
  question="$1"
  default="${2:-yes}"
  if [ "$YES" -eq 1 ]; then
    return 0
  fi
  if [ "$default" = "yes" ]; then
    prompt="[Y/n]"
  else
    prompt="[y/N]"
  fi
  printf "%s %s " "$question" "$prompt"
  read answer
  if [ -z "$answer" ]; then
    [ "$default" = "yes" ]
    return
  fi
  case "$answer" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$repo_root"

echo "NightShift setup"
echo "Repo: $repo_root"

if has_command python3; then
  PYTHON=python3
elif has_command python; then
  PYTHON=python
else
  echo "Python was not found on PATH. Install Python 3.11+ and rerun setup.sh." >&2
  exit 1
fi

echo "Python: $($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

echo "Installing NightShift in editable mode..."
$PYTHON -m pip install -e .

scripts_dir=$($PYTHON -c 'import sysconfig, os; print(sysconfig.get_path("scripts", scheme="posix_user") or sysconfig.get_path("scripts"))')
case ":$PATH:" in
  *":$scripts_dir:"*)
    echo "PATH already includes Python scripts directory."
    ;;
  *)
    if ask_yes_no "Add Python scripts directory to PATH in your shell profile? $scripts_dir" "yes"; then
      shell_name=$(basename "${SHELL:-sh}")
      case "$shell_name" in
        zsh) profile="$HOME/.zshrc" ;;
        bash) profile="$HOME/.bashrc" ;;
        *) profile="$HOME/.profile" ;;
      esac
      line="export PATH=\"$scripts_dir:\$PATH\""
      if [ -f "$profile" ] && grep -F "$scripts_dir" "$profile" >/dev/null 2>&1; then
        echo "Profile already mentions $scripts_dir"
      else
        printf "\n# NightShift CLI\n%s\n" "$line" >> "$profile"
        echo "Added PATH update to $profile"
      fi
      export PATH="$scripts_dir:$PATH"
    else
      echo "Skipped PATH update. You can still run: $PYTHON -m nightshift.cli"
    fi
    ;;
esac

if has_command nightshift; then
  echo "NightShift CLI is available:"
  nightshift --help | sed -n '1,5p'
else
  echo "NightShift CLI is not visible in this shell yet. Open a new terminal or run: $PYTHON -m nightshift.cli --help"
fi

if has_command ollama; then
  echo "Ollama is installed:"
  ollama --version
else
  echo "Ollama was not found."
  os_name=$(uname -s 2>/dev/null || echo unknown)
  if [ "$os_name" = "Darwin" ] && has_command brew; then
    if ask_yes_no "Install Ollama with Homebrew now?" "yes"; then
      brew install ollama
    else
      echo "Skipped Ollama install. Install later from https://ollama.com/download"
    fi
  elif [ "$os_name" = "Linux" ]; then
    if ask_yes_no "Install Ollama with the official install script now?" "no"; then
      curl -fsSL https://ollama.com/install.sh | sh
    else
      echo "Skipped Ollama install. Install later from https://ollama.com/download"
    fi
  else
    echo "Install Ollama from https://ollama.com/download"
  fi
fi

echo ""
echo "Setup complete."
echo "Validate this repo with: nightshift validate"
echo "Start the dashboard with: nightshift web"
