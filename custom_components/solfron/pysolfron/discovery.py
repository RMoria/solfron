"""
Discovery functions for Solfron.

Note: not used by the Home Assistant integration; kept as a library utility.
Reads the local (Linux) ARP table, which is only meaningful when running on
the same host/network segment as the inverter.
"""

from __future__ import annotations

from pathlib import Path

from .exceptions import DiscoveryError


ARP_FILE = Path("/proc/net/arp")


def normalize_mac(mac: str) -> str:
    """Normalize a MAC address."""

    return mac.strip().lower().replace("-", ":")


def read_arp_table() -> dict[str, str]:
    """
    Read the Linux ARP table.

    Returns:
        Dictionary containing {mac: ip}
    """

    if not ARP_FILE.exists():
        raise DiscoveryError("/proc/net/arp not found")

    devices: dict[str, str] = {}

    with ARP_FILE.open("r", encoding="utf-8") as arp:
        next(arp)  # Skip header

        for line in arp:
            parts = line.split()

            if len(parts) < 6:
                continue

            ip = parts[0]
            mac = normalize_mac(parts[3])

            if mac == "00:00:00:00:00:00":
                continue

            devices[mac] = ip

    return devices


def find_ip(mac: str) -> str:
    """
    Find the IP address belonging to a MAC address.

    Raises:
        DiscoveryError if not found.
    """

    mac = normalize_mac(mac)

    devices = read_arp_table()

    try:
        return devices[mac]
    except KeyError as err:
        raise DiscoveryError(f"MAC address {mac} not found") from err


def verify_ip(ip: str, mac: str) -> bool:
    """
    Verify that an IP still belongs to a MAC address.
    """

    mac = normalize_mac(mac)

    devices = read_arp_table()

    return devices.get(mac) == ip


def find_mac(ip: str) -> str:
    """
    Find the MAC address belonging to an IP address.

    Raises:
        DiscoveryError if not found.
    """

    devices = read_arp_table()

    for mac, device_ip in devices.items():
        if device_ip == ip:
            return mac

    raise DiscoveryError(f"IP address {ip} not found")
