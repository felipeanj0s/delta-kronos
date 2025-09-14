#!/usr/bin/env python3
import os
import json
import pathlib
from zbx_api import ensure_host

def _read_agent_psk_from_artifacts(name: str) -> str:
    base = os.getenv("DK_ANSIBLE_ARTIFACTS_DIR", "ansible_artifacts")
    cand = [
        pathlib.Path(base) / "psk" / f"{name}-agent.psk",
        pathlib.Path(base) / "psk" / f"{name}.psk",  # fallback (mesma PSK do proxy)
        pathlib.Path("artifacts") / "psk" / f"{name}-agent.psk",
        pathlib.Path("artifacts") / "psk" / f"{name}.psk",
    ]
    for p in cand:
        if p.is_file():
            return p.read_text().strip()
    return ""

def main():
    proxy_name = os.getenv("ZBX_PROXY_NAME")
    if not proxy_name:
        raise RuntimeError("Defina ZBX_PROXY_NAME.")

    name = os.getenv("ZBX_AGENT_NAME") or proxy_name
    ip = os.getenv("ZBX_AGENT_IP")
    if not ip:
        raise RuntimeError("Defina ZBX_AGENT_IP.")
    port = int(os.getenv("ZBX_AGENT_PORT", "10050"))

    groups = json.loads(os.getenv("ZBX_AGENT_GROUPS", '["Linux servers","Zabbix proxies"]'))
    templates = json.loads(os.getenv("ZBX_AGENT_TEMPLATES", '["Linux by Zabbix agent"]'))

    enforce_same = os.getenv("ENFORCE_SAME_AGENT_PROXY", "true").lower() == "true"
    if enforce_same and name != proxy_name:
        raise RuntimeError(f"Agent('{name}') deve ser igual ao Proxy('{proxy_name}').")

    interfaces = [{
        "type": 1,  # agent
        "main": 1,
        "useip": 1,
        "ip": ip,
        "dns": "",
        "port": str(port),
    }]

    use_psk = os.getenv("ZBX_AGENT_TLS", "psk").lower() == "psk"
    psk_id = os.getenv("ZBX_AGENT_PSK_ID") or f"{name}-psk-agent"
    psk_value = os.getenv("ZBX_AGENT_PSK_VALUE") or _read_agent_psk_from_artifacts(name)

    res = ensure_host(
        name=name,
        interfaces=interfaces,
        group_names=groups,
        template_names=templates,
        proxy_name=proxy_name,
        use_psk=use_psk,
        psk_identity=psk_id,
        psk_value=(psk_value or None),
    )
    print("OK host:", res)

if __name__ == "__main__":
    main()
