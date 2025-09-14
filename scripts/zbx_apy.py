#!/usr/bin/env python3
import os
import json
import requests
from urllib.parse import urljoin

def _normalize_url(u: str) -> str:
    """Garante que a URL termina com /api_jsonrpc.php."""
    if not u:
        return u
    # remove espaços
    u = u.strip()
    # Se já terminar com api_jsonrpc.php, mantém
    if u.endswith("/api_jsonrpc.php"):
        return u
    # Se terminar em /zabbix, completa com api_jsonrpc.php
    if u.endswith("/zabbix") or u.endswith("/zabbix/"):
        return u.rstrip("/") + "/api_jsonrpc.php"
    # Se for raiz do host, também completa
    return u.rstrip("/") + "/api_jsonrpc.php"

ZBX_URL_RAW   = os.getenv("ZABBIX_URL")  # pode ser base (…/zabbix) ou já /api_jsonrpc.php
ZBX_URL       = _normalize_url(ZBX_URL_RAW)
ZBX_TOKEN     = os.getenv("ZABBIX_TOKEN")
TIMEOUT       = int(os.getenv("ZABBIX_TIMEOUT", "30"))
VERIFY_SSL_ENV= os.getenv("ZABBIX_VERIFY_SSL", "true").strip().lower()
VERIFY_SSL    = False if VERIFY_SSL_ENV in ("0","false","no") else True

if not ZBX_URL or not ZBX_TOKEN:
    raise RuntimeError("Defina ZABBIX_URL (pode ser base ou já /api_jsonrpc.php) e ZABBIX_TOKEN.")

# Silencia warnings se desativar SSL verify
if not VERIFY_SSL:
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

def rpc(method, params):
    """Chamada JSON-RPC 2.0 com Bearer Token (Zabbix 6.4+/7.x)."""
    try:
        r = requests.post(
            ZBX_URL,
            headers={
                "Content-Type": "application/json-rpc",
                "Authorization": f"Bearer {ZBX_TOKEN}",
            },
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        r.raise_for_status()
        data = r.json()
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP error em {method}: {e} | body={r.text if 'r' in locals() else ''}") from e
    except Exception as e:
        raise RuntimeError(f"Falha em {method}: {e}") from e

    if "error" in data:
        # Mensagem padrão do Zabbix é um dict com code/message/data
        err = data["error"]
        raise RuntimeError(f"Zabbix API error {method}: {err}")
    return data.get("result")

def _get_hostgroup_ids(names):
    if not names:
        return []
    res = rpc("hostgroup.get", {"output": ["groupid","name"], "filter": {"name": names}})
    found = {g["name"]: g["groupid"] for g in res}
    missing = [n for n in names if n not in found]
    if missing:
        raise RuntimeError(f"Host groups não encontrados: {missing}")
    return list(found.values())

def _get_template_ids(names):
    if not names:
        return []
    res = rpc("template.get", {"output": ["templateid","name"], "filter": {"name": names}})
    found = {t["name"]: t["templateid"] for t in res}
    missing = [n for n in names if n not in found]
    if missing:
        raise RuntimeError(f"Templates não encontrados: {missing}")
    return list(found.values())

def ensure_proxy(
    name,
    mode="active",                 # "active"|"passive"|0|1
    passive_address=None,          # obrigatório se mode=passive
    passive_port=10051,
    psk_identity=None,
    psk_value=None,
    proxy_group_name=None          # opcional: nome do Proxy Group (apenas 1)
):
    """
    Cria/atualiza proxy:
      - operating_mode: 0=active, 1=passive
      - passive: requer address/port
      - PSK: define tls_* somente se identity e value vierem juntos
      - Proxy Group: por nome (opcional)
    """
    # normaliza modo
    m = str(mode).strip().lower()
    if m in ("0", "active"):
        op_mode = 0
    elif m in ("1", "passive"):
        op_mode = 1
    else:
        op_mode = 0  # default

    existing = rpc("proxy.get", {"filter": {"name": name}})
    params = {
        "name": name,
        "operating_mode": op_mode,
    }

    if op_mode == 1:
        if not passive_address:
            raise RuntimeError("Proxy PASSIVE requer ZBX_PROXY_ADDRESS (passive_address).")
        params.update({"address": str(passive_address), "port": str(passive_port)})

    # TLS PSK (só aplica se vierem ambos; evita limpar config no update)
    if psk_identity and psk_value:
        params.update({
            "tls_connect": 2,            # PSK
            "tls_accept": 2,             # PSK
            "tls_psk_identity": psk_identity,
            "tls_psk": psk_value,
        })

    # Proxy Group por nome (opcional)
    if proxy_group_name:
        pg = rpc("proxygroup.get", {"output": ["proxy_groupid","name"], "filter": {"name": [proxy_group_name]}})
        if not pg:
            raise RuntimeError(f"Proxy Group '{proxy_group_name}' não encontrado")
        params["proxy_groupid"] = pg[0]["proxy_groupid"]

    if existing:
        params["proxyid"] = existing[0]["proxyid"]
        return rpc("proxy.update", params)
    else:
        return rpc("proxy.create", params)

def ensure_host(
    name,
    interfaces,                    # [{"type":1,"main":1,"useip":1,"ip":"x.x.x.x","dns":"","port":"10050"}]
    group_names,                   # lista com nomes de grupos
    template_names,                # lista com nomes de templates
    proxy_name=None,               # opcional
    use_psk=False,
    psk_identity=None,
    psk_value=None
):
    """
    Cria/atualiza host:
      - Vincula a grupos/templates por NOME
      - Vincula a proxy via monitored_by=1 + proxyid
      - TLS PSK opcional (define só se identity + value)
    """
    groupids = _get_hostgroup_ids(group_names)
    templateids = _get_template_ids(template_names)

    current = rpc("host.get", {"filter": {"host": name}})

    base = {
        "host": name,
        "groups": [{"groupid": gid} for gid in groupids],
        "templates": [{"templateid": tid} for tid in templateids],
        "interfaces": interfaces,
    }

    if proxy_name:
        px = rpc("proxy.get", {"filter": {"name": proxy_name}})
        if not px:
            raise RuntimeError(f"Proxy '{proxy_name}' não encontrado")
        # Em Zabbix 6.4+/7.x: monitored_by = 1 (proxy), e proxyid (string id)
        base.update({"monitored_by": 1, "proxyid": px[0]["proxyid"]})

    if use_psk and psk_identity and psk_value:
        base.update({
            "tls_connect": 2,
            "tls_accept": 2,
            "tls_psk_identity": psk_identity,
            "tls_psk": psk_value,
        })

    if current:
        base["hostid"] = current[0]["hostid"]
        return rpc("host.update", base)
    else:
        return rpc("host.create", base)
