#!/usr/bin/env python3
import os, sys, stat, shutil, argparse, tempfile, pathlib, subprocess
from contextlib import ExitStack

try:
    import ansible_runner  # pip install ansible-runner
except Exception:
    ansible_runner = None

def main():
    repo_root  = pathlib.Path(__file__).resolve().parents[1]
    ansible_dir= repo_root / "ansible"

    p = argparse.ArgumentParser(description="Rodar playbooks via ansible-runner ou subprocess")
    p.add_argument("--playbook", default="provision.yml")
    p.add_argument("--inventory", default=str(ansible_dir / "inventory" / "hosts.yml"))
    p.add_argument("--limit", default=None)
    p.add_argument("--clean-cache", action="store_true")
    args = p.parse_args()

    vault_password = os.getenv("ANSIBLE_VAULT_PASSWORD")
    if not vault_password:
        print("ERRO: defina ANSIBLE_VAULT_PASSWORD.", file=sys.stderr); sys.exit(2)

    dk_artifacts = os.getenv("DK_ANSIBLE_ARTIFACTS_DIR") or str(repo_root / "ansible_artifacts")
    os.environ["DK_ANSIBLE_ARTIFACTS_DIR"] = dk_artifacts
    pathlib.Path(dk_artifacts, "psk").mkdir(parents=True, exist_ok=True)
    pathlib.Path(dk_artifacts, "credentials").mkdir(parents=True, exist_ok=True)

    runner_artifacts = ansible_dir / "artifacts"
    if args.clean_cache and runner_artifacts.exists():
        shutil.rmtree(runner_artifacts, ignore_errors=True)

    with ExitStack() as stack:
        fd, vault_file_path = tempfile.mkstemp(prefix="vault_", suffix=".txt")
        stack.callback(lambda: os.path.exists(vault_file_path) and os.remove(vault_file_path))
        os.write(fd, vault_password.encode()); os.close(fd)
        os.chmod(vault_file_path, stat.S_IRUSR | stat.S_IWUSR)

        env = os.environ.copy()
        env.update({
            "ANSIBLE_VAULT_PASSWORD_FILE": vault_file_path,
            "ANSIBLE_CONFIG": str(ansible_dir / "configs" / "ansible.cfg"),
            "ANSIBLE_CACHE_PLUGIN_TIMEOUT": "0",
            "DK_ANSIBLE_ARTIFACTS_DIR": dk_artifacts,
        })

        if ansible_runner:
            r = ansible_runner.run(
                private_data_dir=str(ansible_dir),
                playbook=f"playbooks/{args.playbook}",
                inventory=args.inventory,
                envvars=env,
                rotate_artifacts=1,
                cmdline=(f"--limit {args.limit}" if args.limit else None),
            )
            rc = r.rc
        else:
            cmd = [
                "ansible-playbook",
                "-i", args.inventory,
                str(ansible_dir / "playbooks" / args.playbook),
            ]
            if args.limit:
                cmd += ["--limit", args.limit]
            rc = subprocess.call(cmd, env=env)

        if rc == 0:
            print("✅ Playbook executado com sucesso.")
        else:
            print(f"❌ Playbook falhou (rc={rc}).", file=sys.stderr)
            sys.exit(rc)

if __name__ == "__main__":
    main()
