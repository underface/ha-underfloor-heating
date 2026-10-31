"""Kreator konfiguracji: Rozdzielacz → Pętle (uproszczony 2-krokowy flow).

Wersja: 1.2.0

Nowy flow – tylko 2 kroki:
1. async_step_add_manifold  – nazwa, liczba pętli, lokalizacja, domyślna wylewka rozdzielacza
2. async_step_configure_loops – dynamiczny formularz dla każdej pętli (pomieszczenie, m², l/min, opcjonalna inna wylewka)

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
from homeassistant.helpers import config_validation as cv, selector
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
    "Salon 1", "Salon 2", "Kuchnia", "Łazienka", "Korytarz",
    "Gabinet", "Sypialnia 1", "Sypialnia 2", "Garderoba", "Pralnia",
    "Wiatrołap", "Pokój 1", "Pokój 2", "Pokój 3", "Pokój 4",
    "Pokój 5", "Pokój 6", "Pokój 7", "Pokój 8", "Pokój 9",
    "Pokój 10", "Pokój 11", "Pokój 12", "Pokój 13",
]

SCREED_CHOICES = {
    "cement": "Wylewka cementowa tradycyjna",
    "anhydrite": "Wylewka anhydrytowa płynna",
    "dry_screed": "Sucha zabudowa (płyty gipsowo-włóknowe)",
}

SCREED_OVERRIDE_CHOICES = {
    "default": "Domyślna rozdzielacza",
    "cement": "Wylewka cementowa tradycyjna",
    "anhydrite": "Wylewka anhydrytowa płynna",
    "dry_screed": "Sucha zabudowa (płyty gipsowo-włóknowe)",
}

SCREED_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            {"value": "cement", "label": "Wylewka cementowa tradycyjna"},
            {"value": "anhydrite", "label": "Wylewka anhydrytowa płynna"},
            {"value": "dry_screed", "label": "Sucha zabudowa (płyty gipsowo-włóknowe)"},
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

SCREED_OVERRIDE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            {"value": "default", "label": "Domyślna rozdzielacza"},
            {"value": "cement", "label": "Wylewka cementowa tradycyjna"},
            {"value": "anhydrite", "label": "Wylewka anhydrytowa płynna"},
            {"value": "dry_screed", "label": "Sucha zabudowa (płyty gipsowo-włóknowe)"},
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _generate_default_loops_for_manifold(
    manifold_id: str,
    sections_count: int,
    existing_loops: dict,
    default_screed: str = "cement",
    default_thick: float = 50.0,
) -> dict:
    """Generuje pętle dla rozdzielacza od 1 do sections_count."""
    result = dict(existing_loops)

    # Dodaj brakujące
    for i in range(1, sections_count + 1):
        loop_id = f"petla_{manifold_id}_{i}"
        room = _DEFAULT_ROOM_NAMES[i - 1] if i <= len(_DEFAULT_ROOM_NAMES) else f"Obwód {i}"
        if loop_id not in result:
            result[loop_id] = {
                "name": f"Pętla {i}: {room}",
                "manifold_id": manifold_id,
                "section_number": i,
                "zone_name": room,
                "area_m2": 15.0,
                "pipe_type": DEFAULT_PIPE_TYPE,
                "spacing_cm": DEFAULT_PIPE_SPACING_CM,
                "approach_length_m": DEFAULT_APPROACH_LENGTH_M,
                "screed_type": default_screed,
                "screed_thickness_mm": default_thick,
                "screed_override": "default",
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


def _sync_zones_from_loops(loops_dict: dict, manifolds_dict: dict) -> dict:
    """Automatycznie grupuje pętle w pomieszczenia (strefy) i sumuje metraże oraz liczbę pętli."""
    zones: dict = {}
    for loop_id, loop_data in loops_dict.items():
        raw_room = loop_data.get("zone_name", "").strip() or loop_data.get("name", "Strefa")
        # Wyciągnij czystą nazwę pomieszczenia np. z "Pętla 1: Salon" -> "Salon"
        room_name = raw_room.split(":", 1)[1].strip() if ":" in raw_room else raw_room
        if not room_name:
            room_name = f"Obwód {loop_data.get('section_number', 1)}"

        m_id = loop_data.get("manifold_id", "rozdzielacz")
        z_id = _make_manifold_id(room_name)
        if not z_id:
            z_id = f"strefa_{loop_data.get('section_number', 1)}"

        loop_data["zone_id"] = z_id
        loop_data["zone_name"] = room_name

        area = float(loop_data.get("area_m2", 15.0))
        screed = loop_data.get("screed_type") or manifolds_dict.get(m_id, {}).get("screed_type", "cement")
        thick = float(
            loop_data.get("screed_thickness_mm")
            or manifolds_dict.get(m_id, {}).get("screed_thickness_mm", 50.0)
        )

        if z_id not in zones:
            zones[z_id] = {
                "name": room_name,
                "manifold_id": m_id,
                "area_m2": 0.0,
                "screed_type": screed,
                "screed_thickness_mm": thick,
                "loops_count": 0,
                "loops": [],
                "target_temp": 21.0,
                "heat_load_w_m2": 45.0,
                "floor_covering": "tiles",
            }

        zones[z_id]["area_m2"] = round(zones[z_id]["area_m2"] + area, 2)
        zones[z_id]["loops_count"] += 1
        zones[z_id]["loops"].append(loop_id)

    # Zaktualizuj loops_in_zone dla każdej pętli
    for loop_id, loop_data in loops_dict.items():
        z_id = loop_data.get("zone_id")
        if z_id in zones:
            loop_data["loops_in_zone"] = zones[z_id]["loops_count"]

    return zones


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
    fields: dict = {}

    for i in range(1, sections_count + 1):
        loop_id = f"petla_{manifold_id}_{i}"
        loop_data = existing_loops.get(loop_id, {})

        default_room = loop_data.get("zone_name") or (
            _DEFAULT_ROOM_NAMES[i - 1] if i <= len(_DEFAULT_ROOM_NAMES) else f"Pomieszczenie {i}"
        )
        default_area = float(loop_data.get("area_m2", 15.0))
        default_flow = float(loop_data.get(ATTR_ROTAMETER_FLOW_LMIN, 1.5))
        default_screed = loop_data.get("screed_override", "default")
        if default_screed not in SCREED_OVERRIDE_CHOICES:
            default_screed = "default"

        fields[vol.Required(f"loop_{i}_room", default=default_room)] = cv.string
        fields[vol.Required(f"loop_{i}_area", default=default_area)] = vol.Coerce(float)
        fields[vol.Required(f"loop_{i}_flow", default=default_flow)] = vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=6.0)
        )
        fields[vol.Optional(f"loop_{i}_screed", default=default_screed)] = SCREED_OVERRIDE_SELECTOR

    return vol.Schema(fields, extra=vol.ALLOW_EXTRA)


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
        self._pending_data = {
            CONF_MANIFOLDS: {},
            CONF_ZONES: {},
            CONF_LOOPS: {},
        }
        return await self.async_step_add_manifold()

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 1: Nazwa rozdzielacza, liczba pętli, lokalizacja, domyślna posadzka."""
        errors: dict[str, str] = {}

        if user_input is not None:
            m_name = user_input["name"].strip()
            sections_count = int(user_input["sections_count"])
            location = user_input.get("location", "Kotłownia / Parter").strip()
            screed_type = user_input.get("screed_type", "cement")
            screed_thick = float(user_input.get("screed_thickness_mm", 50.0))

            m_id = _make_manifold_id(m_name)
            if not m_id:
                m_id = "rozdzielacz_parter"

            self._pending_manifold_id = m_id
            self._pending_manifold_name = m_name
            self._pending_sections_count = sections_count

            self._pending_data.setdefault(CONF_MANIFOLDS, {})[m_id] = {
                "name": m_name,
                "location": location,
                "sections_count": sections_count,
                "screed_type": screed_type,
                "screed_thickness_mm": screed_thick,
            }
            self._pending_data.setdefault(CONF_LOOPS, {})
            self._pending_data[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, sections_count, self._pending_data[CONF_LOOPS], screed_type, screed_thick
            )

            return await self.async_step_configure_loops()

        schema = vol.Schema(
            {
                vol.Required("name", default="Rozdzielacz Parter"): cv.string,
                vol.Required("sections_count", default=6): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=24)
                ),
                vol.Optional("location", default="Kotłownia / Parter"): cv.string,
                vol.Required("screed_type", default="cement"): SCREED_SELECTOR,
                vol.Required("screed_thickness_mm", default=50.0): vol.Coerce(float),
            },
            extra=vol.ALLOW_EXTRA,
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
        m_data = self._pending_data.get(CONF_MANIFOLDS, {}).get(m_id, {})
        m_screed = m_data.get("screed_type", "cement")
        m_thick = float(m_data.get("screed_thickness_mm", 50.0))

        if user_input is not None:
            for i in range(1, sections_count + 1):
                loop_id = f"petla_{m_id}_{i}"
                room_name = user_input[f"loop_{i}_room"].strip()
                area = float(user_input[f"loop_{i}_area"])
                flow_lmin = float(user_input[f"loop_{i}_flow"])
                screed_override = user_input.get(f"loop_{i}_screed", "default")

                if screed_override and screed_override != "default":
                    screed = screed_override
                    thickness = 50.0 if screed == "cement" else (45.0 if screed == "anhydrite" else 25.0)
                else:
                    screed = m_screed
                    thickness = m_thick

                flow_lh = round(flow_lmin * 60.0, 1)

                if loop_id in self._pending_data[CONF_LOOPS]:
                    l = self._pending_data[CONF_LOOPS][loop_id]
                    l["name"] = f"Pętla {i}: {room_name}"
                    l["zone_name"] = room_name
                    l["area_m2"] = area
                    l["loops_in_zone"] = 1
                    l["screed_type"] = screed
                    l["screed_thickness_mm"] = thickness
                    l["screed_override"] = screed_override
                    l[ATTR_ROTAMETER_FLOW_LH] = flow_lh
                    l[ATTR_ROTAMETER_FLOW_LMIN] = flow_lmin

            # Zsynchronizuj i zsumuj pomieszczenia (strefy)
            self._pending_data[CONF_ZONES] = _sync_zones_from_loops(
                self._pending_data[CONF_LOOPS], self._pending_data[CONF_MANIFOLDS]
            )

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
        """Główne menu opcji."""
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
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("action", default="add_manifold"): vol.In(actions),
            },
            extra=vol.ALLOW_EXTRA,
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
            screed_type = user_input.get("screed_type", "cement")
            screed_thick = float(user_input.get("screed_thickness_mm", 50.0))

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
                "screed_type": screed_type,
                "screed_thickness_mm": screed_thick,
            }
            self.options[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, sections_count, self.options[CONF_LOOPS], screed_type, screed_thick
            )

            self._active_manifold_id = m_id
            self._pending_sections_count = sections_count
            self._pending_manifold_name = m_name

            return await self.async_step_configure_loops()

        schema = vol.Schema(
            {
                vol.Required("name", default=default_name): cv.string,
                vol.Required("sections_count", default=6): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=24)
                ),
                vol.Optional("location", default="Kotłownia / Parter"): cv.string,
                vol.Required("screed_type", default="cement"): SCREED_SELECTOR,
                vol.Required("screed_thickness_mm", default=50.0): vol.Coerce(float),
            },
            extra=vol.ALLOW_EXTRA,
        )
        return self.async_show_form(
            step_id="add_manifold",
            data_schema=schema,
            errors=errors,
        )

    # ======================== KONFIGURACJA PĘTLI =======================

    async def async_step_select_manifold_for_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybierz rozdzielacz do edycji pętli."""
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
            },
            extra=vol.ALLOW_EXTRA,
        )
        return self.async_show_form(step_id="select_manifold_for_loops", data_schema=schema)

    async def async_step_configure_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 2: Dynamiczny formularz dla wszystkich pętli rozdzielacza naraz."""
        m_id = self._active_manifold_id
        m_name = self._pending_manifold_name
        sections_count = self._pending_sections_count
        existing_loops = self.options.get(CONF_LOOPS, {})
        m_data = self.options[CONF_MANIFOLDS].get(m_id, {})
        m_screed = m_data.get("screed_type", "cement")
        m_thick = float(m_data.get("screed_thickness_mm", 50.0))

        if user_input is not None:
            for i in range(1, sections_count + 1):
                loop_id = f"petla_{m_id}_{i}"
                room_name = user_input[f"loop_{i}_room"].strip()
                area = float(user_input[f"loop_{i}_area"])
                flow_lmin = float(user_input[f"loop_{i}_flow"])
                screed_override = user_input.get(f"loop_{i}_screed", "default")

                if screed_override and screed_override != "default":
                    screed = screed_override
                    thickness = 50.0 if screed == "cement" else (45.0 if screed == "anhydrite" else 25.0)
                else:
                    screed = m_screed
                    thickness = m_thick

                flow_lh = round(flow_lmin * 60.0, 1)

                if loop_id in self.options[CONF_LOOPS]:
                    l = self.options[CONF_LOOPS][loop_id]
                    l["name"] = f"Pętla {i}: {room_name}"
                    l["zone_name"] = room_name
                    l["area_m2"] = area
                    l["loops_in_zone"] = 1
                    l["screed_type"] = screed
                    l["screed_thickness_mm"] = thickness
                    l["screed_override"] = screed_override
                    l[ATTR_ROTAMETER_FLOW_LH] = flow_lh
                    l[ATTR_ROTAMETER_FLOW_LMIN] = flow_lmin

            # Zsynchronizuj i zsumuj pomieszczenia (strefy)
            self.options[CONF_ZONES] = _sync_zones_from_loops(
                self.options[CONF_LOOPS], self.options[CONF_MANIFOLDS]
            )

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
            for lid in list(self.options[CONF_LOOPS].keys()):
                if self.options[CONF_LOOPS][lid].get("manifold_id") == m_id:
                    self.options[CONF_LOOPS].pop(lid, None)
            self.options[CONF_MANIFOLDS].pop(m_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)}, extra=vol.ALLOW_EXTRA)
        return self.async_show_form(step_id="remove_manifold", data_schema=schema)
