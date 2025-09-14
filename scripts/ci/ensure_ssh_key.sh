#!/usr/bin/env bash
set -euo pipefail
mkdir -p ansible/.ssh
umask 077
: "${SSH_PRIVATE_KEY:?SSH_PRIVATE_KEY não definido}"
printf "%s" "$SSH_PRIVATE_KEY" > ansible/.ssh/id_rsa
echo "chave privada escrita em ansible/.ssh/id_rsa"
