#!/usr/bin/env bash
# scripts/ci/ensure_ssh_key.sh
set -euo pipefail

: "${SSH_PRIVATE_KEY:?Env SSH_PRIVATE_KEY não definido}"

SSH_DIR="ansible/.ssh"
KEY_PATH="$SSH_DIR/id_rsa"
CONFIG_PATH="$SSH_DIR/config"
KNOWN_HOSTS_PATH="$SSH_DIR/known_hosts"

# 1) Diretório e permissões
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

# 2) Grava a chave privada (600)
printf "%s" "$SSH_PRIVATE_KEY" > "$KEY_PATH"
chmod 600 "$KEY_PATH"

# 3) ssh_config mínimo para uso pelo Ansible
cat > "$CONFIG_PATH" <<'CFG'
Host *
  IdentitiesOnly yes
  IdentityFile ~/.ssh/id_rsa
  ServerAliveInterval 30
  # Em lab: aceita primeira conexão; em prod prefira known_hosts pré-populado
  StrictHostKeyChecking accept-new
CFG
chmod 600 "$CONFIG_PATH"

# 4) (Opcional) Semear known_hosts se HOST for informado
#    Use no pipeline: HOST=192.0.2.10 ./scripts/ci/ensure_ssh_key.sh
if [[ "${HOST:-}" != "" ]]; then
  mkdir -p "$SSH_DIR"
  touch "$KNOWN_HOSTS_PATH"
  chmod 644 "$KNOWN_HOSTS_PATH"
  # -H: hash, -T: timeout
  ssh-keyscan -T 5 -H "$HOST" >> "$KNOWN_HOSTS_PATH" 2>/dev/null || true
fi

echo "[ok] chave privada escrita em $KEY_PATH"
