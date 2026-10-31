"""Kreator konfiguracji: Rozdzielacz > Pętle (szybkie przypisanie grupowe).

Umożliwia błyskawiczne dodawanie rozdzielaczy i przypisywanie pętli:
1. Dodanie rozdzielacza z określeniem liczby pętli (np. Parter, 8 pętli).
2. Zaznaczenie 1 lub wielu pętli i określenie:
   - Pomieszczenie (nazwa)
   - Rozmiar pomieszczenia (m²)
   - Przepływ zadany w l/min (zgodny ze szkiełkiem rotametru)
   - Rodzaj i grubość posadzki/jastrychu

Wersja: 1.1.0
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List

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


class UnderfloorHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Pierwsza konfiguracja integracji."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok 1: Podstawowa nazwa i pierwszy rozdzielacz."""
        errors: dict[str, str] = {}

        if user_input is not None:
            inst_name = user_input.get(ATTR_NAME, DEFAULT_NAME)
            m_name = user_input.get("manifold_name", "Rozdzielacz Parter").strip()
            sections_count = int(user_input.get("sections_count", 8))
            location = user_input.get("location", "Kotłownia / Parter")

            m_id = m_name.lower().replace(" ", "_").replace("ł", "l").replace("ą", "a").replace("ę", "e").replace("ó", "o")
            if not m_id:
                m_id = "rozdzielacz_parter"

            initial_data = {
                CONF_MANIFOLDS: {
                    m_id: {
                        "name": m_name,
                        "location": location,
                        "sections_count": sections_count,
                    }
                },
                CONF_ZONES: {},
                CONF_LOOPS: {},
            }

            # Wygeneruj pętle 1..sections_count
            initial_data[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, sections_count, {}
            )

            return self.async_create_entry(title=inst_name, data=initial_data)

        schema = vol.Schema(
            {
                vol.Required(ATTR_NAME, default=DEFAULT_NAME): str,
                vol.Required("manifold_name", default="Rozdzielacz Parter"): str,
                vol.Required("sections_count", default=8): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                vol.Optional("location", default="Kotłownia / Parter"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return UnderfloorHeatingOptionsFlowHandler(config_entry)


class UnderfloorHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Zarządzanie: szybkie przypisanie pętli, dodawanie rozdzielaczy, zmiana liczby pętli."""

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
        self._selected_loop_ids: list[str] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Główne menu opcji integracji."""
        actions = {
            "assign_loops": "⚡ Przypisz pętle (zaznacz pętle, podaj pomieszczenie, metraż, l/min, wylewkę)",
            "add_manifold": "🎛️ Dodaj nowy rozdzielacz (np. Piętro, Piwnica)",
            "edit_manifold": "⚙️ Zmień nazwę lub liczbę pętli rozdzielacza",
            "remove_manifold": "🗑️ Usuń rozdzielacz",
            "save": "💾 Zapisz i zastosuj zmiany",
        }

        if user_input is not None:
            choice = user_input.get("action")
            if choice == "assign_loops":
                return await self.async_step_select_manifold_for_loops()
            if choice == "add_manifold":
                return await self.async_step_add_manifold()
            if choice == "edit_manifold":
                return await self.async_step_select_edit_manifold()
            if choice == "remove_manifold":
                return await self.async_step_remove_manifold()
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("action", default="assign_loops"): vol.In(actions),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ================= SZYBKIE PRZYPISANIE PĘTLI =================

    async def async_step_select_manifold_for_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór rozdzielacza, którego pętle chcemy konfigurować."""
        manifolds = {
            m_id: f"{m['name']} ({m.get('sections_count', 8)} pętli)"
            for m_id, m in self.options[CONF_MANIFOLDS].items()
        }

        if not manifolds:
            # Utwórz domyślny jeśli brak
            self.options[CONF_MANIFOLDS]["parter"] = {
                "name": "Rozdzielacz Parter",
                "location": "Kotłownia / Parter",
                "sections_count": 8,
            }
            self.options[CONF_LOOPS] = _generate_default_loops_for_manifold("parter", 8, self.options[CONF_LOOPS])
            self._active_manifold_id = "parter"
            return await self.async_step_select_loops_to_configure()

        if len(manifolds) == 1:
            self._active_manifold_id = list(manifolds.keys())[0]
            return await self.async_step_select_loops_to_configure()

        if user_input is not None:
            self._active_manifold_id = user_input["manifold_id"]
            return await self.async_step_select_loops_to_configure()

        schema = vol.Schema(
            {
                vol.Required("manifold_id", default=list(manifolds.keys())[0]): vol.In(manifolds),
            }
        )
        return self.async_show_form(step_id="select_manifold_for_loops", data_schema=schema)

    async def async_step_select_loops_to_configure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok wyboru 1 lub wielu pętli (checkboxy/multiselect)."""
        m_id = self._active_manifold_id
        m_data = self.options[CONF_MANIFOLDS].get(m_id, {})
        m_name = m_data.get("name", m_id)

        # Pobierz i posortuj pętle rozdzielacza
        loops_of_m = [
            (lid, l) for lid, l in self.options[CONF_LOOPS].items() if l.get("manifold_id") == m_id
        ]
        loops_of_m.sort(key=lambda x: int(x[1].get("section_number", 0)))

        loops_choices = {}
        for lid, l in loops_of_m:
            sec = l.get("section_number", "?")
            room = l.get("zone_name", "Nieprzypisana")
            flow_lmin = round(float(l.get(ATTR_ROTAMETER_FLOW_LH, 90.0)) / 60.0, 1)
            area = l.get("area_m2", 0.0)
            screed = SCREED_TYPES.get(l.get("screed_type", "cement"), {}).get("name", "Cement").split()[1]
            thick = int(l.get("screed_thickness_mm", 50))
            loops_choices[lid] = f"Pętla {sec}: [{room}] - {area} m², {flow_lmin} l/min ({screed} {thick}mm)"

        if user_input is not None:
            selected = user_input.get("selected_loops", [])
            if selected:
                self._selected_loop_ids = selected
                return await self.async_step_configure_selected_loops()
            # Jeśli nic nie wybrano, wróć do menu
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("selected_loops"): cv_multi_select(loops_choices),
            }
        )
        return self.async_show_form(
            step_id="select_loops_to_configure",
            data_schema=schema,
            description_placeholders={"manifold_name": m_name},
        )

    async def async_step_configure_selected_loops(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz przypisania parametrów dla zaznaczonych pętli."""
        selected_lids = self._selected_loop_ids
        loops_count = len(selected_lids)

        screed_choices = {k: v["name"] for k, v in SCREED_TYPES.items()}
        spacing_choices = {10.0: "10 cm (zagęszczony)", 15.0: "15 cm (standard)", 20.0: "20 cm (rzadki)"}

        # Pobierz dane z pierwszej z wybranych pętli jako domyślne
        first_loop = self.options[CONF_LOOPS].get(selected_lids[0], {})
        curr_room = first_loop.get("zone_name", "Salon")
        curr_area = float(first_loop.get("area_m2", 18.0)) * loops_count
        curr_flow_lmin = round(float(first_loop.get(ATTR_ROTAMETER_FLOW_LH, 90.0)) / 60.0, 1)
        curr_screed = first_loop.get("screed_type", "cement")
        curr_thick = float(first_loop.get("screed_thickness_mm", 50.0))

        if user_input is not None:
            room_name = user_input["room_name"].strip()
            total_room_area = float(user_input["room_area_m2"])
            flow_lmin = float(user_input["flow_lmin"])
            screed_type = user_input["screed_type"]
            screed_thick = float(user_input["screed_thickness_mm"])
            spacing_cm = float(user_input.get("spacing_cm", 15.0))

            # Przeliczenie na l/h
            flow_lh = round(flow_lmin * 60.0, 1)
            # Powierzchnia przypadająca na każdą pętlę
            area_per_loop = round(total_room_area / float(loops_count), 2)

            # Zapis do każdej z zaznaczonych pętli
            for lid in selected_lids:
                l = self.options[CONF_LOOPS][lid]
                sec_num = l.get("section_number", 1)
                l["name"] = f"Pętla {sec_num}: {room_name}"
                l["zone_name"] = room_name
                l["area_m2"] = area_per_loop
                l["loops_in_zone"] = loops_count
                l["screed_type"] = screed_type
                l["screed_thickness_mm"] = screed_thick
                l["spacing_cm"] = spacing_cm
                l[ATTR_ROTAMETER_FLOW_LH] = flow_lh
                l[ATTR_ROTAMETER_FLOW_LMIN] = flow_lmin

            # Zapis wirtualnej strefy dla przejrzystości
            z_id = room_name.lower().replace(" ", "_").replace("ł", "l").replace("ą", "a").replace("ę", "e").replace("ó", "o")
            self.options[CONF_ZONES][z_id] = {
                "name": room_name,
                "manifold_id": self._active_manifold_id,
                "area_m2": total_room_area,
                "screed_type": screed_type,
                "screed_thickness_mm": screed_thick,
                "loops_count": loops_count,
            }

            # Pytanie czy konfigurować kolejne pętle
            return await self.async_step_confirm_continue()

        schema = vol.Schema(
            {
                vol.Required("room_name", default=curr_room): str,
                vol.Required("room_area_m2", default=curr_area): vol.Coerce(float),
                vol.Required("flow_lmin", default=curr_flow_lmin): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=6.0)),
                vol.Required("screed_type", default=curr_screed): vol.In(screed_choices),
                vol.Required("screed_thickness_mm", default=curr_thick): vol.Coerce(float),
                vol.Optional("spacing_cm", default=15.0): vol.In(spacing_choices),
            }
        )

        return self.async_show_form(
            step_id="configure_selected_loops",
            data_schema=schema,
            description_placeholders={
                "loops_count": str(loops_count),
                "loops_list": ", ".join([f"Pętla {self.options[CONF_LOOPS][lid].get('section_number')}" for lid in selected_lids]),
            },
        )

    async def async_step_confirm_continue(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Pytanie czy kontynuować konfigurację kolejnych pętli."""
        if user_input is not None:
            if user_input.get("continue_config", True):
                return await self.async_step_select_loops_to_configure()
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("continue_config", default=True): bool,
            }
        )
        return self.async_show_form(step_id="confirm_continue", data_schema=schema)

    # ================= ZARZĄDZANIE ROZDZIELACZAMI =================

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Dodanie kolejnego rozdzielacza z liczbą pętli."""
        if user_input is not None:
            m_name = user_input["name"].strip()
            sections_count = int(user_input["sections_count"])
            location = user_input.get("location", "")

            m_id = m_name.lower().replace(" ", "_").replace("ł", "l").replace("ą", "a").replace("ę", "e").replace("ó", "o")
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

            # Wygeneruj pętle
            self.options[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, sections_count, self.options[CONF_LOOPS]
            )

            # Przejdź od razu do konfiguracji pętli nowego rozdzielacza!
            self._active_manifold_id = m_id
            return await self.async_step_select_loops_to_configure()

        schema = vol.Schema(
            {
                vol.Required("name", default=f"Rozdzielacz {len(self.options[CONF_MANIFOLDS]) + 1}"): str,
                vol.Required("sections_count", default=8): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                vol.Optional("location", default="Garderoba / Piętro"): str,
            }
        )
        return self.async_show_form(step_id="add_manifold", data_schema=schema)

    async def async_step_select_edit_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór rozdzielacza do zmiany liczby pętli lub nazwy."""
        manifolds = {
            m_id: f"{m['name']} (obecnie: {m.get('sections_count', 8)} pętli)"
            for m_id, m in self.options[CONF_MANIFOLDS].items()
        }
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            self._active_manifold_id = user_input["manifold_id"]
            return await self.async_step_edit_manifold_details()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)})
        return self.async_show_form(step_id="select_edit_manifold", data_schema=schema)

    async def async_step_edit_manifold_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Zmiana nazwy lub liczby pętli rozdzielacza."""
        m_id = self._active_manifold_id
        m_data = self.options[CONF_MANIFOLDS].get(m_id, {})

        if user_input is not None:
            new_name = user_input["name"].strip()
            new_sections = int(user_input["sections_count"])
            new_loc = user_input.get("location", "")

            self.options[CONF_MANIFOLDS][m_id] = {
                "name": new_name,
                "location": new_loc,
                "sections_count": new_sections,
            }

            # Dopasuj pętle (doda brakujące lub usunie nadmiarowe)
            self.options[CONF_LOOPS] = _generate_default_loops_for_manifold(
                m_id, new_sections, self.options[CONF_LOOPS]
            )

            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("name", default=m_data.get("name", m_id)): str,
                vol.Required("sections_count", default=int(m_data.get("sections_count", 8))): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                vol.Optional("location", default=m_data.get("location", "")): str,
            }
        )
        return self.async_show_form(step_id="edit_manifold_details", data_schema=schema)

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


def cv_multi_select(choices: dict):
    """Pomocniczy walidator multi-select kompatybilny z Home Assistant."""
    return cv_multi_select_list(list(choices.keys()))


def cv_multi_select_list(valid_values: list):
    def validator(values):
        if not isinstance(values, list):
            raise vol.Invalid("Wartość musi być listą zaznaczonych pętli")
        for val in values:
            if val not in valid_values:
                raise vol.Invalid(f"Nieprawidłowy wybór: {val}")
        return values
    return validator
