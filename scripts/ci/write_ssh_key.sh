#!/usr/bin/env bash
set -euo pipefail

: "${SSH_PRIVATE_KEY:?Env SSH_PRIVATE_KEY não definido}"

mkdir -p ansible/.ssh
chmod 700 ansible/.ssh

# Grava a chave
echo "$SSH_PRIVATE_KEY" > ansible/.ssh/id_rsa
chmod 600 ansible/.ssh/id_rsa

# ssh_config local para a execução do Ansible
cat > ansible/.ssh/config <<'CFG'
Host *
  IdentitiesOnly yes
  IdentityFile ~/.ssh/id_rsa
  ServerAliveInterval 30
  # Em labs: aceita primeira conexão; em prod, prefira known_hosts com fingerprint
  StrictHostKeyChecking accept-new
CFG
chmod 600 ansible/.ssh/config

# Opcional: known_hosts “pinned”
# echo "192.168.0.17 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...." >> ansible/.ssh/known_hosts
# chmod 644 ansible/.ssh/known_hosts

echo "[ok] SSH key escrita em ansible/.ssh/id_rsa"
