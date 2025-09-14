#!/usr/bin/env python3
import os
import pathlib
from zbx_api import ensure_proxy

def _read_psk_from_artifacts(name: str) -> str:
    # Prioridade: DK_ANSIBLE_ARTIFACTS_DIR (padrão: ansible_artifacts)
    base = os.getenv("DK_ANSIBLE_ARTIFACTS_DIR", "ansible_artifacts")
    p = pathlib.Path(base) / "psk" / f"{name}.psk"
    if p.is_file():
        return p.read_text().strip()

    # Legacy fallback: artifacts/
    legacy = pathlib.Path("artifacts") / "psk" / f"{name}.psk"
    if legacy.is_file():
        return legacy.read_text().strip()

    return ""

def main():
    # Obrigatórios
    name = os.getenv("ZBX_PROXY_NAME")
    if not name:
        raise RuntimeError("Defina ZBX_PROXY_NAME (nome do proxy no Zabbix).")

    mode = os.getenv("ZBX_PROXY_MODE", "active").strip().lower()
    if mode not in ("active", "passive"):
        mode = "active"

    # Somente para passive
    addr = os.getenv("ZBX_PROXY_ADDRESS")
    port = int(os.getenv("ZBX_PROXY_PORT", "10051"))

    if mode == "passive" and not addr:
        raise RuntimeError("Modo 'passive' exige ZBX_PROXY_ADDRESS.")

    psk_id = os.getenv("ZBX_PSK_ID") or f"{name}-psk"
    psk_value = os.getenv("ZBX_PSK_VALUE") or _read_psk_from_artifacts(name)

    proxy_group = os.getenv("ZBX_PROXY_GROUP")  # opcional (nome do grupo)

    res = ensure_proxy(
        name=name,
        mode=mode,                       # "active" | "passive"
        passive_address=addr,            # usado apenas se passive
        passive_port=port,               # idem
        psk_identity=psk_id,
        psk_value=psk_value or None,     # None -> não altera/define
        proxy_group_name=proxy_group or None,
    )
    print("OK proxy:", res)

if __name__ == "__main__":
    main()
