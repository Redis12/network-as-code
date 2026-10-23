"""Se connecte en SSH à chaque switch et vérifie que le réseau fait ce que l'inventaire décrit.

Pour chaque switch, on envoie des commandes "show", puis on compare la sortie
avec ce qui est écrit dans le YAML. Résultat : une liste de OK / ÉCHEC.
"""
import ipaddress
import os
import sys
from getpass import getpass

from netmiko import ConnectHandler

from inventory import switches


def short(port):
    """Nom de port du YAML -> nom affiché par les "show" (e0/2 -> Et0/2)."""
    return "Et" + port[1:] if port.lower().startswith("e") else port


def peer_ip(ip, network):
    """Dans un /30, l'IP d'en face est l'autre adresse utilisable."""
    hosts = [str(h) for h in ipaddress.ip_network(f"{network}/30").hosts()]
    return hosts[0] if hosts[1] == ip else hosts[1]


# ---------- Tests des switches de distribution ----------

def check_hsrp(conn, data):
    """Active sur les VLANs de hsrp_active, Standby sur les autres."""
    out = conn.send_command("show standby brief")
    results = []
    for vlan in data["vlans"]:
        wanted = "Active" if vlan["id"] in data["hsrp_active"] else "Standby"
        # Ligne du type : "Vl10   10   110 P Active  local   192.168.14.2   192.168.14.3"
        line = next((l for l in out.splitlines() if l.split()[:1] == [f"Vl{vlan['id']}"]), "")
        results.append((wanted in line.split(), f"HSRP VLAN {vlan['id']} : {wanted} attendu"))
    return results


def check_stp_root(conn, data):
    """Root primary sur les mêmes VLANs que HSRP Active (règle du template)."""
    results = []
    for vlan in data["vlans"]:
        out = conn.send_command(f"show spanning-tree vlan {vlan['id']}")
        is_root = "This bridge is the root" in out
        wanted = vlan["id"] in data["hsrp_active"]
        label = "root" if wanted else "pas root"
        results.append((is_root == wanted, f"STP VLAN {vlan['id']} : {label} attendu"))
    return results


def check_etherchannel(conn, data):
    """Po en (SU) = L2 + en service, et chaque membre en (P) = dans le bundle."""
    ec = data["etherchannel"]
    out = conn.send_command("show etherchannel summary")
    line = next((l for l in out.splitlines() if f"Po{ec['id']}(" in l), "")
    ok = f"Po{ec['id']}(SU)" in line and all(f"{short(m)}(P)" in line for m in ec["members"])
    return [(ok, f"EtherChannel Po{ec['id']} up avec {len(ec['members'])} membres")]


def check_eigrp(conn, data):
    """Un voisin EIGRP par lien vers les cores."""
    out = conn.send_command("show ip eigrp neighbors")
    return [(peer_ip(up["ip"], up["network"]) in out,
             f"Voisin EIGRP {up['neighbor']} (échoue tant que les cores sont absents du labo)")
            for up in data["uplinks"]]


# ---------- Tests communs ----------

def check_trunks(conn, ports):
    """Les ports doivent être en trunk (DTP a bien négocié)."""
    out = conn.send_command("show interfaces trunk")
    trunk_ports = {l.split()[0] for l in out.splitlines() if l.strip()}
    return [(short(p) in trunk_ports, f"Trunk sur {p}") for p in ports]


# ---------- Tests des switches d'accès ----------

def check_access_vlans(conn, data):
    """Chaque port PC est dans le bon VLAN (prouve aussi que VTP a transmis les VLANs)."""
    out = conn.send_command("show vlan brief")
    vlan_of = {}
    current = None
    for line in out.splitlines():
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        if parts[0].isdigit():            # nouvelle ligne de VLAN : "10   VLAN0010   active   Et0/0"
            current = int(parts[0])
            parts = parts[3:]
        for p in parts:                   # les ports (une ligne de suite n'a que des ports)
            if p.startswith("Et"):
                vlan_of[p] = current
    return [(vlan_of.get(short(p["port"])) == p["vlan"], f"Port {p['port']} dans le VLAN {p['vlan']}")
            for p in data["ports"]]


def run_checks(conn, role, data):
    if role == "distribution":
        return (check_hsrp(conn, data) + check_stp_root(conn, data)
                + check_etherchannel(conn, data) + check_eigrp(conn, data)
                + check_trunks(conn, data["trunks"]))
    return check_trunks(conn, data["uplinks"]) + check_access_vlans(conn, data)


def main():
    password = os.environ.get("NAC_SSH_PASSWORD") or getpass("Mot de passe SSH des switches : ")
    failures = 0

    for name, role, data in switches():
        host = f"{data['mgmt']['prefix']}.{data['mgmt_octet']}"
        print(f"\n=== {name} ({host})")
        try:
            conn = ConnectHandler(device_type="cisco_ios", host=host,
                                  username=data["ssh_user"], password=password)
        except Exception as err:          # switch éteint, mauvais mot de passe...
            print(f"  ÉCHEC  connexion impossible : {err}")
            failures += 1
            continue

        with conn:                        # ferme la session SSH à la fin du bloc
            for ok, label in run_checks(conn, role, data):
                print(f"  {'OK   ' if ok else 'ÉCHEC'}  {label}")
                failures += not ok

    print(f"\n{'Tout est OK' if failures == 0 else f'{failures} test(s) en échec'}")
    sys.exit(1 if failures else 0)        # code 1 = échec (utile plus tard pour GitHub Actions)


if __name__ == "__main__":
    main()
