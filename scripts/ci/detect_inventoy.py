#!/usr/bin/env python3
import sys, os, json, yaml, hashlib

def load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}

def flatten_hosts(inv):
    """
    Retorna dict: { "<host>": {"group": "<group>", "vars": {...}} }
    Percorre all.children.*.hosts
    """
    out = {}
    try:
        children = inv.get("all", {}).get("children", {}) or {}
        for group, gdata in children.items():
            hosts = gdata.get("hosts", {}) or {}
            for h, vars_ in hosts.items():
                out[h] = {"group": group, "vars": vars_ or {}}
    except Exception:
        pass
    return out

def normalize(v):
    # serializa em json p/ comparação estável (ordenação de chaves)
    return json.dumps(v, sort_keys=True, separators=(",", ":"))

def diff_hosts(old_map, new_map):
    added   = [h for h in new_map.keys() - old_map.keys()]
    removed = [h for h in old_map.keys() - new_map.keys()]
    common  = new_map.keys() & old_map.keys()

    changed = []
    for h in common:
        if old_map[h]["group"] != new_map[h]["group"]:
            changed.append(h)
            continue
        if normalize(old_map[h]["vars"]) != normalize(new_map[h]["vars"]):
            changed.append(h)

    return added, removed, changed

def main():
    if len(sys.argv) < 3:
        print("usage: detect_inventory_changes.py <old_hosts.yml> <new_hosts.yml> [--out <file>]")
        sys.exit(2)

    old_path, new_path = sys.argv[1], sys.argv[2]
    out_file = None
    if "--out" in sys.argv:
        out_file = sys.argv[sys.argv.index("--out") + 1]

    old = load_yaml(old_path)
    new = load_yaml(new_path)
    old_map = flatten_hosts(old)
    new_map = flatten_hosts(new)

    added, removed, changed = diff_hosts(old_map, new_map)

    # Matriz p/ GH Actions: lista de objetos {host, group}
    matrix = [{"host": h, "group": new_map[h]["group"]} for h in added + changed if h in new_map]
    result = {
        "added": added,
        "removed": removed,
        "changed": changed,
        "matrix": matrix,
        "count": len(matrix),
    }
    payload = json.dumps(result, ensure_ascii=False)
    print(payload)

    # Se pediram, grava no arquivo de saída (GITHUB_OUTPUT)
    if out_file:
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"matrix={json.dumps(matrix)}\n")
            f.write(f"count={len(matrix)}\n")

if __name__ == "__main__":
    main()
