"""Inicjalizacja integracji Home Assistant dla Ogrzewania Podłogowego.

Umożliwia definiowanie rozdzielaczy, stref grzewczych, pętli podłogówki,
automatyczną estymację długości, obliczanie rotametrów oraz pełną diagnostykę
hydrauliczną i termiczną dostępną jako encje i atrybuty HA.
Wspiera automatyczną instalację i obsługę przez HACS.

Wersja: 1.0.0
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_LOOP_ID,
    ATTR_ROTAMETER_FLOW_LH,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Platformy obsługiwane przez integrację
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
]

# Schemat usługi ustawienia przepływu rotametru
SET_FLOW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOOP_ID): cv.string,
        vol.Required(ATTR_ROTAMETER_FLOW_LH): vol.Coerce(float),
    }
)

URL_BASE = f"/{DOMAIN}_frontend"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Konfiguracja integracji oraz rejestracja zasobów frontendowych (HACS)."""
    hass.data.setdefault(DOMAIN, {})

    # Rejestracja ścieżki statycznej dla karty Lovelace (wsparcie HACS bez konieczności ręcznego kopiowania do www)
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    card_file = os.path.join(frontend_dir, "underfloor-heating-card.js")

    if os.path.exists(card_file):
        try:
            # Nowsze wersje Home Assistant Core
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths([
                StaticPathConfig(f"{URL_BASE}/underfloor-heating-card.js", card_file, False)
            ])
            _LOGGER.debug("Zarejestrowano kartę Lovelace w ścieżce: %s/underfloor-heating-card.js", URL_BASE)
        except Exception:
            try:
                # Starsze wersje Home Assistant Core (fallback)
                hass.http.register_static_path(f"{URL_BASE}/underfloor-heating-card.js", card_file, False)
            except Exception as err:
                _LOGGER.warning("Nie udało się automatycznie zarejestrować karty frontend: %s", err)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Inicjalizacja wpisu konfiguracyjnego."""
    hass.data.setdefault(DOMAIN, {})

    # Główny magazyn stanu dla danego wpisu konfiguracyjnego
    coordinator_data = {
        CONF_MANIFOLDS: dict(entry.options.get(CONF_MANIFOLDS, entry.data.get(CONF_MANIFOLDS, {}))),
        CONF_ZONES: dict(entry.options.get(CONF_ZONES, entry.data.get(CONF_ZONES, {}))),
        CONF_LOOPS: dict(entry.options.get(CONF_LOOPS, entry.data.get(CONF_LOOPS, {}))),
        # Przechowywanie aktualnych wartości rotametrów w pamięci podręcznej
        "rotameter_flows": {},
    }

    # Inicjalizacja domyślnych przepływów z konfiguracji pętli
    for loop_id, loop_data in coordinator_data[CONF_LOOPS].items():
        init_flow = loop_data.get(ATTR_ROTAMETER_FLOW_LH, 90.0)
        coordinator_data["rotameter_flows"][loop_id] = float(init_flow)

    hass.data[DOMAIN][entry.entry_id] = coordinator_data

    # Rejestracja platform (sensor, number, binary_sensor)
    await hass.config_entries.async_forward_entry_set(entry, PLATFORMS)

    # Rejestracja usługi serwisowej w Home Assistant: underfloor_heating.set_rotameter_flow
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
