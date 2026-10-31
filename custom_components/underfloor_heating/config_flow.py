"""Kreator konfiguracji: Rozdzielacz → Pętle (uproszczony 2-krokowy flow).

Wersja: 1.2.0

Nowy flow – tylko 2 kroki:
1. async_step_add_manifold  – nazwa, liczba pętli, lokalizacja
2. async_step_configure_loops – dynamiczny formularz dla każdej pętli naraz

OptionsFlow:
- add_manifold    → od razu krok 1
- edit_loops      → wybierz rozdzielacz → krok 2
- remove_manifold → usuń rozdzielacz
- save            → zapisz i zamknij
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .calculations import calculate_thermal_properties
from .const import (
    ATTR_APPROACH_LENGTH,
    ATTR_AREA,
    ATTR_FLOOR_COVERING,
    ATTR_NAME,
    ATTR_PIPE_TYPE,
    ATTR_ROTAMETER_FLOW_LH,
    ATTR_ROTAMETER_FLOW_LMIN,
    ATTR_SCREED_THICKNESS,
    ATTR_SCREED_TYPE,
    ATTR_SPACING_CM,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DEFAULT_APPROACH_LENGTH_M,
    DEFAULT_NAME,
    DEFAULT_PIPE_SPACING_CM,
    DEFAULT_PIPE_TYPE,
    DOMAIN,
    FLOOR_COVERINGS,
    PIPE_TYPES,
    SCREED_TYPES,
)

_LOGGER = logging.getLogger(__name__)

# Domyślne nazwy pomieszczeń dla kolejnych pętli
_DEFAULT_ROOM_NAMES = [
    "Salon", "Kuchnia", "Łazienka", "Sypialnia", "Gabinet",
    "Korytarz", "Garderoba", "WC", "Pralnia", "Taras",
    "Pokój 1", "Pokój 2", "Pokój 3", "Pokój 4", "Pokój 5",
    "Pokój 6", "Pokój 7", "Pokój 8", "Pokój 9", "Pokój 10",
    "Pokój 11", "Pokój 12", "Pokój 13", "Pokój 14",
]


def _generate_default_loops_for_manifold(
    manifold_id: str,
    sections_count: int,
    existing_loops: dict,
) -> dict:
    """Generuje pętle dla rozdzielacza od 1 do sections_count."""
    result = dict(existing_loops)
    # Filtruj obecne pętle tego rozdzielacza
    current_m_loops = {
        lid: l for lid, l in result.items() if l.get("manifold_id") == manifold_id
    }

    # Dodaj brakujące
    for i in range(1, sections_count + 1):
        loop_id = f"petla_{manifold_id}_{i}"
        if loop_id not in result:
            result[loop_id] = {
                "name": f"Pętla {i}",
                "manifold_id": manifold_id,
                "section_number": i,
                "zone_name": f"Obwód {i}",
                "area_m2": 15.0,
                "pipe_type": DEFAULT_PIPE_TYPE,
                "spacing_cm": DEFAULT_PIPE_SPACING_CM,
                "approach_length_m": DEFAULT_APPROACH_LENGTH_M,
                "screed_type": "cement",
                "screed_thickness_mm": 50.0,
                "floor_covering": "tiles",
                "loops_in_zone": 1,
                ATTR_ROTAMETER_FLOW_LH: 90.0,
                ATTR_ROTAMETER_FLOW_LMIN: 1.5,
            }

    # Usuń nadmiarowe jeśli sekcje zostały zmniejszone
    for lid, l in list(result.items()):
        if l.get("manifold_id") == manifold_id and l.get("section_number", 0) > sections_count:
            result.pop(lid, None)

    return result


def _make_manifold_id(name: str) -> str:
    """Tworzy bezpieczny identyfikator na podstawie nazwy rozdzielacza."""
    m_id = (
        name.lower()
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
    return m_id or "rozdzielacz"


def _build_loops_schema(sections_count: int, existing_loops: dict, manifold_id: str) -> vol.Schema:
    """Buduje dynamiczny schemat formularza dla wszystkich pętli naraz."""
    screed_choices = {k: v["name"] for k, v in SCREED_TYPES.items()}
    fields: dict = {}

    for i in range(1, sections_count + 1):
        loop_id = f"petla_{manifold_id}_{i}"
        loop_data = existing_loops.get(loop_id, {})

        default_room = loop_data.get("zone_name") or (
            _DEFAULT_ROOM_NAMES[i - 1] if i <= len(_DEFAULT_ROOM_NAMES) else f"Pomieszczenie {i}"
        )
        default_area = float(loop_data.get("area_m2", 15.0))
        default_flow = float(loop_data.get(ATTR_ROTAMETER_FLOW_LMIN, 1.5))
        default_screed = loop_data.get("screed_type", "cement")
        default_thick = float(loop_data.get("screed_thickness_mm", 50.0))

        fields[vol.Required(f"loop_{i}_room", default=default_room)] = str
        fields[vol.Required(f"loop_{i}_area", default=default_area)] = vol.Coerce(float)
        fields[vol.Required(f"loop_{i}_flow", default=default_flow)] = vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=6.0)
        )
        fields[vol.Required(f"loop_{i}_screed", default=default_screed)] = vol.In(screed_choices)
        fields[vol.Required(f"loop_{i}_thickness", default=default_thick)] = vol.Coerce(float)

    return vol.Schema(fields)


# ===========================================================================
#  KONFIGURACJA PIERWSZA INSTALACJI
# ===========================================================================

class UnderfloorHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Pierwsza konfiguracja integracji – krok 1 → krok 2."""

    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        # Tymczasowe dane przekazywane między krokami
        self._pending_manifold_id: str = ""
        self._pending_manifold_name: str = ""
        self._pending_sections_count: int = 8
        self._pending_data: dict = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok startowy – od razu przechodzi do dodania pierwszego rozdzielacza."""
        # Inicjalizuj dane i przekieruj do kroku add_manifold
        self._pending_data = {
            CONF_MANIFOLDS: {},
            CONF_ZONES: {},
            CONF_LOOPS: {},
        }
        return await self.async_step_add_manifold()

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 1: Nazwa rozdzielacza, liczba pętli, lokalizacja."""
        errors: dict[str, str] = {}

        if user_input is not None:
            m_name = user_input["name"].strip()
            sections_count = int(user_input["sections_count"])
            location = user_input.get("location", "Kotłownia / Parter").strip()

            m_id = _make_manifold_id(m_name)
            if not m_id:
                m_id = "rozdzielacz_parter"

            # Zapisz tymczasowo do przekazania do kroku 2
            self._pending_manifold_id = m_id
            self._pending_manifold_name = m_name
            self._pending_sections_count = sections_count

            self._pending_data.setdefault(CONF_MANIFOLDS, {})[m_id] = {
                "name": m_name,
                "location": location,
                "sections_count": sections_count,
            }
            self._pending_data.setdefault(CONF_LOOPS, {})
            self._pending_data[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, sections_count, self._pending_data[CONF_LOOPS]
            )

            return await self.async_step_configure_loops()

        schema = vol.Schema(
            {
                vol.Required("name", default="Rozdzielacz Parter"): str,
                vol.Required("sections_count", default=8): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=24)
                ),
                vol.Optional("location", default="Kotłownia / Parter"): str,
            }
        )
        return self.async_show_form(
            step_id="add_manifold",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_configure_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 2: Dynamiczny formularz dla wszystkich pętli naraz."""
        m_id = self._pending_manifold_id
        m_name = self._pending_manifold_name
        sections_count = self._pending_sections_count
        existing_loops = self._pending_data.get(CONF_LOOPS, {})

        if user_input is not None:
            # Zapisz dane pętli
            for i in range(1, sections_count + 1):
                loop_id = f"petla_{m_id}_{i}"
                room_name = user_input[f"loop_{i}_room"].strip()
                area = float(user_input[f"loop_{i}_area"])
                flow_lmin = float(user_input[f"loop_{i}_flow"])
                screed = user_input[f"loop_{i}_screed"]
                thickness = float(user_input[f"loop_{i}_thickness"])
                flow_lh = round(flow_lmin * 60.0, 1)

                if loop_id in self._pending_data[CONF_LOOPS]:
                    l = self._pending_data[CONF_LOOPS][loop_id]
                    l["name"] = f"Pętla {i}: {room_name}"
                    l["zone_name"] = room_name
                    l["area_m2"] = area
                    l["loops_in_zone"] = 1
                    l["screed_type"] = screed
                    l["screed_thickness_mm"] = thickness
                    l[ATTR_ROTAMETER_FLOW_LH] = flow_lh
                    l[ATTR_ROTAMETER_FLOW_LMIN] = flow_lmin

            return self.async_create_entry(title=DEFAULT_NAME, data=self._pending_data)

        schema = _build_loops_schema(sections_count, existing_loops, m_id)

        return self.async_show_form(
            step_id="configure_loops",
            data_schema=schema,
            description_placeholders={
                "manifold_name": m_name,
                "sections_count": str(sections_count),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return UnderfloorHeatingOptionsFlowHandler(config_entry)


# ===========================================================================
#  OPTIONS FLOW (zarządzanie po instalacji)
# ===========================================================================

class UnderfloorHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Zarządzanie instalacją – menu 3 akcji."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        try:
            super().__init__(config_entry)
        except TypeError:
            super().__init__()
        self._config_entry = config_entry
        self.options = copy.deepcopy(dict(config_entry.options or config_entry.data))
        self.options.setdefault(CONF_MANIFOLDS, {})
        self.options.setdefault(CONF_ZONES, {})
        self.options.setdefault(CONF_LOOPS, {})

        self._active_manifold_id: str | None = None
        self._pending_sections_count: int = 8
        self._pending_manifold_name: str = ""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Główne menu opcji – 3 akcje."""
        actions = {
            "add_manifold": "🎛️ Dodaj nowy rozdzielacz",
            "edit_loops": "✏️ Edytuj pętle rozdzielacza",
            "remove_manifold": "🗑️ Usuń rozdzielacz",
            "save": "💾 Zapisz i zastosuj zmiany",
        }

        if user_input is not None:
            choice = user_input.get("action")
            if choice == "add_manifold":
                return await self.async_step_add_manifold()
            if choice == "edit_loops":
                return await self.async_step_select_manifold_for_loops()
            if choice == "remove_manifold":
                return await self.async_step_remove_manifold()
            # save
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("action", default="add_manifold"): vol.In(actions),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ======================== DODAJ ROZDZIELACZ ========================

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 1: Dane nowego rozdzielacza."""
        errors: dict[str, str] = {}
        default_name = f"Rozdzielacz {len(self.options[CONF_MANIFOLDS]) + 1}"

        if user_input is not None:
            m_name = user_input["name"].strip()
            sections_count = int(user_input["sections_count"])
            location = user_input.get("location", "").strip()

            m_id = _make_manifold_id(m_name)
            base_id = m_id
            cnt = 1
            while m_id in self.options[CONF_MANIFOLDS]:
                m_id = f"{base_id}_{cnt}"
                cnt += 1

            self.options[CONF_MANIFOLDS][m_id] = {
                "name": m_name,
                "location": location,
                "sections_count": sections_count,
            }
            self.options[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, sections_count, self.options[CONF_LOOPS]
            )

            self._active_manifold_id = m_id
            self._pending_sections_count = sections_count
            self._pending_manifold_name = m_name

            # Bezpośrednio do konfiguracji pętli
            return await self.async_step_configure_loops()

        schema = vol.Schema(
            {
                vol.Required("name", default=default_name): str,
                vol.Required("sections_count", default=8): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=24)
                ),
                vol.Optional("location", default="Kotłownia / Parter"): str,
            }
        )
        return self.async_show_form(
            step_id="add_manifold",
            data_schema=schema,
            errors=errors,
        )

    # ======================== KONFIGURACJA PĘTLI =======================

    async def async_step_select_manifold_for_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybierz rozdzielacz do edycji pętli (przy edit_loops)."""
        manifolds = {
            m_id: f"{m['name']} ({m.get('sections_count', 8)} pętli)"
            for m_id, m in self.options[CONF_MANIFOLDS].items()
        }

        if not manifolds:
            return await self.async_step_init()

        if len(manifolds) == 1:
            m_id = list(manifolds.keys())[0]
            self._active_manifold_id = m_id
            m = self.options[CONF_MANIFOLDS][m_id]
            self._pending_sections_count = int(m.get("sections_count", 8))
            self._pending_manifold_name = m.get("name", m_id)
            return await self.async_step_configure_loops()

        if user_input is not None:
            m_id = user_input["manifold_id"]
            self._active_manifold_id = m_id
            m = self.options[CONF_MANIFOLDS][m_id]
            self._pending_sections_count = int(m.get("sections_count", 8))
            self._pending_manifold_name = m.get("name", m_id)
            return await self.async_step_configure_loops()

        schema = vol.Schema(
            {
                vol.Required("manifold_id", default=list(manifolds.keys())[0]): vol.In(manifolds),
            }
        )
        return self.async_show_form(step_id="select_manifold_for_loops", data_schema=schema)

    async def async_step_configure_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 2: Dynamiczny formularz dla wszystkich pętli rozdzielacza naraz."""
        m_id = self._active_manifold_id
        m_name = self._pending_manifold_name
        sections_count = self._pending_sections_count
        existing_loops = self.options.get(CONF_LOOPS, {})

        if user_input is not None:
            for i in range(1, sections_count + 1):
                loop_id = f"petla_{m_id}_{i}"
                room_name = user_input[f"loop_{i}_room"].strip()
                area = float(user_input[f"loop_{i}_area"])
                flow_lmin = float(user_input[f"loop_{i}_flow"])
                screed = user_input[f"loop_{i}_screed"]
                thickness = float(user_input[f"loop_{i}_thickness"])
                flow_lh = round(flow_lmin * 60.0, 1)

                if loop_id in self.options[CONF_LOOPS]:
                    l = self.options[CONF_LOOPS][loop_id]
                    l["name"] = f"Pętla {i}: {room_name}"
                    l["zone_name"] = room_name
                    l["area_m2"] = area
                    l["loops_in_zone"] = 1
                    l["screed_type"] = screed
                    l["screed_thickness_mm"] = thickness
                    l[ATTR_ROTAMETER_FLOW_LH] = flow_lh
                    l[ATTR_ROTAMETER_FLOW_LMIN] = flow_lmin

                    # Utwórz/aktualizuj wirtualną strefę
                    z_id = _make_manifold_id(room_name) or f"strefa_{i}"
                    self.options[CONF_ZONES][z_id] = {
                        "name": room_name,
                        "manifold_id": m_id,
                        "area_m2": area,
                        "screed_type": screed,
                        "screed_thickness_mm": thickness,
                        "loops_count": 1,
                    }

            return self.async_create_entry(title="", data=self.options)

        schema = _build_loops_schema(sections_count, existing_loops, m_id)

        return self.async_show_form(
            step_id="configure_loops",
            data_schema=schema,
            description_placeholders={
                "manifold_name": m_name,
                "sections_count": str(sections_count),
            },
        )

    # ======================== USUŃ ROZDZIELACZ ========================

    async def async_step_remove_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie rozdzielacza wraz ze wszystkimi jego pętlami."""
        manifolds = {m_id: m["name"] for m_id, m in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            m_id = user_input["manifold_id"]
            # Usuń pętle rozdzielacza
            for lid in list(self.options[CONF_LOOPS].keys()):
                if self.options[CONF_LOOPS][lid].get("manifold_id") == m_id:
                    self.options[CONF_LOOPS].pop(lid, None)
            # Usuń rozdzielacz
            self.options[CONF_MANIFOLDS].pop(m_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)})
        return self.async_show_form(step_id="remove_manifold", data_schema=schema)
