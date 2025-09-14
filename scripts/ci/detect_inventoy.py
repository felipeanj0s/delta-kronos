#!/usr/bin/env python3
import sys, os, json, yaml

def load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}

def flatten_hosts(inv):
    out = {}
    children = (inv.get("all", {}) or {}).get("children", {}) or {}
    for group, gdata in children.items():
        hosts = (gdata or {}).get("hosts", {}) or {}
        for h, vars_ in hosts.items():
            out[h] = {"group": group, "vars": vars_ or {}}
    return out

def normalize(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))

def diff_hosts(old_map, new_map):
    old_keys, new_keys = set(old_map), set(new_map)
    added   = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    common  = new_keys & old_keys
    changed = []
    for h in sorted(common):
        if old_map[h]["group"] != new_map[h]["group"]:
            changed.append(h); continue
        if normalize(old_map[h]["vars"]) != normalize(new_map[h]["vars"]):
            changed.append(h)
    return added, removed, changed

def main():
    if len(sys.argv) < 3:
        print("usage: detect_inventory_changes.py <old> <new> [--out <file>]")
        sys.exit(2)

    old_path, new_path = sys.argv[1], sys.argv[2]
    out_file = sys.argv[sys.argv.index("--out")+1] if "--out" in sys.argv else None

    old_map = flatten_hosts(load_yaml(old_path))
    new_map = flatten_hosts(load_yaml(new_path))
    added, removed, changed = diff_hosts(old_map, new_map)

    matrix = [{"host": h, "group": new_map[h]["group"]} for h in (added + changed) if h in new_map]
    result = {"added": added, "removed": removed, "changed": changed, "matrix": matrix, "count": len(matrix)}
    print(json.dumps(result, ensure_ascii=False))

    if out_file:
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"matrix={json.dumps(matrix)}\n")
            f.write(f"count={len(matrix)}\n")

if __name__ == "__main__":
    main()
