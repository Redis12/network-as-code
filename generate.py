"""Génère la config Cisco de chaque switch à partir de l'inventaire YAML."""
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

BASE = Path(__file__).parent
INV = BASE / "inventory"
OUT = BASE / "configs"


def load(path):
    """Lit un fichier YAML (renvoie {} s'il n'existe pas ou est vide)."""
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def main():
    hosts = load(INV / "hosts.yaml")
    common = load(INV / "group_vars" / "all.yaml")

    # trim/lstrip : enlève les lignes vides laissées par {% %}
    # StrictUndefined : plante si une variable manque au lieu de générer une config trouée
    env = Environment(loader=FileSystemLoader(BASE / "templates"),
                      trim_blocks=True, lstrip_blocks=True,
                      undefined=StrictUndefined)
    OUT.mkdir(exist_ok=True)

    for group, roles in hosts.items():          # ex. batiment1
        group_vars = load(INV / "group_vars" / f"{group}.yaml")
        for role, switches in roles.items():    # distribution / access
            template = env.get_template(f"{role}.j2")
            for name in switches:               # ex. DS-SW1
                # Du plus général au plus précis : le plus précis gagne
                data = {**common, **group_vars,
                        **load(INV / "host_vars" / f"{name}.yaml"),
                        "hostname": name}
                (OUT / f"{name}.txt").write_text(template.render(data), encoding="utf-8")
                print(f"OK  {name}  ({role})")


if __name__ == "__main__":
    main()
