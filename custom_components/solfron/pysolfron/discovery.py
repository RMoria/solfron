"""
Discovery functions for Solfron.

Reads the local (Linux) ARP table to map the inverter's MAC address to its
current IP address. This is only meaningful when running on the same network
segment as the inverter (e.g. Home Assistant OS, which uses host networking).
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
import socket

from .exceptions import DiscoveryError


ARP_FILE = Path("/proc/net/arp")

# ATF_COM: the entry is complete (has a valid hardware address).
_ATF_COM = 0x2

# UDP "discard" port; any port works, we only need the kernel to ARP the host.
_PRIME_PORT = 9


def normalize_mac(mac: str) -> str:
    """Normalize a MAC address."""

    return mac.strip().lower().replace("-", ":")


def read_arp_entries() -> list[tuple[str, str]]:
    """
    Read the complete entries of the Linux ARP table.

    Returns:
        A list of (ip, mac) tuples. Incomplete or failed entries are skipped,
        and one MAC may appear with several IPs.
    """

    if not ARP_FILE.exists():
        raise DiscoveryError("/proc/net/arp not found")

    entries: list[tuple[str, str]] = []

    with ARP_FILE.open("r", encoding="utf-8") as arp:
        next(arp, None)  # Skip header

        for line in arp:
            parts = line.split()

            if len(parts) < 6:
                continue

            ip = parts[0]
            mac = normalize_mac(parts[3])

            try:
                flags = int(parts[2], 16)
            except ValueError:
                continue

            if not flags & _ATF_COM or mac == "00:00:00:00:00:00":
                continue

            entries.append((ip, mac))

    return entries


def read_arp_table() -> dict[str, str]:
    """
    Read the Linux ARP table.

    Returns:
        Dictionary containing {mac: ip}. Prefer read_arp_entries(), which keeps
        every IP when one MAC has several.
    """

    return {mac: ip for ip, mac in read_arp_entries()}


def find_ips(mac: str) -> list[str]:
    """Return every IP the ARP table currently maps to a MAC address."""

    mac = normalize_mac(mac)
    return [ip for ip, entry_mac in read_arp_entries() if entry_mac == mac]


def find_ip(mac: str) -> str:
    """
    Find the IP address belonging to a MAC address.

    Raises:
        DiscoveryError if not found.
    """

    ips = find_ips(mac)
    if not ips:
        raise DiscoveryError(f"MAC address {normalize_mac(mac)} not found")
    return ips[0]


def verify_ip(ip: str, mac: str) -> bool:
    """Verify that an IP still belongs to a MAC address."""

    return ip in find_ips(mac)


def find_mac(ip: str) -> str:
    """
    Find the MAC address belonging to an IP address.

    Raises:
        DiscoveryError if not found.
    """

    for entry_ip, mac in read_arp_entries():
        if entry_ip == ip:
            return mac

    raise DiscoveryError(f"IP address {ip} not found")


def prime_arp(reference_ip: str) -> int:
    """
    Make the kernel resolve every address in the /24 around reference_ip.

    Sends one empty UDP datagram to each host. Hosts that are present answer
    the resulting ARP request, so they appear in the ARP table shortly after.
    Only runs for private IPv4 addresses.

    Returns:
        The number of addresses probed.
    """

    try:
        address = ipaddress.IPv4Address(reference_ip)
    except ValueError:
        return 0

    if not address.is_private:
        return 0

    network = ipaddress.IPv4Network(f"{address}/24", strict=False)
    probed = 0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setblocking(False)
        for host in network.hosts():
            try:
                sock.sendto(b"", (str(host), _PRIME_PORT))
                probed += 1
            except OSError:
                continue

    return probed
