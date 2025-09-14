#!/usr/bin/env python3
import os
import sys
import stat
import shutil
import argparse
import tempfile
import pathlib
from contextlib import ExitStack

# (opcional) permite .env no DEV local
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def main():
    import ansible_runner  # pip install ansible-runner

    repo_root = pathlib.Path(__file__).resolve().parents[1]   # .../scripts -> repo root
    ansible_dir = repo_root / "ansible"

    parser = argparse.ArgumentParser(description="Rodar playbooks via ansible-runner")
    parser.add_argument("--playbook", default="provision.yml", help="arquivo em ansible/playbooks/")
    parser.add_argument("--inventory", default=str(ansible_dir / "inventory" / "hosts.yml"))
    parser.add_argument("--limit", default=None, help="--limit do Ansible (opcional)")
    parser.add_argument("--clean-cache", action="store_true", help="limpar ansible/artifacts antes de rodar")
    args = parser.parse_args()

    vault_password = os.getenv("ANSIBLE_VAULT_PASSWORD")
    if not vault_password:
        print("ERRO: defina ANSIBLE_VAULT_PASSWORD (no CI: GitHub Secrets).", file=sys.stderr)
        sys.exit(2)

    # Diretório local para artefatos do Ansible (PSKs/senhas refletidas)
    dk_artifacts = os.getenv("DK_ANSIBLE_ARTIFACTS_DIR")
    if not dk_artifacts:
        dk_artifacts = str(repo_root / "ansible_artifacts")  # padrão local
        os.environ["DK_ANSIBLE_ARTIFACTS_DIR"] = dk_artifacts

    # Garante subpastas esperadas (quando rodar local)
    pathlib.Path(dk_artifacts, "psk").mkdir(parents=True, exist_ok=True)
    pathlib.Path(dk_artifacts, "credentials").mkdir(parents=True, exist_ok=True)

    # Cache do ansible-runner (safe remover quando pedido)
    runner_artifacts = ansible_dir / "artifacts"
    if args.clean_cache and runner_artifacts.exists():
        shutil.rmtree(runner_artifacts, ignore_errors=True)

    with ExitStack() as stack:
        # arquivo temporário para o vault (0600)
        fd, vault_file_path = tempfile.mkstemp(prefix="vault_", suffix=".txt")
        stack.callback(lambda: os.path.exists(vault_file_path) and os.remove(vault_file_path))
        os.write(fd, vault_password.encode())
        os.close(fd)
        os.chmod(vault_file_path, stat.S_IRUSR | stat.S_IWUSR)

        envvars = {
            "ANSIBLE_VAULT_PASSWORD_FILE": vault_file_path,
            "ANSIBLE_CONFIG": str(ansible_dir / "configs" / "ansible.cfg"),
            "ANSIBLE_CACHE_PLUGIN_TIMEOUT": "0",
            # importante: exportar para as roles usarem o caminho correto
            "DK_ANSIBLE_ARTIFACTS_DIR": dk_artifacts,
        }

        cmdline = f"--limit {args.limit}" if args.limit else None

        r = ansible_runner.run(
            private_data_dir=str(ansible_dir),
            playbook=f"playbooks/{args.playbook}",
            inventory=args.inventory,
            envvars=envvars,
            rotate_artifacts=1,
            cmdline=cmdline,
        )

        if r.rc == 0:
            print("✅ Playbook executado com sucesso.")
        else:
            print(f"❌ Playbook falhou (rc={r.rc}).", file=sys.stderr)
            sys.exit(r.rc)

if __name__ == "__main__":
    main()
