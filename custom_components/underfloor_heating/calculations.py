"""Moduł obliczeń inżynieryjnych dla ogrzewania podłogowego.

Zawiera estymację długości pętli, obliczenia hydrauliczne (opory, prędkości,
spadki ciśnień) oraz diagnostykę zrównoważenia rozdzielacza i stref.

Wersja: 1.0.0
"""

import math
from typing import Any, Dict, List, Tuple

from .const import (
    FLOOR_COVERINGS,
    PIPE_TYPES,
    SCREED_TYPES,
    STATUS_ACCEPTABLE,
    STATUS_CRITICAL,
    STATUS_OPTIMAL,
    STATUS_OVERFLOW,
    STATUS_UNDERFLOW,
    WATER_DENSITY,
    WATER_KINEMATIC_VISCOSITY,
    WATER_SPECIFIC_HEAT,
)


def estimate_loop_length(
    area_m2: float,
    loops_count: int = 1,
    spacing_cm: float = 15.0,
    approach_length_m: float = 4.0,
) -> float:
    """Automatyczne wyliczenie długości pojedynczej pętli podłogówki (estymacja).

    Wzór:
    Powierzchnia przypadająca na pętlę = area_m2 / loops_count
    Długość rury w strefie aktywnej = Powierzchnia_pętli / (spacing_cm / 100)
    Długość podejścia tranzytowego (zasilanie + powrót) = 2 * approach_length_m
    Narzut na łuki i zagięcia przy brzegach: 3%

    :param area_m2: Powierzchnia strefy/pomieszczenia w m²
    :param loops_count: Liczba pętli przypadająca na to pomieszczenie
    :param spacing_cm: Rozstaw rur PE w cm (np. 10, 15, 20 cm)
    :param approach_length_m: Średnia odległość od rozdzielacza do wejścia do strefy w metrach
    :return: Szacowana długość pojedynczej pętli w metrach (zaokrąglona do 1 miejsca po przecinku)
    """
    if loops_count <= 0:
        loops_count = 1
    if area_m2 <= 0:
        return round(2.0 * approach_length_m, 1)

    area_per_loop = area_m2 / float(loops_count)
    spacing_m = max(spacing_cm / 100.0, 0.05)

    # Aktywna długość rury grzejnej w pomieszczeniu
    active_pipe_length = area_per_loop / spacing_m

    # Tranzyt (zasilanie + powrót)
    transit_length = 2.0 * float(approach_length_m)

    # 3% narzutu na zagięcia i meandry/ślimaki
    total_length = (active_pipe_length * 1.03) + transit_length

    return round(total_length, 1)


def calculate_hydraulics(
    flow_l_h: float,
    loop_length_m: float,
    pipe_type: str = "pex_16x2",
) -> Dict[str, float]:
    """Oblicza parametry hydrauliczne pętli: prędkość przepływu i spadek ciśnienia.

    Używa równania ciągłości strugi oraz równania Darcy-Weisbacha ze wzorem
    Colebrooka-White'a (aproksymacja Swamee-Jain) dla oporów liniowych oraz
    oporów miejscowych (kolanka, zawór rozdzielacza, rotametr).

    :param flow_l_h: Przepływ objętościowy w litrach na godzinę (l/h)
    :param loop_length_m: Całkowita długość pętli w metrach
    :param pipe_type: Identyfikator typu rury z PIPE_TYPES
    :return: Słownik z prędkością (m/s), liczbą Reynoldsa i spadkiem ciśnienia (kPa)
    """
    pipe_info = PIPE_TYPES.get(pipe_type, PIPE_TYPES["pex_16x2"])
    d_inner = pipe_info["inner_diameter_mm"] / 1000.0  # wewnętrzna średnica w metrach
    k_roughness = pipe_info["absolute_roughness_mm"] / 1000.0  # chropowatość w metrach

    if flow_l_h <= 0.001 or loop_length_m <= 0.01:
        return {
            "flow_velocity_ms": 0.0,
            "reynolds_number": 0.0,
            "pressure_drop_kpa": 0.0,
            "pressure_drop_mbar": 0.0,
        }

    # Przepływ w m³/s: 1 l/h = (1 / 1000) / 3600 m³/s
    q_m3_s = (flow_l_h / 1000.0) / 3600.0

    # Pole przekroju rury w m²
    cross_section_area = (math.pi * (d_inner**2)) / 4.0

    # Prędkość liniowa czynnika w m/s
    velocity = q_m3_s / cross_section_area

    # Liczba Reynoldsa
    reynolds = (velocity * d_inner) / WATER_KINEMATIC_VISCOSITY

    # Współczynnik tarcia liniowego lambda (Darcy friction factor)
    if reynolds < 2300:
        # Przepływ laminarny
        friction_factor = 64.0 / max(reynolds, 1.0)
    else:
        # Przepływ burzliwy - wzór Swamee-Jaina
        relative_roughness = k_roughness / d_inner
        denom = math.log10((relative_roughness / 3.7) + (5.74 / (reynolds**0.9)))
        friction_factor = 0.25 / (denom**2)

    # Liniowy spadek ciśnienia (Darcy-Weisbach): delta_p = lambda * (L/D) * (rho * v^2 / 2)
    dynamic_pressure = (WATER_DENSITY * (velocity**2)) / 2.0
    linear_pressure_drop_pa = friction_factor * (loop_length_m / d_inner) * dynamic_pressure

    # Opory miejscowe (kolanka ślimaka, wejście do rozdzielacza, zawór odcinający, rotametr)
    # Przyjmuje się sumaryczny współczynnik oporów miejscowych zeta w zakresie 12.0 - 15.0
    zeta_sum = 14.0
    minor_pressure_drop_pa = zeta_sum * dynamic_pressure

    total_pressure_drop_pa = linear_pressure_drop_pa + minor_pressure_drop_pa
    pressure_drop_kpa = round(total_pressure_drop_pa / 1000.0, 2)
    pressure_drop_mbar = round(total_pressure_drop_pa / 100.0, 1)

    return {
        "flow_velocity_ms": round(velocity, 3),
        "reynolds_number": round(reynolds, 0),
        "pressure_drop_kpa": pressure_drop_kpa,
        "pressure_drop_mbar": pressure_drop_mbar,
    }


def calculate_thermal_properties(
    area_m2: float,
    screed_type: str = "cement",
    screed_thickness_mm: float = 65.0,
    floor_covering: str = "tiles",
    design_heat_load_w_m2: float = 45.0,
    delta_t: float = 5.0,
) -> Dict[str, float]:
    """Oblicza właściwości cieplne wylewki, wymaganą moc oraz wymagany przepływ projektowy.

    :param area_m2: Powierzchnia strefy w m²
    :param screed_type: Typ wylewki ("cement", "anhydrite", "dry_screed")
    :param screed_thickness_mm: Grubość wylewki w mm
    :param floor_covering: Rodzaj wykończenia ("tiles", "vinyl_glue", "laminate", itp.)
    :param design_heat_load_w_m2: Zapotrzebowanie cieplne pomieszczenia w W/m² (domyślnie 45 W/m² dla domu energooszczędnego)
    :param delta_t: Schłodzenie czynnika w pętli (zasilanie - powrót) w Kelwinach (zazwyczaj 5K dla podłogówki)
    :return: Słownik z mocą strefy (W), wymaganym przepływem (l/h i l/min), oporem termicznym i bezwładnością
    """
    screed_info = SCREED_TYPES.get(screed_type, SCREED_TYPES["cement"])
    covering_info = FLOOR_COVERINGS.get(floor_covering, FLOOR_COVERINGS["tiles"])

    thickness_m = screed_thickness_mm / 1000.0
    screed_r = thickness_m / screed_info["conductivity"]
    covering_r = covering_info["thermal_resistance"]
    total_floor_r = screed_r + covering_r  # m²K/W

    # Całkowita moc cieplna potrzebna w pomieszczeniu (W)
    total_heat_output_w = area_m2 * design_heat_load_w_m2

    # Wymagany przepływ projektowy: Q = P / (cw * delta_t) w kg/s -> zamiana na l/h
    # 1 W = 1 J/s
    if delta_t <= 0.1:
        delta_t = 5.0

    mass_flow_kg_s = total_heat_output_w / (WATER_SPECIFIC_HEAT * delta_t)
    volume_flow_m3_s = mass_flow_kg_s / WATER_DENSITY
    required_flow_lh = volume_flow_m3_s * 1000.0 * 3600.0  # litry na godzinę
    required_flow_lmin = required_flow_lh / 60.0

    # Pojemność cieplna wylewki C = objętość * gęstość * ciepło właściwe (J/K)
    screed_volume_m3 = area_m2 * thickness_m
    screed_mass_kg = screed_volume_m3 * screed_info["density"]
    heat_capacity_kj_k = (screed_mass_kg * screed_info["specific_heat"]) / 1000.0
    heat_capacity_kwh_k = heat_capacity_kj_k / 3600.0

    # Szacowana stała czasowa bezwładności termicznej wylewki w godzinach
    # Czas reakcji na zmianę temperatury zasilania (około 2-3 x stała czasowa dla 90% nasycenia)
    thermal_time_constant_hours = (heat_capacity_kwh_k * 1000.0) / max(total_heat_output_w, 1.0)

    return {
        "heat_output_w": round(total_heat_output_w, 1),
        "required_flow_lh": round(required_flow_lh, 1),
        "required_flow_lmin": round(required_flow_lmin, 2),
        "floor_thermal_resistance": round(total_floor_r, 4),
        "screed_mass_kg": round(screed_mass_kg, 1),
        "heat_capacity_kwh_k": round(heat_capacity_kwh_k, 2),
        "thermal_inertia_hours": round(thermal_time_constant_hours, 1),
    }


def diagnose_loop(
    current_flow_lh: float,
    required_flow_lh: float,
    loop_length_m: float,
    pipe_type: str = "pex_16x2",
    pressure_drop_kpa: float = 0.0,
    flow_velocity_ms: float = 0.0,
) -> Dict[str, Any]:
    """Diagnostyka pętli ogrzewania podłogowego.

    Ocenia, czy pętla jest zrównoważona hydraulicznie, czy rotametr jest
    ustawiony poprawnie, czy długość pętli nie przekracza norm oraz czy opory
    nie są zbyt duże.

    :return: Słownik zawierający status, odchylenie %, opis słowny i listę ostrzeżeń
    """
    warnings: List[str] = []
    pipe_info = PIPE_TYPES.get(pipe_type, PIPE_TYPES["pex_16x2"])
    max_len = pipe_info["max_recommended_length_m"]

    # 1. Sprawdzenie długości pętli
    if loop_length_m > max_len:
        warnings.append(
            f"Długość pętli ({loop_length_m} m) przekracza zalecane maksimum {max_len} m "
            f"dla rury {pipe_info['name']}. Może wystąpić niedogrzanie i duże opory hydrauliczne."
        )
    elif loop_length_m < 20.0 and loop_length_m > 0:
        warnings.append(
            f"Pętla jest bardzo krótka ({loop_length_m} m). Istnieje ryzyko uprzywilejowania "
            "hydraulicznego (zwarcie hydrauliczne) - rotametr musi być mocno skręcony."
        )

    # 2. Sprawdzenie prędkości przepływu
    if current_flow_lh > 0:
        if flow_velocity_ms < 0.15:
            warnings.append(
                f"Prędkość czynnika ({flow_velocity_ms} m/s) jest poniżej 0.15 m/s. "
                "Ryzyko problemów z samoczynnym odpowietrzaniem pętli."
            )
        elif flow_velocity_ms > 0.8:
            warnings.append(
                f"Prędkość czynnika ({flow_velocity_ms} m/s) przekracza zalecane 0.8 m/s. "
                "Możliwy szum hydrauliczny na zaworach i rotametrach oraz podwyższony pobór prądu pompy."
            )

    # 3. Sprawdzenie spadku ciśnienia
    if pressure_drop_kpa > 25.0:
        warnings.append(
            f"Wysoki spadek ciśnienia pętli ({pressure_drop_kpa} kPa > 25 kPa). "
            "Może wymagać pracy pompy obiegowej na najwyższym biegu lub dodatkowej grupy pompowej."
        )

    # 4. Ocena zrównoważenia przepływu (aktualny vs projektowy)
    if required_flow_lh <= 0.1:
        status = STATUS_OPTIMAL
        deviation_pct = 0.0
        status_text = "Brak wymaganego przepływu (pętla wyłączona lub pominięta)"
    else:
        deviation_pct = round(((current_flow_lh - required_flow_lh) / required_flow_lh) * 100.0, 1)

        if abs(deviation_pct) <= 15.0:
            status = STATUS_OPTIMAL
            status_text = f"Przepływ optymalny (odchylenie {deviation_pct}% od wymaganego)"
        elif -30.0 <= deviation_pct < -15.0:
            status = STATUS_ACCEPTABLE
            status_text = f"Przepływ lekko zdławiony ({deviation_pct}%), strefa może nagrzewać się wolniej"
        elif 15.0 < deviation_pct <= 35.0:
            status = STATUS_ACCEPTABLE
            status_text = f"Przepływ lekko zawyżony (+{deviation_pct}%), nieznaczny wzrost zużycia energii pompy"
        elif deviation_pct < -30.0:
            status = STATUS_UNDERFLOW
            status_text = f"Pętla mocno zdławiona ({deviation_pct}%), ryzyko niedogrzania pomieszczenia"
            warnings.append(
                f"Za mały przepływ ({current_flow_lh} l/h vs wymagany {required_flow_lh} l/h). "
                "Otwórz rotametr, aby zrównoważyć strefę."
            )
        else:
            status = STATUS_OVERFLOW
            status_text = f"Pętla przewymiarowana / zbyt duży przepływ (+{deviation_pct}%)"
            warnings.append(
                f"Zbyt duży przepływ ({current_flow_lh} l/h vs wymagany {required_flow_lh} l/h). "
                "Pętla kradnie przepływ innym pętlom na rozdzielaczu. Przykręć rotametr."
            )

    if loop_length_m > max_len * 1.25 or pressure_drop_kpa > 35.0:
        status = STATUS_CRITICAL

    return {
        "status": status,
        "status_details": status_text,
        "deviation_pct": deviation_pct,
        "warnings": warnings,
        "is_balanced": status in (STATUS_OPTIMAL, STATUS_ACCEPTABLE),
    }


def diagnose_manifold(
    loops_diagnostics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Diagnostyka całego rozdzielacza na podstawie parametrów jego pętli.

    Sprawdza rozrzut oporów pomiędzy najdłuższą i najkrótszą pętlą oraz sumaryczny
    przepływ rozdzielacza.
    """
    total_flow_lh = sum(d.get("current_flow_lh", 0.0) for d in loops_diagnostics)
    total_required_flow_lh = sum(d.get("required_flow_lh", 0.0) for d in loops_diagnostics)
    max_pressure_drop = max((d.get("pressure_drop_kpa", 0.0) for d in loops_diagnostics), default=0.0)
    min_pressure_drop = min((d.get("pressure_drop_kpa", 0.0) for d in loops_diagnostics if d.get("current_flow_lh", 0) > 0), default=0.0)

    unbalanced_loops = [d for d in loops_diagnostics if not d.get("is_balanced", True)]
    all_warnings = []
    for d in loops_diagnostics:
        all_warnings.extend(d.get("warnings", []))

    # Analiza rozstępu hydraulicznego (autorotacja rozdzielacza)
    delta_pressure_ratio = (max_pressure_drop / min_pressure_drop) if min_pressure_drop > 0.5 else 1.0
    if delta_pressure_ratio > 3.0 and len(loops_diagnostics) > 1:
        all_warnings.append(
            f"Duża dysproporcja oporów hydraulicznych na rozdzielaczu ({round(delta_pressure_ratio, 1)}x). "
            "Krótkie pętle wymagają bardzo precyzyjnego zdławienia rotametrami."
        )

    is_manifold_balanced = len(unbalanced_loops) == 0 and len(all_warnings) == 0

    return {
        "total_flow_lh": round(total_flow_lh, 1),
        "total_flow_lmin": round(total_flow_lh / 60.0, 2),
        "total_required_flow_lh": round(total_required_flow_lh, 1),
        "max_pressure_drop_kpa": round(max_pressure_drop, 2),
        "is_balanced": is_manifold_balanced,
        "unbalanced_loops_count": len(unbalanced_loops),
        "warnings_count": len(all_warnings),
        "warnings": all_warnings,
    }

