#!/usr/bin/env bash
set -euo pipefail

: "${SSH_PRIVATE_KEY:?Env SSH_PRIVATE_KEY não definido}"

mkdir -p ansible/.ssh
chmod 700 ansible/.ssh

# grava chave
printf "%s" "$SSH_PRIVATE_KEY" > ansible/.ssh/id_rsa
chmod 600 ansible/.ssh/id_rsa

# ssh_config local p/ execução do Ansible
cat > ansible/.ssh/config <<'CFG'
Host *
  IdentitiesOnly yes
  IdentityFile ~/.ssh/id_rsa
  ServerAliveInterval 30
  StrictHostKeyChecking accept-new
CFG
chmod 600 ansible/.ssh/config

echo "[ok] SSH key escrita em ansible/.ssh/id_rsa"
