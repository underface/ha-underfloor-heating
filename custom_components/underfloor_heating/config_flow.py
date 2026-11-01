"""Kreator konfiguracji: Rozdzielacz → Pomieszczenia (z liczbą pętli i metrażem).

Wersja: 1.4.0

Architektura 100% Room-First:
1. Krok 1 (add_manifold): Nazwa rozdzielacza, lokalizacja, domyślna wylewka.
2. Krok 2 (add_room): Kolejne pomieszczenia (nazwa, całkowity metraż m²,
   liczba pętli w pokoju, wylewka, rotametr).
   Pętle są automatycznie generowane pod danym pomieszczeniem.

OptionsFlow:
- add_room        → Dodaj kolejne pomieszczenie do rozdzielacza
- edit_room       → Edytuj metraż, wylewkę i rotametry pomieszczenia
- remove_room     → Usuń pomieszczenie wraz z jego pętlami
- add_manifold    → Dodaj nowy rozdzielacz
- remove_manifold → Usuń rozdzielacz
- save            → Zapisz i zastosuj
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

from .const import (
    ATTR_APPROACH_LENGTH,
    ATTR_AREA,
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
)
from .helpers import slugify_id

_LOGGER = logging.getLogger(__name__)

# Sugerowane nazwy dla kolejnych pomieszczeń
_DEFAULT_ROOM_NAMES = [
    "Salon", "Kuchnia", "Łazienka", "Korytarz", "Gabinet",
    "Sypialnia", "Garderoba", "Pralnia", "Wiatrołap", "WC",
    "Pokój dziecięcy", "Pokój gościnny",
]

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


# ===========================================================================
#  KONFIGURACJA PIERWSZA INSTALACJI (KROK 1: ROZDZIELACZ → KROK 2: POKOJE)
# ===========================================================================

class UnderfloorHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Kreator instalacji oparty w 100% na definicji Pomieszczeń."""

    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        self._pending_manifold_id: str = "rozdzielacz_parter"
        self._pending_manifold_name: str = "Rozdzielacz Parter"
        self._pending_manifold_data: dict[str, Any] = {}
        self._pending_rooms: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok startowy – rozpoczyna od parametrów rozdzielacza."""
        return await self.async_step_add_manifold()

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 1: Parametry belki rozdzielacza (bez pytania o liczbę pętli!)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            m_name = user_input["name"].strip()
            location = user_input.get("location", "Kotłownia / Parter").strip()
            screed_type = user_input.get("screed_type", "cement")
            screed_thick = float(user_input.get("screed_thickness_mm", 50.0))

            m_id = slugify_id(m_name) or "rozdzielacz_parter"
            self._pending_manifold_id = m_id
            self._pending_manifold_name = m_name
            self._pending_manifold_data = {
                "name": m_name,
                "location": location,
                "screed_type": screed_type,
                "screed_thickness_mm": screed_thick,
                "sections_count": 0,
            }
            self._pending_rooms = []
            return await self.async_step_add_room()

        schema = vol.Schema(
            {
                vol.Required("name", default="Rozdzielacz Parter"): cv.string,
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

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """KROK 2: Dodawanie pomieszczenia (metraż pokoju, liczba pętli, wylewka, rotametr)."""
        room_idx = len(self._pending_rooms) + 1
        default_room_name = (
            _DEFAULT_ROOM_NAMES[room_idx - 1]
            if room_idx <= len(_DEFAULT_ROOM_NAMES)
            else f"Pomieszczenie {room_idx}"
        )

        default_area = 30.0 if "Salon" in default_room_name else (15.0 if "Kuchnia" in default_room_name else (8.0 if "Łazienka" in default_room_name else 12.0))
        default_loops = 2 if "Salon" in default_room_name else 1

        if user_input is not None:
            r_name = user_input["room_name"].strip()
            r_area = float(user_input["area_m2"])
            r_loops = int(user_input["loops_count"])
            r_screed = user_input.get("screed_override", "default")
            r_flow = float(user_input.get("flow_lmin", 1.5))
            add_another = bool(user_input.get("add_another", False))

            self._pending_rooms.append({
                "name": r_name,
                "area": r_area,
                "loops_count": r_loops,
                "screed": r_screed,
                "flow": r_flow,
            })

            if add_another:
                return await self.async_step_add_room()

            return self._finalize_configuration()

        schema = vol.Schema(
            {
                vol.Required("room_name", default=default_room_name): cv.string,
                vol.Required("area_m2", default=default_area): vol.Coerce(float),
                vol.Required("loops_count", default=default_loops): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=10)
                ),
                vol.Optional("screed_override", default="default"): SCREED_OVERRIDE_SELECTOR,
                vol.Required("flow_lmin", default=1.5): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=6.0)
                ),
                vol.Required("add_another", default=True if room_idx < 3 else False): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        )

        return self.async_show_form(
            step_id="add_room",
            data_schema=schema,
            description_placeholders={
                "room_idx": str(room_idx),
                "manifold_name": self._pending_manifold_name,
                "total_added": str(len(self._pending_rooms)),
            },
        )

    def _finalize_configuration(self) -> FlowResult:
        """Tworzy pełną konfigurację: rozdzielacz, strefy i pętle."""
        m_id = self._pending_manifold_id
        m_data = self._pending_manifold_data
        m_screed = m_data.get("screed_type", "cement")
        m_thick = float(m_data.get("screed_thickness_mm", 50.0))

        data: dict[str, Any] = {
            CONF_MANIFOLDS: {m_id: m_data},
            CONF_ZONES: {},
            CONF_LOOPS: {},
        }

        global_loop_idx = 1
        for room_idx, room in enumerate(self._pending_rooms):
            r_name = room["name"]
            r_area = float(room["area"])
            loops_cnt = int(room["loops_count"])
            screed_override = room["screed"]
            flow_lmin = float(room["flow"])
            flow_lh = round(flow_lmin * 60.0, 1)

            if screed_override and screed_override != "default":
                screed = screed_override
                thick = 50.0 if screed == "cement" else (45.0 if screed == "anhydrite" else 25.0)
            else:
                screed = m_screed
                thick = m_thick

            base_zid = slugify_id(r_name) or f"strefa_{room_idx + 1}"
            z_id = base_zid
            collision_counter = 1
            while z_id in data[CONF_ZONES]:
                z_id = f"{base_zid}_{collision_counter}"
                collision_counter += 1

            area_per_loop = round(r_area / max(1, loops_cnt), 2)
            created_loop_ids = []

            for l_sub in range(1, loops_cnt + 1):
                lid = f"petla_{m_id}_{global_loop_idx}"
                created_loop_ids.append(lid)
                sub_label = f" {l_sub}" if loops_cnt > 1 else ""
                clean_name = f"Pętla {global_loop_idx}: {r_name}{sub_label}"

                data[CONF_LOOPS][lid] = {
                    "name": clean_name,
                    "manifold_id": m_id,
                    "section_number": global_loop_idx,
                    "zone_name": r_name,
                    "zone_id": z_id,
                    "area_m2": area_per_loop,
                    "pipe_type": DEFAULT_PIPE_TYPE,
                    "spacing_cm": DEFAULT_PIPE_SPACING_CM,
                    "approach_length_m": DEFAULT_APPROACH_LENGTH_M,
                    "screed_type": screed,
                    "screed_thickness_mm": thick,
                    "screed_override": screed_override,
                    "floor_covering": "tiles",
                    "loops_in_zone": loops_cnt,
                    ATTR_ROTAMETER_FLOW_LH: flow_lh,
                    ATTR_ROTAMETER_FLOW_LMIN: flow_lmin,
                }
                global_loop_idx += 1

            data[CONF_ZONES][z_id] = {
                "name": r_name,
                "manifold_id": m_id,
                "area_m2": r_area,
                "screed_type": screed,
                "screed_thickness_mm": thick,
                "loops_count": loops_cnt,
                "loops": created_loop_ids,
                "target_temp": 21.0,
                "heat_load_w_m2": 45.0,
                "floor_covering": "tiles",
            }

        m_data["sections_count"] = global_loop_idx - 1
        _LOGGER.info(
            "Utworzono integrację Podłogówka: rozdzielacz %s, %d pomieszczeń, %d pętli",
            m_id, len(self._pending_rooms), global_loop_idx - 1
        )
        return self.async_create_entry(title=DEFAULT_NAME, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return UnderfloorHeatingOptionsFlowHandler(config_entry)


# ===========================================================================
#  OPTIONS FLOW (ZARZĄDZANIE: DODAJ / EDYTUJ / USUŃ POMIESZCZENIE)
# ===========================================================================

class UnderfloorHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Zarządzanie instalacją – operacje w 100% na poziomie Pomieszczeń."""

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

        self._selected_zone_id: str | None = None
        self._target_manifold_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Główne menu opcji konfiguracji."""
        actions = {
            "add_room": "➕ Dodaj pomieszczenie do rozdzielacza",
            "edit_room": "✏️ Edytuj pomieszczenie (metraż, wylewka, rotametr)",
            "remove_room": "🗑️ Usuń pomieszczenie",
            "add_manifold": "🎛️ Dodaj nowy rozdzielacz",
            "remove_manifold": "🗑️ Usuń rozdzielacz",
            "save": "💾 Zapisz i zastosuj zmiany",
        }

        if user_input is not None:
            act = user_input.get("action")
            if act == "add_room":
                return await self.async_step_add_room()
            if act == "edit_room":
                return await self.async_step_select_room_to_edit()
            if act == "remove_room":
                return await self.async_step_remove_room()
            if act == "add_manifold":
                return await self.async_step_add_manifold()
            if act == "remove_manifold":
                return await self.async_step_remove_manifold()
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("action", default="add_room"): vol.In(actions),
            },
            extra=vol.ALLOW_EXTRA,
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ======================== DODAJ POMIESZCZENIE ========================

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Dodaje nowe pomieszczenie i automatycznie tworzy dla niego pętle."""
        manifolds = {m_id: m["name"] for m_id, m in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_add_manifold()

        default_m_id = list(manifolds.keys())[0]

        if user_input is not None:
            m_id = user_input.get("manifold_id", default_m_id)
            r_name = user_input["room_name"].strip()
            r_area = float(user_input["area_m2"])
            r_loops = int(user_input["loops_count"])
            r_screed = user_input.get("screed_override", "default")
            r_flow = float(user_input.get("flow_lmin", 1.5))

            m_data = self.options[CONF_MANIFOLDS][m_id]
            m_screed = m_data.get("screed_type", "cement")
            m_thick = float(m_data.get("screed_thickness_mm", 50.0))

            if r_screed and r_screed != "default":
                screed = r_screed
                thick = 50.0 if screed == "cement" else (45.0 if screed == "anhydrite" else 25.0)
            else:
                screed = m_screed
                thick = m_thick

            base_zid = slugify_id(r_name)
            z_id = base_zid
            collision_counter = 1
            while z_id in self.options[CONF_ZONES]:
                z_id = f"{base_zid}_{collision_counter}"
                collision_counter += 1

            area_per_loop = round(r_area / max(1, r_loops), 2)
            flow_lh = round(r_flow * 60.0, 1)

            # Znajdź kolejny najwyższy numer sekcji na tym rozdzielaczu
            existing_sections = [
                l.get("section_number", 0)
                for l in self.options[CONF_LOOPS].values()
                if l.get("manifold_id") == m_id
            ]
            next_sec = (max(existing_sections) if existing_sections else 0) + 1

            created_loop_ids = []
            for l_sub in range(1, r_loops + 1):
                lid = f"petla_{m_id}_{next_sec}"
                created_loop_ids.append(lid)
                sub_label = f" {l_sub}" if r_loops > 1 else ""
                clean_name = f"Pętla {next_sec}: {r_name}{sub_label}"

                self.options[CONF_LOOPS][lid] = {
                    "name": clean_name,
                    "manifold_id": m_id,
                    "section_number": next_sec,
                    "zone_name": r_name,
                    "zone_id": z_id,
                    "area_m2": area_per_loop,
                    "pipe_type": DEFAULT_PIPE_TYPE,
                    "spacing_cm": DEFAULT_PIPE_SPACING_CM,
                    "approach_length_m": DEFAULT_APPROACH_LENGTH_M,
                    "screed_type": screed,
                    "screed_thickness_mm": thick,
                    "screed_override": r_screed,
                    "floor_covering": "tiles",
                    "loops_in_zone": r_loops,
                    ATTR_ROTAMETER_FLOW_LH: flow_lh,
                    ATTR_ROTAMETER_FLOW_LMIN: r_flow,
                }
                next_sec += 1

            self.options[CONF_ZONES][z_id] = {
                "name": r_name,
                "manifold_id": m_id,
                "area_m2": r_area,
                "screed_type": screed,
                "screed_thickness_mm": thick,
                "loops_count": r_loops,
                "loops": created_loop_ids,
                "target_temp": 21.0,
                "heat_load_w_m2": 45.0,
                "floor_covering": "tiles",
            }

            m_data["sections_count"] = len([
                l for l in self.options[CONF_LOOPS].values() if l.get("manifold_id") == m_id
            ])

            return await self.async_step_init()

        schema_dict: dict[Any, Any] = {}
        if len(manifolds) > 1:
            schema_dict[vol.Required("manifold_id", default=default_m_id)] = vol.In(manifolds)

        schema_dict.update({
            vol.Required("room_name"): cv.string,
            vol.Required("area_m2", default=15.0): vol.Coerce(float),
            vol.Required("loops_count", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            vol.Optional("screed_override", default="default"): SCREED_OVERRIDE_SELECTOR,
            vol.Required("flow_lmin", default=1.5): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=6.0)),
        })

        return self.async_show_form(step_id="add_room", data_schema=vol.Schema(schema_dict, extra=vol.ALLOW_EXTRA))

    # ======================== EDYTUJ POMIESZCZENIE =====================

    async def async_step_select_room_to_edit(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór pomieszczenia do edycji."""
        rooms = {
            z_id: f"{z.get('name', z_id)} ({z.get('area_m2', 0)} m², {z.get('loops_count', 1)} pętli)"
            for z_id, z in self.options[CONF_ZONES].items()
        }
        if not rooms:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_zone_id = user_input["zone_id"]
            return await self.async_step_edit_room()

        schema = vol.Schema({vol.Required("zone_id"): vol.In(rooms)}, extra=vol.ALLOW_EXTRA)
        return self.async_show_form(step_id="select_room_to_edit", data_schema=schema)

    async def async_step_edit_room(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edycja parametrów wybranego pomieszczenia."""
        z_id = self._selected_zone_id
        if not z_id or z_id not in self.options[CONF_ZONES]:
            return await self.async_step_init()

        z = self.options[CONF_ZONES][z_id]

        if user_input is not None:
            new_area = float(user_input["area_m2"])
            new_screed = user_input.get("screed_override", "default")
            new_flow = float(user_input.get("flow_lmin", 1.5))

            z["area_m2"] = new_area
            loops_cnt = z.get("loops_count", 1) or 1
            area_per_loop = round(new_area / float(loops_cnt), 2)
            flow_lh = round(new_flow * 60.0, 1)

            m_data = self.options[CONF_MANIFOLDS].get(z.get("manifold_id"), {})
            m_screed = m_data.get("screed_type", "cement")
            m_thick = float(m_data.get("screed_thickness_mm", 50.0))

            if new_screed and new_screed != "default":
                screed = new_screed
                thick = 50.0 if screed == "cement" else (45.0 if screed == "anhydrite" else 25.0)
            else:
                screed = m_screed
                thick = m_thick

            z["screed_type"] = screed
            z["screed_thickness_mm"] = thick

            # Zaktualizuj powiązane pętle
            for lid in z.get("loops", []):
                if lid in self.options[CONF_LOOPS]:
                    lp = self.options[CONF_LOOPS][lid]
                    lp["area_m2"] = area_per_loop
                    lp["screed_type"] = screed
                    lp["screed_thickness_mm"] = thick
                    lp["screed_override"] = new_screed
                    lp[ATTR_ROTAMETER_FLOW_LMIN] = new_flow
                    lp[ATTR_ROTAMETER_FLOW_LH] = flow_lh

            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("area_m2", default=float(z.get("area_m2", 15.0))): vol.Coerce(float),
                vol.Optional("screed_override", default=z.get("screed_override", "default")): SCREED_OVERRIDE_SELECTOR,
                vol.Required("flow_lmin", default=1.5): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=6.0)),
            },
            extra=vol.ALLOW_EXTRA,
        )
        return self.async_show_form(
            step_id="edit_room",
            data_schema=schema,
            description_placeholders={"room_name": z.get("name", z_id)},
        )

    # ======================== USUŃ POMIESZCZENIE =======================

    async def async_step_remove_room(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie pomieszczenia wraz ze wszystkimi jego pętlami."""
        rooms = {
            z_id: f"{z.get('name', z_id)} ({z.get('area_m2', 0)} m², {z.get('loops_count', 1)} pętli)"
            for z_id, z in self.options[CONF_ZONES].items()
        }
        if not rooms:
            return await self.async_step_init()

        if user_input is not None:
            z_id = user_input["zone_id"]
            if z_id in self.options[CONF_ZONES]:
                z = self.options[CONF_ZONES].pop(z_id)
                m_id = z.get("manifold_id")
                # Usuń pętle tego pokoju
                for lid in z.get("loops", []):
                    self.options[CONF_LOOPS].pop(lid, None)

                # Zaktualizuj liczbę sekcji rozdzielacza
                if m_id and m_id in self.options[CONF_MANIFOLDS]:
                    self.options[CONF_MANIFOLDS][m_id]["sections_count"] = len([
                        l for l in self.options[CONF_LOOPS].values() if l.get("manifold_id") == m_id
                    ])

            return await self.async_step_init()

        schema = vol.Schema({vol.Required("zone_id"): vol.In(rooms)}, extra=vol.ALLOW_EXTRA)
        return self.async_show_form(step_id="remove_room", data_schema=schema)

    # ======================== DODAJ ROZDZIELACZ ========================

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Dodanie nowego rozdzielacza."""
        if user_input is not None:
            m_name = user_input["name"].strip()
            location = user_input.get("location", "").strip()
            screed_type = user_input.get("screed_type", "cement")
            screed_thick = float(user_input.get("screed_thickness_mm", 50.0))

            base_id = slugify_id(m_name)
            m_id = base_id
            collision_counter = 1
            while m_id in self.options[CONF_MANIFOLDS]:
                m_id = f"{base_id}_{collision_counter}"
                collision_counter += 1

            self.options[CONF_MANIFOLDS][m_id] = {
                "name": m_name,
                "location": location,
                "sections_count": 0,
                "screed_type": screed_type,
                "screed_thickness_mm": screed_thick,
            }
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("name", default=f"Rozdzielacz {len(self.options[CONF_MANIFOLDS]) + 1}"): cv.string,
                vol.Optional("location", default="Kotłownia"): cv.string,
                vol.Required("screed_type", default="cement"): SCREED_SELECTOR,
                vol.Required("screed_thickness_mm", default=50.0): vol.Coerce(float),
            },
            extra=vol.ALLOW_EXTRA,
        )
        return self.async_show_form(step_id="add_manifold", data_schema=schema)

    # ======================== USUŃ ROZDZIELACZ ========================

    async def async_step_remove_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie rozdzielacza wraz z przypisanymi pokojami i pętlami."""
        manifolds = {m_id: m["name"] for m_id, m in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            m_id = user_input["manifold_id"]
            # Usuń pętle rozdzielacza
            for lid in list(self.options[CONF_LOOPS].keys()):
                if self.options[CONF_LOOPS][lid].get("manifold_id") == m_id:
                    self.options[CONF_LOOPS].pop(lid, None)
            # Usuń strefy rozdzielacza
            for zid in list(self.options[CONF_ZONES].keys()):
                if self.options[CONF_ZONES][zid].get("manifold_id") == m_id:
                    self.options[CONF_ZONES].pop(zid, None)
            self.options[CONF_MANIFOLDS].pop(m_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)}, extra=vol.ALLOW_EXTRA)
        return self.async_show_form(step_id="remove_manifold", data_schema=schema)
