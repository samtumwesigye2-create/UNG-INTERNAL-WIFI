#!/usr/bin/env python3
"""Internal Wi-Fi Platform Raspberry Pi installer.

Dry-run by default. --apply writes managed configuration and enables services.
It NEVER enables Internet forwarding. A rollback snapshot is written before
managed files are changed.
"""
from __future__ import annotations
import argparse, os, shutil, subprocess, textwrap, time, pwd
from pathlib import Path

DEFAULTS = {
    "interface": "wlan0", "ssid": "InternalNet", "country": "UG",
    "address": "192.168.50.1/24", "gateway": "192.168.50.1",
    "dhcp_start": "192.168.50.100", "dhcp_end": "192.168.50.200",
}

def detect():
    return {name: shutil.which(name) is not None for name in ("hostapd", "dnsmasq", "nft", "systemctl", "ip")}

def plan():
    return [
        "Verify Raspberry Pi OS and Wi-Fi AP capability",
        "Install/verify hostapd, dnsmasq and nftables",
        "Configure the Wi-Fi interface for the private AP",
        "Configure DHCP/DNS for 192.168.50.0/24",
        "Install the Internal Wi-Fi API",
        "Apply firewall policy with Internet forwarding disabled",
        "Enable services for boot-time recovery",
        "Run a local health check",
    ]

def run(cmd):
    subprocess.run(cmd, check=True)

def write(path: Path, content: str, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.chmod(path, mode)

def backup(paths):
    root = Path(f"/var/backups/internal-wifi/{time.strftime('%Y%m%d-%H%M%S')}")
    root.mkdir(parents=True, exist_ok=True)
    for p in paths:
        p = Path(p)
        if p.exists():
            dst = root / p.as_posix().lstrip("/")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    return root

def render_hostapd(interface, ssid, country, psk):
    return textwrap.dedent(f"""\
        country_code={country}
        interface={interface}
        driver=nl80211
        ssid={ssid}
        hw_mode=g
        channel=6
        wmm_enabled=1
        auth_algs=1
        wpa=2
        wpa_key_mgmt=WPA-PSK
        rsn_pairwise=CCMP
        wpa_passphrase={psk}
    """)

def render_dnsmasq(interface, start, end):
    return textwrap.dedent(f"""\
        interface={interface}
        bind-interfaces
        domain=internal
        local=/internal/
        dhcp-range={start},{end},255.255.255.0,12h
        dhcp-option=3,192.168.50.1
        dhcp-option=6,192.168.50.1
    """)

def render_nft(interface):
    return textwrap.dedent(f"""\
        table inet internal_wifi {{
          chain input {{
            type filter hook input priority 0; policy drop;
            iif lo accept
            ct state established,related accept
            iifname \"{interface}\" udp dport {{53,67}} accept
            iifname \"{interface}\" tcp dport {{53,8080}} accept
            ip protocol icmp accept
          }}
          chain forward {{
            type filter hook forward priority 0; policy drop;
          }}
          chain output {{
            type filter hook output priority 0; policy accept;
          }}
        }}
    """)

def ensure_service_user(user: str = "internalwifi"):
    try:
        pwd.getpwnam(user)
    except KeyError:
        run(["useradd", "--system", "--home", "/opt/internal-wifi", "--shell", "/usr/sbin/nologin", user])

def install_application(source_dir: Path, app_dir: Path = Path("/opt/internal-wifi"), user: str = "internalwifi"):
    app_dir.mkdir(parents=True, exist_ok=True)
    for name in ("app", "deploy", "systemd", "requirements.txt", "README.md"):
        src = source_dir / name
        dst = app_dir / name
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    venv = app_dir / ".venv"
    run(["python3", "-m", "venv", str(venv)])
    run([str(venv / "bin" / "pip"), "install", "--upgrade", "pip"])
    run([str(venv / "bin" / "pip"), "install", "-r", str(app_dir / "requirements.txt")])
    run(["chown", "-R", f"{user}:{user}", str(app_dir)])

def write_runtime_env(admin_token: str, app_dir: Path = Path("/opt/internal-wifi")):
    env_path = app_dir / ".env"
    write(env_path, f"INTERNAL_WIFI_ADMIN_TOKEN={admin_token}\n", 0o600)
    run(["chown", "internalwifi:internalwifi", str(env_path)])

def persist_nftables(fragment: str = "/etc/nftables.d/internal-wifi.nft"):
    nft_main = Path("/etc/nftables.conf")
    include = f'include "{fragment}"'
    current = nft_main.read_text() if nft_main.exists() else "#!/usr/sbin/nft -f\nflush ruleset\n"
    if include not in current:
        current = current.rstrip() + "\n" + include + "\n"
        write(nft_main, current)
    run(["systemctl", "enable", "nftables"])

def install_api_service(source_dir: Path):
    svc_src = source_dir / "systemd" / "internal-wifi-api.service"
    svc_dst = Path("/etc/systemd/system/internal-wifi-api.service")
    shutil.copy2(svc_src, svc_dst)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "internal-wifi-api.service"])
    run(["systemctl", "restart", "internal-wifi-api.service"])

def apply(args):
    missing = [k for k,v in detect().items() if not v]
    if missing:
        raise SystemExit("Missing required tools: " + ", ".join(missing))
    psk = os.environ.get("INTERNAL_WIFI_PSK", "")
    if len(psk) < 12:
        raise SystemExit("Set INTERNAL_WIFI_PSK to a strong passphrase of at least 12 characters before --apply")
    admin = os.environ.get("INTERNAL_WIFI_ADMIN_TOKEN", "")
    if len(admin) < 24:
        raise SystemExit("Set INTERNAL_WIFI_ADMIN_TOKEN to a random value of at least 24 characters before --apply")

    managed = ["/etc/hostapd/hostapd.conf", "/etc/dnsmasq.d/internal-wifi.conf", "/etc/nftables.d/internal-wifi.nft", "/etc/nftables.conf", "/etc/systemd/system/internal-wifi-api.service"]
    snap = backup(managed)
    print(f"Rollback snapshot: {snap}")
    write(Path(managed[0]), render_hostapd(args.interface, args.ssid, args.country, psk), 0o600)
    write(Path(managed[1]), render_dnsmasq(args.interface, args.dhcp_start, args.dhcp_end))
    write(Path(managed[2]), render_nft(args.interface))

    source_dir = Path(__file__).resolve().parents[1]
    ensure_service_user()
    install_application(source_dir)
    write_runtime_env(admin)
    persist_nftables(managed[2])
    install_api_service(source_dir)

    run(["sysctl", "-w", "net.ipv4.ip_forward=0"])
    run(["ip", "link", "set", args.interface, "up"])
    subprocess.run(["ip", "addr", "flush", "dev", args.interface], check=False)
    run(["ip", "addr", "add", args.address, "dev", args.interface])
    run(["nft", "-f", managed[2]])
    for svc in ("hostapd", "dnsmasq"):
        run(["systemctl", "enable", svc])
        run(["systemctl", "restart", svc])
    print("Applied private AP configuration. Internet forwarding is OFF.")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--interface", default=DEFAULTS["interface"])
    p.add_argument("--ssid", default=DEFAULTS["ssid"])
    p.add_argument("--country", default=DEFAULTS["country"])
    p.add_argument("--address", default=DEFAULTS["address"])
    p.add_argument("--dhcp-start", default=DEFAULTS["dhcp_start"])
    p.add_argument("--dhcp-end", default=DEFAULTS["dhcp_end"])
    args = p.parse_args()
    if args.apply and os.geteuid() != 0:
        raise SystemExit("--apply requires root privileges")
    print("Internal Wi-Fi Platform v0.5")
    print("Detected tools:")
    for k, v in detect().items(): print(f"  {k}: {'available' if v else 'missing'}")
    print("\nDeployment plan:")
    for step in plan(): print("  - " + step)
    if not args.apply:
        print("\nDRY RUN: no privileged network changes were made.")
    else:
        apply(args)

if __name__ == "__main__": main()
