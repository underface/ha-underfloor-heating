"""Inicjalizacja integracji Home Assistant dla Ogrzewania Podłogowego.

Umożliwia definiowanie rozdzielaczy, stref grzewczych, pętli podłogówki,
automatyczną estymację długości, obliczanie rotametrów oraz pełną diagnostykę
hydrauliczną i termiczną dostępną jako encje i atrybuty HA.
Udostępnia usługi do zmiany konfiguracji stref i pętli w dowolnym momencie.

Wersja: 1.0.4
"""

from __future__ import annotations

import copy
import logging
import os
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from .helpers import (
    clean_loop_name,
    get_loop_device_info,
    get_manifold_device_info,
    get_zone_device_info,
)

from .const import (
    ATTR_APPROACH_LENGTH,
    ATTR_AREA,
    ATTR_LOOP_ID,
    ATTR_NAME,
    ATTR_PIPE_TYPE,
    ATTR_ROTAMETER_FLOW_LH,
    ATTR_ROTAMETER_FLOW_LMIN,
    ATTR_SCREED_THICKNESS,
    ATTR_SCREED_TYPE,
    ATTR_SPACING_CM,
    ATTR_ZONE_ID,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DEFAULT_APPROACH_LENGTH_M,
    DEFAULT_PIPE_SPACING_CM,
    DEFAULT_PIPE_TYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Platformy obsługiwane przez integrację
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
]

# Schematy usług
SET_FLOW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOOP_ID): cv.string,
        vol.Required(ATTR_ROTAMETER_FLOW_LH): vol.Coerce(float),
    }
)

UPDATE_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE_ID): cv.string,
        vol.Optional(ATTR_NAME): cv.string,
        vol.Optional(ATTR_AREA): vol.Coerce(float),
        vol.Optional(ATTR_SCREED_TYPE): cv.string,
        vol.Optional(ATTR_SCREED_THICKNESS): vol.Coerce(float),
        vol.Optional("target_temp"): vol.Coerce(float),
        vol.Optional("heat_load_w_m2"): vol.Coerce(float),
    }
)

UPDATE_LOOP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOOP_ID): cv.string,
        vol.Optional(ATTR_NAME): cv.string,
        vol.Optional(ATTR_SPACING_CM): vol.Coerce(float),
        vol.Optional(ATTR_APPROACH_LENGTH): vol.Coerce(float),
        vol.Optional("loops_in_zone"): vol.Coerce(int),
        vol.Optional(ATTR_PIPE_TYPE): cv.string,
    }
)

URL_BASE = f"/{DOMAIN}_frontend"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Konfiguracja integracji oraz rejestracja zasobów frontendowych (HACS) i panelu bocznego."""
    hass.data.setdefault(DOMAIN, {})

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    card_file = os.path.join(frontend_dir, "underfloor-heating-card.js")
    panel_file = os.path.join(frontend_dir, "underfloor-heating-panel.js")

    if os.path.exists(frontend_dir):
        try:
            from homeassistant.components.http import StaticPathConfig

            paths = [
                StaticPathConfig(URL_BASE, frontend_dir, False),
            ]
            if os.path.exists(card_file):
                paths.append(StaticPathConfig(f"{URL_BASE}/underfloor-heating-card.js", card_file, False))
            if os.path.exists(panel_file):
                paths.append(StaticPathConfig(f"{URL_BASE}/underfloor-heating-panel.js", panel_file, False))

            await hass.http.async_register_static_paths(paths)
            _LOGGER.debug("Zarejestrowano zasoby frontendowe w ścieżce: %s", URL_BASE)
        except Exception:
            try:
                hass.http.register_static_path(URL_BASE, frontend_dir, False)
            except Exception as err:
                _LOGGER.warning("Nie udało się zarejestrować zasobów frontend: %s", err)

    # Rejestracja dedykowanego panelu bocznego w menu głównym Home Assistant
    try:
        from homeassistant.components import panel_custom

        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path="underfloor_heating",
            webcomponent_name="underfloor-heating-panel",
            sidebar_title="Podłogówka",
            sidebar_icon="mdi:heating-coil",
            module_url=f"{URL_BASE}/underfloor-heating-panel.js",
            config={},
            require_admin=False,
        )
        _LOGGER.info("Zarejestrowano dedykowany panel boczny 'Podłogówka' w menu bocznym HA")
    except Exception as err:
        _LOGGER.debug("Błąd rejestracji panelu bocznego panel_custom: %s", err)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Inicjalizacja wpisu konfiguracyjnego."""
    hass.data.setdefault(DOMAIN, {})

    coordinator_data = {
        CONF_MANIFOLDS: dict(entry.options.get(CONF_MANIFOLDS, entry.data.get(CONF_MANIFOLDS, {}))),
        CONF_ZONES: dict(entry.options.get(CONF_ZONES, entry.data.get(CONF_ZONES, {}))),
        CONF_LOOPS: dict(entry.options.get(CONF_LOOPS, entry.data.get(CONF_LOOPS, {}))),
        "rotameter_flows": {},
    }

    # Inicjalizacja domyślnych przepływów z konfiguracji pętli
    for loop_id, loop_data in coordinator_data[CONF_LOOPS].items():
        init_flow = loop_data.get(ATTR_ROTAMETER_FLOW_LH, 90.0)
        coordinator_data["rotameter_flows"][loop_id] = float(init_flow)

    hass.data[DOMAIN][entry.entry_id] = coordinator_data

    # Synchronizacja i budowa 3-poziomowej hierarchii w Rejestrze Urządzeń HA:
    # 1 - Rozdzielacz (Główny)
    #   └── 2 - Pomieszczenie (Połączone przez Rozdzielacz)
    #         └── 3 - Pętle (Połączone przez Pomieszczenie)
    dev_reg = dr.async_get(hass)

    # Poziom 1: Rozdzielacze
    manifold_devs = {}
    for manifold_id, m_data in coordinator_data[CONF_MANIFOLDS].items():
        m_name = m_data.get("name", f"Rozdzielacz {manifold_id}")
        m_area = m_data.get("location", "Kotłownia")
        m_dev = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"manifold_{manifold_id}")},
            name=m_name,
            manufacturer="Podłogówka",
            model="Rozdzielacz Ogrzewania Podłogowego",
            suggested_area=m_area,
        )
        try:
            dev_reg.async_update_device(m_dev.id, name=m_name)
        except Exception:
            pass
        manifold_devs[manifold_id] = m_dev

    default_m_id = list(coordinator_data[CONF_MANIFOLDS].keys())[0] if coordinator_data[CONF_MANIFOLDS] else "parter"
    default_m_dev = manifold_devs.get(default_m_id)

    # Poziom 2: Pomieszczenia (Strefy)
    zone_devs = {}
    for zone_id, z_data in coordinator_data[CONF_ZONES].items():
        z_name = z_data.get("name", zone_id)
        m_id = z_data.get("manifold_id") or default_m_id
        parent_m = manifold_devs.get(m_id) or default_m_dev

        z_dev = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"zone_{zone_id}")},
            name=f"Pomieszczenie: {z_name}",
            manufacturer="Podłogówka",
            model=f"Strefa ({z_data.get('loops_count', 1)} obiegów)",
            suggested_area=z_name,
            via_device=(DOMAIN, f"manifold_{m_id}"),
        )
        try:
            update_kw = {"name": f"Pomieszczenie: {z_name}"}
            if parent_m:
                update_kw["via_device_id"] = parent_m.id
            dev_reg.async_update_device(z_dev.id, **update_kw)
        except Exception:
            pass
        zone_devs[zone_id] = z_dev

    # Poziom 3: Pętle podłogówki
    for loop_id, l_data in coordinator_data[CONF_LOOPS].items():
        z_id = l_data.get("zone_id")
        z_info = coordinator_data[CONF_ZONES].get(z_id, {})
        room_name = l_data.get("zone_name") or z_info.get("name", "Strefa")
        sec_num = l_data.get("section_number", 1)
        clean_name = clean_loop_name(l_data.get("name", ""), sec_num, room_name)

        parent_z = zone_devs.get(z_id)
        m_id = l_data.get("manifold_id") or default_m_id

        parent_via_tuple = (DOMAIN, f"zone_{z_id}") if z_id else (DOMAIN, f"manifold_{m_id}")

        l_dev = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"loop_{loop_id}")},
            name=clean_name,
            manufacturer="Podłogówka",
            model="Pętla Ogrzewania Podłogowego",
            suggested_area=room_name,
            via_device=parent_via_tuple,
        )
        try:
            update_kw = {"name": clean_name}
            if parent_z:
                update_kw["via_device_id"] = parent_z.id
            elif default_m_dev:
                update_kw["via_device_id"] = default_m_dev.id
            dev_reg.async_update_device(l_dev.id, **update_kw)
        except Exception:
            pass

    # Usunięcie starych lub osieroconych urządzeń z rejestru HA
    try:
        active_identifiers = set()
        for m_id in coordinator_data[CONF_MANIFOLDS]:
            active_identifiers.add((DOMAIN, f"manifold_{m_id}"))
        for z_id in coordinator_data[CONF_ZONES]:
            active_identifiers.add((DOMAIN, f"zone_{z_id}"))
        for l_id in coordinator_data[CONF_LOOPS]:
            active_identifiers.add((DOMAIN, f"loop_{l_id}"))

        existing_devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
        for dev in existing_devices:
            if not any(ident in active_identifiers for ident in dev.identifiers):
                _LOGGER.info("Usuwanie osieroconego urządzenia z rejestru HA: %s (%s)", dev.name, dev.id)
                dev_reg.async_remove_device(dev.id)
    except Exception as err:
        _LOGGER.debug("Błąd czyszczenia osieroconych urządzeń: %s", err)

    # Rejestracja platform (sensor, number, binary_sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 1. Usługa ustawienia rotametru
    async def handle_set_flow(call: ServiceCall) -> None:
        loop_id = call.data[ATTR_LOOP_ID]
        new_flow = call.data[ATTR_ROTAMETER_FLOW_LH]
        _LOGGER.info("Ustawianie przepływu rotametru dla pętli %s na %s l/h", loop_id, new_flow)

        if entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN][entry.entry_id]["rotameter_flows"][loop_id] = float(new_flow)
            async_notify_update(hass, entry.entry_id)

    hass.services.async_register(
        DOMAIN,
        "set_rotameter_flow",
        handle_set_flow,
        schema=SET_FLOW_SCHEMA,
    )

    # 2. Usługa aktualizacji parametrów strefy (metraż m², wylewka, itp.)
    async def handle_update_zone(call: ServiceCall) -> None:
        zone_id = call.data[ATTR_ZONE_ID]
        new_options = copy.deepcopy(dict(entry.options or entry.data))
        new_options.setdefault(CONF_ZONES, {})

        if zone_id in new_options[CONF_ZONES]:
            z = new_options[CONF_ZONES][zone_id]
            for key in (ATTR_NAME, ATTR_AREA, ATTR_SCREED_TYPE, ATTR_SCREED_THICKNESS, "target_temp", "heat_load_w_m2"):
                if key in call.data:
                    z[key] = call.data[key]
            _LOGGER.info("Zaktualizowano parametry strefy %s: %s", zone_id, z)
            hass.config_entries.async_update_entry(entry, options=new_options)

    hass.services.async_register(
        DOMAIN,
        "update_zone",
        handle_update_zone,
        schema=UPDATE_ZONE_SCHEMA,
    )

    # 3. Usługa aktualizacji parametrów pętli (rozstaw, podejście, rura)
    async def handle_update_loop(call: ServiceCall) -> None:
        loop_id = call.data[ATTR_LOOP_ID]
        new_options = copy.deepcopy(dict(entry.options or entry.data))
        new_options.setdefault(CONF_LOOPS, {})

        if loop_id in new_options[CONF_LOOPS]:
            l = new_options[CONF_LOOPS][loop_id]
            for key in (ATTR_NAME, ATTR_SPACING_CM, ATTR_APPROACH_LENGTH, "loops_in_zone", ATTR_PIPE_TYPE):
                if key in call.data:
                    l[key] = call.data[key]
            _LOGGER.info("Zaktualizowano parametry pętli %s: %s", loop_id, l)
            hass.config_entries.async_update_entry(entry, options=new_options)

    hass.services.async_register(
        DOMAIN,
        "update_loop",
        handle_update_loop,
        schema=UPDATE_LOOP_SCHEMA,
    )

    # 4. Usługa zapisu pełnej konfiguracji pomieszczeń i pętli z interaktywnego panelu Lovelace/modala
    async def handle_save_manifold_config(call: ServiceCall) -> None:
        manifold_id = call.data["manifold_id"]
        rooms = call.data.get("rooms", [])
        new_options = copy.deepcopy(dict(entry.options or entry.data))
        new_options.setdefault(CONF_MANIFOLDS, {})
        new_options.setdefault(CONF_ZONES, {})
        new_options.setdefault(CONF_LOOPS, {})

        if manifold_id not in new_options[CONF_MANIFOLDS]:
            _LOGGER.warning("Rozdzielacz %s nie istnieje w konfiguracji", manifold_id)
            return

        m_data = new_options[CONF_MANIFOLDS][manifold_id]
        default_screed = m_data.get(ATTR_SCREED_TYPE, "cement")
        default_thick = float(m_data.get(ATTR_SCREED_THICKNESS, 50.0))

        # Usuń dotychczasowe pętle przypisane do tego rozdzielacza
        existing_loops = new_options[CONF_LOOPS]
        for lid in list(existing_loops.keys()):
            if existing_loops[lid].get("manifold_id") == manifold_id:
                existing_loops.pop(lid, None)

        # Usuń dotychczasowe strefy przypisane do tego rozdzielacza
        existing_zones = new_options[CONF_ZONES]
        for zid in list(existing_zones.keys()):
            if existing_zones[zid].get("manifold_id") == manifold_id:
                existing_zones.pop(zid, None)

        global_loop_idx = 1
        for room_idx, room in enumerate(rooms):
            r_name = str(room.get("name", f"Pomieszczenie {room_idx + 1}")).strip()
            r_area = float(room.get("area", 15.0))
            raw_screed = str(room.get("screed", "default")).lower()
            if "cement" in raw_screed:
                r_screed = "cement"
                r_thick = 50.0
                r_override = "cement"
            elif "anhydr" in raw_screed:
                r_screed = "anhydrite"
                r_thick = 45.0
                r_override = "anhydrite"
            elif "such" in raw_screed or "dry" in raw_screed:
                r_screed = "dry_screed"
                r_thick = 25.0
                r_override = "dry_screed"
            else:
                r_screed = default_screed
                r_thick = default_thick
                r_override = "default"

            # Utwórz unikalny identyfikator strefy
            z_id = (
                r_name.lower()
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
            ) or f"strefa_{room_idx + 1}"

            loops_list = room.get("loops", [{"flow": 1.5}])
            loops_count = len(loops_list)
            area_per_loop = round(r_area / max(1, loops_count), 2)

            created_loop_ids = []
            for l_idx, l_data in enumerate(loops_list):
                flow_lmin = float(l_data.get("flow", 1.5))
                flow_lh = round(flow_lmin * 60.0, 1)
                lid = f"petla_{manifold_id}_{global_loop_idx}"
                created_loop_ids.append(lid)

                existing_loops[lid] = {
                    "name": f"Pętla {global_loop_idx}: {r_name}",
                    "manifold_id": manifold_id,
                    "section_number": global_loop_idx,
                    "zone_name": r_name,
                    "zone_id": z_id,
                    "area_m2": area_per_loop,
                    "pipe_type": DEFAULT_PIPE_TYPE,
                    "spacing_cm": DEFAULT_PIPE_SPACING_CM,
                    "approach_length_m": DEFAULT_APPROACH_LENGTH_M,
                    "screed_type": r_screed,
                    "screed_thickness_mm": r_thick,
                    "screed_override": r_override,
                    "floor_covering": "tiles",
                    "loops_in_zone": loops_count,
                    ATTR_ROTAMETER_FLOW_LH: flow_lh,
                    ATTR_ROTAMETER_FLOW_LMIN: flow_lmin,
                }
                # Aktualizacja stanu rotametrów w koordynatorze
                if entry.entry_id in hass.data[DOMAIN]:
                    hass.data[DOMAIN][entry.entry_id]["rotameter_flows"][lid] = flow_lh

                global_loop_idx += 1

            existing_zones[z_id] = {
                "name": r_name,
                "manifold_id": manifold_id,
                "area_m2": r_area,
                "screed_type": r_screed,
                "screed_thickness_mm": r_thick,
                "loops_count": loops_count,
                "loops": created_loop_ids,
                "target_temp": 21.0,
                "heat_load_w_m2": 45.0,
                "floor_covering": "tiles",
            }

        # Zaktualizuj liczbę sekcji rozdzielacza
        m_data["sections_count"] = global_loop_idx - 1
        _LOGGER.info(
            "Zapisano konfigurację rozdzielacza %s: %d pomieszczeń, %d pętli",
            manifold_id,
            len(rooms),
            global_loop_idx - 1,
        )
        hass.config_entries.async_update_entry(entry, options=new_options)

    hass.services.async_register(
        DOMAIN,
        "save_manifold_configuration",
        handle_save_manifold_config,
    )

    # Nasłuchiwanie na aktualizację opcji konfiguracyjnych
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Obsługa aktualizacji konfiguracji integracji."""
    await hass.config_entries.async_reload(entry.entry_id)


def async_notify_update(hass: HomeAssistant, entry_id: str) -> None:
    """Wysyła sygnał aktualizacji do powiązanych encji."""
    from homeassistant.helpers.dispatcher import async_dispatcher_send

    async_dispatcher_send(hass, f"{DOMAIN}_{entry_id}_update")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odładowanie wpisu integracji."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
