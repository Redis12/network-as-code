"""Lit l'inventaire YAML et fusionne les variables de chaque switch.

Utilisé par generate.py (pour créer les configs) et verify.py (pour les tester) :
les deux scripts voient donc exactement les mêmes données.
"""
from pathlib import Path

import yaml

INV = Path(__file__).parent / "inventory"


def load(path):
    """Lit un fichier YAML (renvoie {} s'il n'existe pas ou est vide)."""
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def switches():
    """Donne (nom, rôle, données) pour chaque switch déclaré dans hosts.yaml."""
    hosts = load(INV / "hosts.yaml")
    common = load(INV / "group_vars" / "all.yaml")

    for group, roles in hosts.items():          # ex. batiment1
        group_vars = load(INV / "group_vars" / f"{group}.yaml")
        for role, names in roles.items():       # distribution / access
            for name in names:                  # ex. DS-SW1
                # Du plus général au plus précis : le plus précis gagne
                data = {**common, **group_vars,
                        **load(INV / "host_vars" / f"{name}.yaml"),
                        "hostname": name}
                yield name, role, data
