"""Génère la config Cisco de chaque switch à partir de l'inventaire YAML."""
import os
from getpass import getpass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from inventory import switches

BASE = Path(__file__).parent
OUT = BASE / "configs"


def main():
    # trim/lstrip : enlève les lignes vides laissées par {% %}
    # StrictUndefined : plante si une variable manque au lieu de générer une config trouée
    env = Environment(loader=FileSystemLoader(BASE / "templates"),
                      trim_blocks=True, lstrip_blocks=True,
                      undefined=StrictUndefined)
    OUT.mkdir(exist_ok=True)
    (OUT / "bootstrap").mkdir(exist_ok=True)

    # Le mot de passe SSH n'est jamais dans le dépôt : variable d'environnement
    # NAC_SSH_PASSWORD si elle existe, sinon on le demande (rien ne s'affiche à la frappe)
    ssh_password = os.environ.get("NAC_SSH_PASSWORD") or getpass("Mot de passe SSH des switches : ")
    bootstrap = env.get_template("bootstrap.j2")

    for name, role, data in switches():
        template = env.get_template(f"{role}.j2")   # distribution.j2 ou access.j2
        (OUT / f"{name}.txt").write_text(template.render(data), encoding="utf-8")
        # configs/ est ignoré par Git : le mot de passe ne part pas sur GitHub
        (OUT / "bootstrap" / f"{name}.txt").write_text(
            bootstrap.render(data, ssh_password=ssh_password), encoding="utf-8")
        print(f"OK  {name}  ({role} + bootstrap)")


if __name__ == "__main__":
    main()
