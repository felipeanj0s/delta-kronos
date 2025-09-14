#!/usr/bin/env bash
# scripts/ci/ensure_ssh_key.sh
set -euo pipefail

: "${SSH_PRIVATE_KEY:?Env SSH_PRIVATE_KEY não definido}"

REPO_ROOT="$(pwd)"
SSH_DIR="$REPO_ROOT/ansible/.ssh"
KEY_PATH="$SSH_DIR/id_rsa"
CONFIG_PATH="$SSH_DIR/config"
KNOWN_HOSTS_PATH="$SSH_DIR/known_hosts"

# 1) Diretório e permissões
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

# 2) Grava a chave privada (600)
printf "%s" "$SSH_PRIVATE_KEY" > "$KEY_PATH"
chmod 600 "$KEY_PATH"

# 3) known_hosts (cria vazio, 644)
touch "$KNOWN_HOSTS_PATH"
chmod 644 "$KNOWN_HOSTS_PATH"

# 4) ssh_config apontando para os caminhos do repositório
cat > "$CONFIG_PATH" <<CFG
Host *
  IdentitiesOnly yes
  IdentityFile $KEY_PATH
  UserKnownHostsFile $KNOWN_HOSTS_PATH
  ServerAliveInterval 30
  StrictHostKeyChecking accept-new
CFG
chmod 600 "$CONFIG_PATH"

# 5) (Opcional) Semear known_hosts se HOST(es) informados (vírgula/space-separated)
if [[ -n "${HOST:-}" ]]; then
  IFS=', ' read -r -a _hosts <<< "${HOST}"
  for h in "${_hosts[@]}"; do
    [[ -z "$h" ]] && continue
    ssh-keyscan -T 5 -H "$h" >> "$KNOWN_HOSTS_PATH" 2>/dev/null || true
  done
fi

echo "[ok] chave privada em $KEY_PATH | config em $CONFIG_PATH | known_hosts em $KNOWN_HOSTS_PATH"
