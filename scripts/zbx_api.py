#!/usr/bin/env python3
import os
import json
import requests
from requests.adapters import HTTPAdapter, Retry

def _normalize_url(u: str) -> str:
    if not u:
        return u
    u = u.strip()
    if u.endswith("/api_jsonrpc.php"):
        return u
    if u.endswith("/zabbix") or u.endswith("/zabbix/"):
        return u.rstrip("/") + "/api_jsonrpc.php"
    return u.rstrip("/") + "/api_jsonrpc.php"

ZBX_URL_RAW = os.getenv("ZABBIX_URL")
ZBX_URL     = _normalize_url(ZBX_URL_RAW or "")
ZBX_TOKEN   = os.getenv("ZABBIX_TOKEN")
TIMEOUT     = float(os.getenv("ZABBIX_TIMEOUT", "30"))
VERIFY_SSL  = (os.getenv("ZABBIX_VERIFY_SSL", "true").strip().lower() not in ("0","false","no"))

if not ZBX_URL or not ZBX_TOKEN:
    raise RuntimeError("Defina ZABBIX_URL (base ou /api_jsonrpc.php) e ZABBIX_TOKEN.")

if not VERIFY_SSL:
    # evitar flood de warnings em lab
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

# --- HTTP session com retries/backoff ---
_sess = requests.Session()
_sess.headers.update({
    "Content-Type": "application/json-rpc",
    "Authorization": f"Bearer {ZBX_TOKEN}",
})
_retries = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"POST"}),
)
_sess.mount(ZBX_URL.split("/api_jsonrpc.php")[0], HTTPAdapter(max_retries=_retries))

def rpc(method, params):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    try:
        r = _sess.post(ZBX_URL, data=json.dumps(payload), timeout=TIMEOUT, verify=VERIFY_SSL)
        r.raise_for_status()
        data = r.json()
    except requests.HTTPError as e:
        body = r.text if 'r' in locals() else ''
        raise RuntimeError(f"HTTP error em {method}: {e} | body={body}") from e
    except Exception as e:
        raise RuntimeError(f"Falha em {method}: {e}") from e
    if "error" in data:
        raise RuntimeError(f"Zabbix API error {method}: {data['error']}")
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
    mode="active",               # "active"|"passive"|0|1
    passive_address=None,        # obrigatório se mode=passive
    passive_port=10051,
    psk_identity=None,
    psk_value=None,
    proxy_group_name=None        # opcional
):
    # normaliza modo
    m = str(mode).strip().lower()
    op_mode = 0 if m in ("0","active") else 1 if m in ("1","passive") else 0

    existing = rpc("proxy.get", {"filter": {"name": name}})
    params = {"name": name, "operating_mode": op_mode}

    if op_mode == 1:
        if not passive_address:
            raise RuntimeError("Proxy PASSIVE requer 'passive_address'.")
        params.update({"address": str(passive_address), "port": str(passive_port)})

    # PSK (apenas se identity + value para não sobrescrever acidentalmente)
    if psk_identity and psk_value:
        params.update({
            "tls_connect": 2,           # PSK
            "tls_accept": 2,            # PSK
            "tls_psk_identity": psk_identity,
            "tls_psk": psk_value,
        })

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
    interfaces,                  # [{"type":1,"main":1,"useip":1,"ip":"x.x.x.x","dns":"","port":"10050"}]
    group_names,                 # nomes de grupos
    template_names,              # nomes de templates
    proxy_name=None,             # opcional
    proxy_group_name=None,       # opcional (alternativa a proxy_name)
    use_psk=False,
    psk_identity=None,
    psk_value=None
):
    groupids = _get_hostgroup_ids(group_names)
    templateids = _get_template_ids(template_names)

    base = {
        "host": name,
        "groups": [{"groupid": gid} for gid in groupids],
        "templates": [{"templateid": tid} for tid in templateids],
        "interfaces": interfaces,
    }

    # Vincular a proxy OU proxy group (Zabbix 7.x)
    if proxy_name:
        px = rpc("proxy.get", {"filter": {"name": proxy_name}})
        if not px:
            raise RuntimeError(f"Proxy '{proxy_name}' não encontrado")
        base.update({"monitored_by": 1, "proxyid": px[0]["proxyid"]})
    elif proxy_group_name:
        pg = rpc("proxygroup.get", {"filter": {"name": proxy_group_name}})
        if not pg:
            raise RuntimeError(f"Proxy group '{proxy_group_name}' não encontrado")
        base.update({"monitored_by": 2, "proxy_groupid": pg[0]["proxy_groupid"]})

    if use_psk and psk_identity and psk_value:
        base.update({
            "tls_connect": 2,
            "tls_accept": 2,
            "tls_psk_identity": psk_identity,
            "tls_psk": psk_value,
        })

    cur = rpc("host.get", {"filter": {"host": [name]}})
    if cur:
        base["hostid"] = cur[0]["hostid"]
        return rpc("host.update", base)
    else:
        return rpc("host.create", base)
