"""Funkcje pomocnicze dla integracji Ogrzewanie Podłogowe.

Zapewnia jednolite tworzenie informacji o urządzeniach (DeviceInfo)
oraz zachowanie ścisłej 3-poziomowej hierarchii:
Poziom 1: Rozdzielacz (Manifold)
  └── Poziom 2: Pomieszczenie / Strefa (Zone)
        └── Poziom 3: Pętle podłogówki (Loops)

Wersja: 1.4.0
"""

from __future__ import annotations

from typing import Any
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_ZONES, DOMAIN


def slugify_id(name: str) -> str:
    """Tworzy bezpieczny identyfikator ASCII z polskiej nazwy (zamienia spacje i polskie znaki diakrytyczne)."""
    clean = (
        str(name or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("ł", "l")
        .replace("ą", "a")
        .replace("ę", "e")
        .replace("ó", "o")
        .replace("ś", "s")
        .replace("ź", "z")
        .replace("ż", "z")
        .replace("ć", "c")
        .replace("ń", "n")
    )
    # Usuń wszelkie pozostałe znaki niealfanumeryczne (z wyjątkiem podkreślenia)
    sanitized = "".join(c for c in clean if c.isalnum() or c == "_")
    return sanitized or "obiekt"


def clean_loop_name(raw_name: str, section_number: int | str = 1, room_name: str = "Strefa") -> str:
    """Oczyszcza nazwę pętli z powielonych prefiksów 'Pętla:' i formatuje jednolicie."""
    clean = str(raw_name or "").strip()
    while clean.startswith("Pętla:"):
        clean = clean[len("Pętla:"):].strip()
    while clean.startswith("Pętla "):
        parts = clean.split(":", 1)
        if len(parts) == 2 and ("Pętla" in parts[1] or "petla" in parts[1].lower()):
            clean = parts[1].strip()
        else:
            break
    while clean.startswith("Pętla:"):
        clean = clean[len("Pętla:"):].strip()

    if not clean or clean.lower() in ("pętla", "petla", "loop"):
        return f"Pętla {section_number}: {room_name}"
    return clean


def get_manifold_device_info(manifold_id: str, m_data: dict[str, Any]) -> DeviceInfo:
    """Zwraca DeviceInfo dla rozdzielacza (urządzenie główne - Poziom 1)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"manifold_{manifold_id}")},
        name=m_data.get("name", f"Rozdzielacz {manifold_id}"),
        manufacturer="Podłogówka",
        model="Rozdzielacz Ogrzewania Podłogowego",
        suggested_area=m_data.get("location", "Kotłownia"),
    )


def get_zone_device_info(
    zone_id: str,
    z_data: dict[str, Any],
    default_manifold_id: str = "parter",
) -> DeviceInfo:
    """Zwraca DeviceInfo dla pomieszczenia (urządzenie podrzędne rozdzielacza - Poziom 2)."""
    m_id = z_data.get("manifold_id") or default_manifold_id
    z_name = z_data.get("name", zone_id)
    loops_cnt = z_data.get("loops_count", len(z_data.get("loops", []))) or 1
    return DeviceInfo(
        identifiers={(DOMAIN, f"zone_{zone_id}")},
        name=f"Pomieszczenie: {z_name}",
        manufacturer="Podłogówka",
        model=f"Strefa ({loops_cnt} obiegów)",
        suggested_area=z_name,
        via_device=(DOMAIN, f"manifold_{m_id}"),
    )


def get_loop_device_info(
    loop_id: str,
    l_data: dict[str, Any],
    zones_data: dict[str, Any] | None = None,
    default_manifold_id: str = "parter",
) -> DeviceInfo:
    """Zwraca DeviceInfo dla pętli (urządzenie podrzędne pomieszczenia - Poziom 3)."""
    z_id = l_data.get("zone_id")
    z_data = (zones_data or {}).get(z_id, {}) if z_id else {}
    room_name = l_data.get("zone_name") or z_data.get("name", "Strefa")
    sec_num = l_data.get("section_number", 1)

    clean_name = clean_loop_name(l_data.get("name", ""), sec_num, room_name)
    m_id = l_data.get("manifold_id") or default_manifold_id

    # Hierarchia: Pętla podłączona do Pomieszczenia (strefy)
    parent_via = (DOMAIN, f"zone_{z_id}") if z_id else (DOMAIN, f"manifold_{m_id}")

    return DeviceInfo(
        identifiers={(DOMAIN, f"loop_{loop_id}")},
        name=clean_name,
        manufacturer="Podłogówka",
        model="Pętla Ogrzewania Podłogowego",
        suggested_area=room_name,
        via_device=parent_via,
    )
