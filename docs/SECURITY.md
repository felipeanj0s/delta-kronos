# Segurança

- **Tokens e segredos**:
  - Não comitar `.env`. Use `ZABBIX_URL` e `ZABBIX_TOKEN` via secrets (GitHub/GitLab).
- **PSK**:
  - PSKs gerados/garantidos no provisionamento são salvos em `artifacts/psk/<host>.psk`.
  - A identidade PSK deve ser coerente com `psk_id` do inventário.
- **Acesso SSH**:
  - Utilize chaves exclusivas para este projeto e permissão mínima necessária.
