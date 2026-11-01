/**
 * Karta Lovelace: Rozdzielacz Ogrzewania Podłogowego (RWD)
 * Wersja: 1.3.0
 * 
 * Odwzorowanie 1:1 z projektu referencyjnego:
 * - Górne statystyki w 3 kartach: Przepływ sumaryczny, Pętla krytyczna Δp, Różnica ΔT i Moc kW
 * - Belka górna (Inox AISI 304 - Zasilanie) z pionowymi szklanymi rotametrami i plakietkami przepływu na górze
 * - Belka dolna (Inox AISI 304 - Powrót) z siłownikami elektrotermicznymi 230V NC i diodą ON
 * - Lewy panel termometrów zegarowych (Zasilanie 38.0°C / Powrót 32.0°C / ΔT = 6.0°C Optymalna)
 * - Płaska siatka kafelków pętli z pełnymi parametrami inżynieryjnymi, przyciskami [-] 0.1 [+] i ramką "AKTYWNA EDYCJA"
 * - Interaktywny in-card modal edycji parametrów pętli
 */

const I18N = {
  pl: {
    supply: "ZASILANIE",
    return: "POWRÓT",
    supply_pipe: "BELKA GÓRNA",
    return_pipe: "BELKA DOLNA",
    supplying: "Zasilająca",
    returning: "Powrotna",
    total_flow: "PRZEPŁYW SUMARYCZNY",
    crit_loop: "PĘTLA KRYTYCZNA (ΔP_MAX)",
    delta_t: "RÓŻNICA ΔT",
    balanced: "Zrównoważony hydraulicznie",
    needs_adjustment: "Wymaga regulacji",
    crit_status: "krytyczny",
    opt_status: "Optymalny",
    accept_status: "Akceptowalny",
    overflow_status: "Przewymiarowany",
    active_edit: "AKTYWNA EDYCJA",
    loop_grid_title: "SEKCJE PĘTLI GRZEWCZYCH (KLIKNIJ KAFELEK, ABY OTWORZYĆ IN-CARD MODAL EDYCJI)",
    step_hint: "Krok regulacji rotametru: ±0.1 l/min",
    pipe_len: "Długość rury:",
    dp_drop: "Spadek Δp:",
    screed_lbl: "Posadzka:",
    save: "Zapisz",
    cancel: "Anuluj",
  },
  en: {
    supply: "SUPPLY",
    return: "RETURN",
    supply_pipe: "TOP MANIFOLD",
    return_pipe: "BOTTOM MANIFOLD",
    supplying: "Supply (Flow)",
    returning: "Return",
    total_flow: "TOTAL FLOW",
    crit_loop: "CRITICAL LOOP (ΔP_MAX)",
    delta_t: "DIFFERENCE ΔT",
    balanced: "Hydraulically balanced",
    needs_adjustment: "Needs adjustment",
    crit_status: "critical",
    opt_status: "Optimal",
    accept_status: "Acceptable",
    overflow_status: "Overflow",
    active_edit: "ACTIVE EDIT",
    loop_grid_title: "HEATING LOOPS SECTIONS (CLICK CARD TO OPEN IN-CARD EDIT MODAL)",
    step_hint: "Rotameter adjustment step: ±0.1 l/min",
    pipe_len: "Pipe length:",
    dp_drop: "Pressure drop Δp:",
    screed_lbl: "Screed:",
    save: "Save",
    cancel: "Cancel",
  }
};

class UnderfloorHeatingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._lang = "pl";
    this._activeManifoldId = null;
    this._selectedLoopIndex = 4; // Domyślnie zaznaczona pętla #5 jak na zrzucie
    this._currentLoops = [];
  }

  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    const detected = (hass.locale && hass.locale.language) || hass.language || "pl";
    this._lang = detected.startsWith("pl") ? "pl" : "en";
    this.updateCard();
  }

  get t() {
    return I18N[this._lang] || I18N["pl"];
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          --bg-card: #080e1b;
          --card-surface: #0c1527;
          --border: #1e293b;
          --text-main: #ffffff;
          --text-muted: #94a3b8;
          --cyan-acc: #38bdf8;
          --gold-acc: #f59e0b;
          --green-acc: #22c55e;
          --danger-acc: #ef4444;
          --steel: linear-gradient(180deg, #f8fafc 0%, #cbd5e1 20%, #94a3b8 50%, #475569 80%, #cbd5e1 100%);
          --brass: linear-gradient(180deg, #fef08a 0%, #eab308 50%, #854d0e 85%, #fef08a 100%);
        }

        .card-container {
          background: var(--bg-card);
          color: var(--text-main);
          border-radius: 18px;
          padding: 24px;
          border: 1px solid #1e293b;
          box-shadow: 0 16px 40px rgba(0,0,0,0.6);
          user-select: none;
        }

        /* NAGŁÓWEK GŁÓWNY Z TYTUŁEM I STATUSAMI */
        .main-header {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 16px;
        }

        .menu-btn {
          width: 38px;
          height: 38px;
          background: #0f1c33;
          border: 1px solid #1e293b;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--cyan-acc);
          cursor: pointer;
        }
        .menu-btn svg { width: 20px; height: 20px; fill: currentColor; }

        .title-block {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .title-row {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }

        .manifold-title {
          font-size: 1.45rem;
          font-weight: 800;
          color: #ffffff;
          letter-spacing: -0.01em;
        }

        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 0.75rem;
          font-weight: 700;
          background: rgba(34, 197, 94, 0.15);
          color: #4ade80;
          border: 1px solid rgba(34, 197, 94, 0.3);
        }
        .status-badge.crit {
          background: rgba(239, 68, 68, 0.15);
          color: #f87171;
          border-color: rgba(239, 68, 68, 0.3);
        }

        .subtitle-row {
          font-size: 0.82rem;
          color: var(--text-muted);
        }

        /* 3 KAFELKI METRYK NA GÓRZE */
        .metrics-cards-row {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 14px;
          margin-bottom: 24px;
        }

        .metric-card {
          background: var(--card-surface);
          border: 1px solid #1b263b;
          border-radius: 12px;
          padding: 12px 18px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .metric-card-lbl {
          font-size: 0.7rem;
          font-weight: 700;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .metric-card-val {
          font-size: 1.15rem;
          font-weight: 800;
          color: #ffffff;
        }
        .val-blue { color: #38bdf8; }
        .val-gold { color: #f59e0b; }
        .val-green { color: #4ade80; }

        /* WIZUALIZACJA ROZDZIELACZA HYDRAULICZNEGO */
        .station-viewport {
          background: #060b17;
          border: 1px solid #19253c;
          border-radius: 16px;
          padding: 30px 20px 20px 20px;
          position: relative;
          overflow-x: auto;
          margin-bottom: 28px;
        }

        .station-inner {
          min-width: 780px;
          display: grid;
          grid-template-columns: 190px 1fr 35px;
          align-items: center;
          position: relative;
        }

        /* Pionowe uchwyty montażowe ze stali */
        .mount-bracket-1 {
          position: absolute;
          left: 215px;
          top: -20px;
          bottom: 40px;
          width: 18px;
          background: rgba(71, 85, 105, 0.45);
          border-radius: 4px;
          z-index: 1;
        }
        .mount-bracket-2 {
          position: absolute;
          right: 90px;
          top: -20px;
          bottom: 40px;
          width: 18px;
          background: rgba(71, 85, 105, 0.45);
          border-radius: 4px;
          z-index: 1;
        }

        /* LEWA KOLUMNA: TERMOMETRY ZEGAROWE I ETYKIETY BELEK */
        .left-station-col {
          display: flex;
          flex-direction: column;
          gap: 24px;
          z-index: 5;
        }

        .gauge-section {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .gauge-circle {
          width: 60px;
          height: 60px;
          border-radius: 50%;
          background: radial-gradient(circle, #0f172a 55%, #020617 100%);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          box-shadow: 0 6px 16px rgba(0,0,0,0.7), inset 0 1px 3px rgba(255,255,255,0.15);
          position: relative;
          flex-shrink: 0;
        }
        .gauge-red { border: 3.5px solid #ef4444; }
        .gauge-blue { border: 3.5px solid #0284c7; }

        .gauge-dial-title {
          font-size: 7px;
          font-weight: 800;
          color: #94a3b8;
          text-transform: uppercase;
        }
        .gauge-dial-temp {
          font-size: 13px;
          font-weight: 800;
          color: #ffffff;
        }

        .gauge-meta {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .gauge-bar-name {
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.05em;
        }
        .bar-name-red { color: #f87171; }
        .bar-name-blue { color: #38bdf8; }
        .gauge-bar-desc {
          font-size: 12px;
          font-weight: 700;
          color: #ffffff;
        }
        .gauge-bar-formula {
          font-size: 9px;
          color: #94a3b8;
        }

        .delta-t-pill {
          background: rgba(56, 189, 248, 0.1);
          border: 1px solid rgba(56, 189, 248, 0.3);
          border-radius: 8px;
          padding: 6px 12px;
          font-size: 11px;
          font-weight: 700;
          color: #38bdf8;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          width: fit-content;
        }

        /* GŁÓWNE BELKI STALOWE */
        .station-pipes-col {
          display: flex;
          flex-direction: column;
          gap: 90px;
          position: relative;
          padding: 30px 0;
          z-index: 2;
        }

        .inox-pipe {
          height: 42px;
          background: var(--steel);
          border-radius: 8px;
          border: 1px solid #475569;
          box-shadow: inset 0 2px 3px rgba(255,255,255,0.85), 0 8px 18px rgba(0,0,0,0.6);
          position: relative;
        }

        .inox-label {
          position: absolute;
          left: 16px;
          top: 13px;
          font-size: 9px;
          font-weight: 800;
          color: rgba(15, 23, 42, 0.45);
          letter-spacing: 0.06em;
          pointer-events: none;
        }

        /* WARSTWA ROTAMETRÓW (GÓRNA BELKA) */
        .rotameters-row {
          position: absolute;
          top: -72px;
          left: 10px;
          right: 10px;
          display: flex;
          justify-content: space-around;
        }

        .rotameter-station {
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 85px;
          flex-shrink: 0;
          position: relative;
          cursor: pointer;
        }

        /* Górna plakietka z wartością przepływu (np. 2.4 l/min) */
        .rot-top-badge {
          background: #091224;
          border: 1px solid #1e293b;
          border-radius: 6px;
          padding: 2px 7px;
          font-size: 11px;
          font-weight: 800;
          color: #38bdf8;
          margin-bottom: 6px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.5);
          white-space: nowrap;
          transition: all 0.15s;
        }
        .rotameter-station.active .rot-top-badge,
        .rot-top-badge.gold {
          background: #241804;
          border-color: #f59e0b;
          color: #f59e0b;
        }

        .rot-cylinder {
          width: 22px;
          height: 68px;
          background: rgba(15, 23, 42, 0.85);
          border: 1.5px solid #64748b;
          border-radius: 3px;
          position: relative;
          overflow: hidden;
          box-shadow: inset 0 0 6px rgba(56, 189, 248, 0.25);
        }

        .rot-water-col {
          position: absolute;
          bottom: 0; left: 0; right: 0;
          background: linear-gradient(180deg, #38bdf8 0%, #0284c7 100%);
          transition: height 0.3s;
        }

        .rot-red-disc {
          position: absolute;
          left: 2px; right: 2px;
          height: 5px;
          background: #ef4444;
          border-radius: 2px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.7);
          transition: bottom 0.3s;
        }

        .rot-collar {
          width: 24px;
          height: 9px;
          background: var(--brass);
          border-radius: 1px 1px 3px 3px;
        }

        /* Czerwona pionowa rura schodząca z górnej belki w dół */
        .vertical-transit-pipe {
          position: absolute;
          top: 104px;
          width: 10px;
          height: 70px;
          background: #ef4444;
          border-radius: 3px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4);
          z-index: 1;
        }

        /* WARSTWA SIŁOWNIKÓW (DOLNA BELKA) */
        .actuators-row {
          position: absolute;
          top: -20px;
          left: 10px;
          right: 10px;
          display: flex;
          justify-content: space-around;
        }

        .actuator-station {
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 85px;
          flex-shrink: 0;
          position: relative;
          cursor: pointer;
        }

        .actuator-shell {
          width: 32px;
          height: 52px;
          background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
          border: 1px solid #94a3b8;
          border-radius: 8px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 4px;
          box-shadow: 0 4px 10px rgba(0,0,0,0.4);
          transition: all 0.15s;
          z-index: 3;
        }
        .actuator-station.active .actuator-shell {
          border: 2px solid #f59e0b;
          box-shadow: 0 0 12px rgba(245, 158, 11, 0.45);
        }

        .actuator-led-pill {
          background: #14532d;
          border: 1px solid #22c55e;
          border-radius: 10px;
          padding: 1px 5px;
          font-size: 7px;
          font-weight: 800;
          color: #4ade80;
        }

        .actuator-sub-txt {
          font-size: 6px;
          font-weight: 700;
          color: #64748b;
        }

        /* Króćce i podejścia rur pod dolną belką */
        .bottom-feed-pipes {
          margin-top: 26px;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .brass-nipple {
          width: 14px;
          height: 8px;
          background: var(--brass);
          border-radius: 1px;
        }
        .pipe-drop {
          width: 8px;
          height: 28px;
          border-radius: 2px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .pipe-drop-blue { background: #0284c7; }

        .circuit-title {
          margin-top: 8px;
          font-size: 11px;
          font-weight: 700;
          color: #cbd5e1;
          text-align: center;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 85px;
          transition: color 0.15s;
        }
        .actuator-station:hover .circuit-title,
        .actuator-station.active .circuit-title {
          color: #f59e0b;
        }

        /* PRAWA STRONA: ODPOWIETRZNIK I ZAWÓR */
        .right-vents-col {
          display: flex;
          flex-direction: column;
          gap: 90px;
          align-items: center;
          z-index: 5;
        }
        .brass-vent {
          width: 16px;
          height: 42px;
          background: var(--brass);
          border-radius: 4px;
          border: 1px solid #ca8a04;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        }

        /* DOLNY GRID KAFELKÓW PĘTLI ZGODNY ZE ZRZUTEM */
        .grid-header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          flex-wrap: wrap;
          gap: 8px;
        }
        .grid-title {
          font-size: 0.85rem;
          font-weight: 800;
          color: #cbd5e1;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .grid-step-hint {
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--cyan-acc);
        }

        .loops-cards-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
          gap: 14px;
        }

        .loop-box {
          background: var(--card-surface);
          border: 1px solid #1e293b;
          border-radius: 12px;
          padding: 14px 12px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          position: relative;
          cursor: pointer;
          transition: all 0.2s;
        }
        .loop-box:hover {
          border-color: #38bdf8;
          transform: translateY(-2px);
        }

        /* ZAZNACZONY KAFELEK: AKTYWNA EDYCJA */
        .loop-box.active {
          border: 2px solid #f59e0b;
          box-shadow: 0 0 16px rgba(245, 158, 11, 0.35);
        }
        .active-edit-tag {
          position: absolute;
          top: -11px;
          right: 12px;
          background: #f59e0b;
          color: #000000;
          font-size: 9px;
          font-weight: 900;
          padding: 2px 8px;
          border-radius: 10px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .loop-top-meta {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .loop-num-area {
          font-size: 0.7rem;
          font-weight: 800;
          color: var(--text-muted);
          text-transform: uppercase;
        }
        .loop-status-pill {
          font-size: 9px;
          font-weight: 800;
          padding: 2px 6px;
          border-radius: 10px;
        }
        .pill-opt { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
        .pill-warn { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
        .pill-crit { background: rgba(239, 68, 68, 0.15); color: #f87171; }

        .loop-room-title {
          font-size: 0.95rem;
          font-weight: 800;
          color: #ffffff;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .loop-flow-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          border-bottom: 1px solid rgba(255,255,255,0.06);
          padding-bottom: 6px;
        }
        .flow-val-lmin {
          font-size: 1.25rem;
          font-weight: 900;
          color: #38bdf8;
        }
        .loop-box.active .flow-val-lmin { color: #f59e0b; }
        .flow-val-lh {
          font-size: 0.8rem;
          font-weight: 700;
          color: #cbd5e1;
        }

        .loop-details-grid {
          display: flex;
          flex-direction: column;
          gap: 3px;
          font-size: 0.72rem;
          color: #94a3b8;
        }
        .detail-item {
          display: flex;
          justify-content: space-between;
        }
        .detail-item strong {
          color: #f1f5f9;
        }
        .detail-item.warn strong {
          color: #f59e0b;
        }

        /* STEPPER STEROWANIA [-] 0.1 [+] */
        .stepper-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: #060a14;
          border: 1px solid #1e293b;
          border-radius: 8px;
          padding: 3px;
          margin-top: 4px;
        }
        .stepper-btn {
          width: 32px;
          height: 26px;
          background: #111d33;
          border: 1px solid #1e293b;
          color: #ffffff;
          border-radius: 6px;
          font-weight: 800;
          font-size: 14px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }
        .stepper-btn:hover {
          background: #0284c7;
          border-color: #38bdf8;
        }
        .stepper-step-lbl {
          font-size: 10px;
          font-weight: 800;
          color: #94a3b8;
        }

        /* IN-CARD MODAL EDYCJI PĘTLI */
        .modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.75);
          backdrop-filter: blur(4px);
          display: none;
          align-items: center;
          justify-content: center;
          z-index: 9999;
        }
        .modal-content {
          background: #0f172a;
          border: 1px solid #334155;
          border-radius: 14px;
          padding: 22px;
          width: 90%;
          max-width: 420px;
          box-shadow: 0 16px 36px rgba(0,0,0,0.6);
        }
        .modal-header {
          font-size: 1.15rem;
          font-weight: 800;
          color: #38bdf8;
          margin-bottom: 14px;
          padding-bottom: 8px;
          border-bottom: 1px solid #334155;
        }
        .form-row { margin-bottom: 12px; }
        .form-row label {
          display: block; font-size: 0.75rem; color: #94a3b8; font-weight: 700; margin-bottom: 4px; text-transform: uppercase;
        }
        .form-row input, .form-row select {
          width: 100%; box-sizing: border-box; padding: 9px 12px; background: #090e1c;
          border: 1px solid #334155; border-radius: 8px; color: #f8fafc; font-size: 0.95rem; outline: none;
        }
        .form-row input:focus, .form-row select:focus { border-color: #38bdf8; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
        .btn-modal { padding: 8px 16px; border-radius: 8px; font-size: 0.85rem; font-weight: 700; cursor: pointer; border: none; }
        .btn-save { background: #0284c7; color: white; }
        .btn-cancel { background: #334155; color: #cbd5e1; }
      
        /* ROOM-FIRST KONFIGURACJA POMIESZCZEŃ I PĘTLI */
        .header-action-btn {
          background: rgba(56, 189, 248, 0.15);
          border: 1px solid rgba(56, 189, 248, 0.45);
          color: #38bdf8;
          border-radius: 10px;
          padding: 5px 12px;
          font-size: 0.78rem;
          font-weight: 700;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s ease;
          margin-left: auto;
        }
        .header-action-btn:hover {
          background: rgba(56, 189, 248, 0.3);
          border-color: #38bdf8;
          transform: translateY(-1px);
        }

        .rooms-modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(15, 23, 42, 0.75);
          backdrop-filter: blur(6px);
          display: none;
          align-items: center;
          justify-content: center;
          z-index: 99999;
          padding: 16px;
          box-sizing: border-box;
        }
        .rooms-modal-container {
          background: #fcf8f8;
          color: #1c1917;
          width: 100%;
          max-width: 680px;
          border-radius: 24px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          border: 1px solid #e7e5e4;
          display: flex;
          flex-direction: column;
          max-height: 90vh;
          overflow: hidden;
          box-sizing: border-box;
        }
        .modal-top-bar {
          padding: 16px 20px;
          background: #ffffff;
          border-bottom: 1px solid #e7e5e4;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-shrink: 0;
        }
        .modal-top-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .modal-icon-btn {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          border: none;
          background: transparent;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #57534e;
          transition: background 0.2s;
        }
        .modal-icon-btn:hover {
          background: #f5f5f4;
        }
        .modal-icon-btn svg {
          width: 20px;
          height: 20px;
          fill: currentColor;
        }
        .modal-title {
          font-size: 1.15rem;
          font-weight: 800;
          color: #1c1917;
          margin: 0;
          letter-spacing: -0.01em;
        }
        .modal-subtitle {
          font-size: 0.75rem;
          color: #78716c;
          margin: 2px 0 0 0;
        }

        .rooms-sticky-summary {
          background: #1e1b4b;
          color: #ffffff;
          padding: 12px 20px;
          flex-shrink: 0;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 14px;
          box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
        }
        .summary-stat-group {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .summary-col {
          display: flex;
          flex-direction: column;
        }
        .summary-label {
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #a5b4fc;
          font-weight: 600;
        }
        .summary-val-row {
          display: flex;
          align-items: baseline;
          gap: 4px;
          margin-top: 2px;
        }
        .summary-num {
          font-size: 1.25rem;
          font-weight: 800;
          color: #ffffff;
          line-height: 1.2;
        }
        .summary-num.text-emerald {
          color: #34d399;
        }
        .summary-sub {
          font-size: 0.78rem;
          color: #a5b4fc;
        }
        .summary-sep {
          width: 1px;
          height: 30px;
          background: rgba(99, 102, 241, 0.4);
        }
        .slots-visual-box {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
        }
        .slots-dots-container {
          display: flex;
          gap: 4px;
        }
        .slot-dot {
          width: 20px;
          height: 24px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          font-weight: 800;
          transition: all 0.2s ease;
        }
        .slot-dot.occupied {
          background: #34d399;
          color: #0f172a;
          transform: scale(1.05);
        }
        .slot-dot.free {
          background: rgba(49, 46, 129, 0.7);
          color: #818cf8;
          border: 1px solid #3730a3;
        }
        .slots-status-text {
          font-size: 11px;
          color: #c7d2fe;
          margin-top: 3px;
        }

        .rooms-help-banner {
          background: #fffbeb;
          border-bottom: 1px solid #fde68a;
          padding: 10px 20px;
          font-size: 12px;
          color: #78350f;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .help-close-btn {
          font-weight: 800;
          color: #b45309;
          background: transparent;
          border: none;
          cursor: pointer;
        }

        .rooms-list-scrollable {
          padding: 16px 20px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 14px;
          flex: 1;
        }
        .room-card {
          background: #ffffff;
          border: 1px solid #e7e5e4;
          border-radius: 16px;
          overflow: hidden;
          box-shadow: 0 1px 2px rgba(0,0,0,0.05);
          transition: border-color 0.2s ease;
        }
        .room-card:hover {
          border-color: #d6d3d1;
        }
        .room-card-head {
          padding: 12px 16px;
          border-bottom: 1px solid #f5f5f4;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .room-head-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .room-card-idx {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: #f5f5f4;
          color: #57534e;
          font-size: 12px;
          font-weight: 800;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid #e7e5e4;
        }
        .room-card-title-badge {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #a8a29e;
        }
        .room-delete-btn {
          background: transparent;
          border: none;
          color: #a8a29e;
          cursor: pointer;
          padding: 4px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s ease;
        }
        .room-delete-btn:hover {
          color: #e11d48;
          background: #ffe4e6;
        }
        .room-delete-btn svg {
          width: 16px;
          height: 16px;
          fill: currentColor;
        }

        .room-grid {
          display: grid;
          grid-template-columns: 5fr 3fr 4fr;
          gap: 10px;
          padding: 12px 16px;
        }
        @media (max-width: 600px) {
          .room-grid { grid-template-columns: 1fr; }
        }
        .room-field-group {
          display: flex;
          flex-direction: column;
        }
        .room-field-group label {
          font-size: 11px;
          font-weight: 600;
          color: #78716c;
          margin-bottom: 4px;
        }
        .room-field-group input, .room-field-group select {
          width: 100%;
          box-sizing: border-box;
          padding: 8px 12px;
          background: rgba(245, 245, 244, 0.7);
          border: 1px solid #d6d3d1;
          border-radius: 10px;
          font-size: 13px;
          font-weight: 600;
          color: #1c1917;
          outline: none;
          transition: all 0.2s ease;
        }
        .room-field-group input:focus, .room-field-group select:focus {
          border-color: #4f46e5;
          background: #ffffff;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
        }

        .room-loops-section {
          padding: 12px 16px 16px 16px;
          background: #ffffff;
          border-top: 1px solid #f5f5f4;
        }
        .loops-stepper-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
        }
        .loops-stepper-label {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 700;
          color: #374151;
        }
        .loops-stepper-label svg {
          width: 16px;
          height: 16px;
          fill: #4f46e5;
        }
        .stepper-control-box {
          display: flex;
          align-items: center;
          gap: 4px;
          background: #f5f5f4;
          padding: 3px;
          border-radius: 10px;
          border: 1px solid #e7e5e4;
        }
        .stepper-btn-mini {
          width: 26px;
          height: 26px;
          border-radius: 7px;
          background: #ffffff;
          border: none;
          font-size: 14px;
          font-weight: 800;
          color: #374151;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 1px 2px rgba(0,0,0,0.06);
          transition: all 0.15s ease;
        }
        .stepper-btn-mini:hover {
          background: #f1f5f9;
        }
        .stepper-btn-mini.btn-plus {
          background: #4f46e5;
          color: #ffffff;
        }
        .stepper-btn-mini.btn-plus:hover {
          background: #4338ca;
        }
        .stepper-btn-mini:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        .stepper-num-val {
          width: 28px;
          text-align: center;
          font-size: 13px;
          font-weight: 800;
          color: #1e1b4b;
        }

        .loop-row-card {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          background: rgba(245, 245, 244, 0.9);
          padding: 8px 12px;
          border-radius: 10px;
          border: 1px solid rgba(231, 229, 228, 0.8);
          margin-bottom: 6px;
        }
        .loop-row-left {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .loop-badge-tag {
          padding: 3px 8px;
          border-radius: 6px;
          background: #e0e7ff;
          color: #312e81;
          font-weight: 800;
          font-size: 11px;
          border: 1px solid #c7d2fe;
        }
        .loop-desc-txt {
          font-size: 12px;
          color: #78716c;
        }
        .loop-desc-txt strong {
          color: #292524;
        }
        .loop-flow-ctrl {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .loop-flow-ctrl label {
          font-size: 11px;
          font-weight: 600;
          color: #57534e;
        }
        .flow-box-mini {
          display: flex;
          align-items: center;
          background: #ffffff;
          border: 1px solid #d6d3d1;
          border-radius: 8px;
          padding: 2px 4px;
        }
        .flow-box-mini input {
          width: 36px;
          border: none;
          background: transparent;
          text-align: center;
          font-size: 13px;
          font-weight: 800;
          color: #1c1917;
          outline: none;
        }
        .flow-box-mini button {
          width: 24px;
          height: 24px;
          border: none;
          background: transparent;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 800;
          color: #57534e;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .flow-box-mini button:hover {
          background: #f5f5f4;
        }

        .rooms-add-bar {
          padding: 12px 20px;
          background: #f5f5f4;
          border-top: 1px solid #e7e5e4;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          flex-shrink: 0;
        }
        .btn-dashed-add {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          border-radius: 10px;
          background: #ffffff;
          border: 2px dashed #a5b4fc;
          color: #312e81;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .btn-dashed-add:hover {
          border-color: #4f46e5;
          background: #eef2ff;
        }
        .btn-dashed-add svg {
          width: 16px;
          height: 16px;
          fill: currentColor;
        }
        .quick-tags-row {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }
        .quick-tags-lbl {
          font-size: 11px;
          color: #a8a29e;
        }
        .quick-tag-chip {
          background: #ffffff;
          border: 1px solid #d6d3d1;
          padding: 4px 10px;
          border-radius: 7px;
          font-size: 11px;
          font-weight: 600;
          color: #44403c;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .quick-tag-chip:hover {
          background: #e7e5e4;
          color: #1c1917;
        }

        .rooms-modal-footer {
          padding: 14px 20px;
          background: #ffffff;
          border-top: 1px solid #e7e5e4;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-shrink: 0;
        }
        .footer-note {
          font-size: 12px;
          color: #78716c;
        }
        .footer-btns {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .btn-footer-primary {
          padding: 9px 22px;
          border-radius: 20px;
          font-size: 13px;
          font-weight: 700;
          background: #3f4773;
          color: #ffffff;
          border: none;
          cursor: pointer;
          box-shadow: 0 4px 10px rgba(63, 71, 115, 0.3);
          transition: all 0.2s ease;
        }
        .btn-footer-primary:hover {
          background: #31385e;
          transform: translateY(-1px);
        }
        .btn-footer-secondary {
          padding: 8px 16px;
          border-radius: 20px;
          font-size: 13px;
          font-weight: 600;
          background: transparent;
          color: #57534e;
          border: none;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .btn-footer-secondary:hover {
          background: #f5f5f4;
          color: #1c1917;
        }

        .toast-popup {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: #1c1917;
          color: #ffffff;
          padding: 12px 20px;
          border-radius: 16px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.4);
          font-size: 13px;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 10px;
          z-index: 100000;
          transform: translateY(100px);
          opacity: 0;
          transition: all 0.3s ease;
        }
        .toast-popup.show {
          transform: translateY(0);
          opacity: 1;
        }
        .toast-icon {
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: rgba(34, 197, 94, 0.2);
          color: #4ade80;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
        }
</style>

      <div class="card-container">
        <!-- 1. GŁÓWNY NAGŁÓWEK -->
        <div class="main-header">
          <div class="menu-btn" id="btn-manifold-menu" title="Otwórz konfigurację rozdzielacza">
            <svg viewBox="0 0 24 24"><path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"/></svg>
          </div>
          <div class="title-block">
            <div class="title-row">
              <span class="manifold-title" id="card-title">Rozdzielacz Parter</span>
              <span class="status-badge" id="card-status-badge">
                <span style="font-size:8px;">●</span> <span id="card-status-txt">Zrównoważony hydraulicznie</span>
              </span>
              <button class="header-action-btn" id="btn-config-rooms" title="Konfiguruj strefy i rotametry">
                ⚙️ Konfiguracja pętli (Pomieszczenia)
              </button>
            </div>
          </div>
            <div class="subtitle-row" id="card-subtitle">
              Lokalizacja: Kotłownia / Parter • Posadzka bazowa: Wylewka anhydrytowa (45 mm, λ = 1.8 W/(m·K))
            </div>
          </div>
        </div>

        <!-- 2. TRZY KARTY METRYK -->
        <div class="metrics-cards-row">
          <div class="metric-card">
            <div class="metric-card-lbl">PRZEPŁYW SUMARYCZNY</div>
            <div class="metric-card-val val-blue" id="stat-sum-flow">11.4 l/min (684 l/h)</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-lbl">PĘTLA KRYTYCZNA (ΔP_MAX)</div>
            <div class="metric-card-val val-gold" id="stat-crit-dp">18.4 kPa (184 mbar)</div>
          </div>
          <div class="metric-card">
            <div class="metric-card-lbl">RÓŻNICA ΔT</div>
            <div class="metric-card-val val-green" id="stat-delta-t">6.0 °C (Moc: ~4.78 kW)</div>
          </div>
        </div>

        <!-- 3. FOTOREALISTYCZNY ROZDZIELACZ HYDRAULICZNY -->
        <div class="station-viewport">
          <div class="station-inner">
            <div class="mount-bracket-1"></div>
            <div class="mount-bracket-2"></div>

            <!-- LEWA STRONA: TERMOMETRY ZEGAROWE -->
            <div class="left-station-col">
              <!-- Zasilanie 38.0°C -->
              <div class="gauge-section">
                <div class="gauge-circle gauge-red">
                  <div class="gauge-dial-title">ZASILANIE</div>
                  <div class="gauge-dial-temp">38.0°C</div>
                </div>
                <div class="gauge-meta">
                  <div class="gauge-bar-name bar-name-red">BELKA GÓRNA</div>
                  <div class="gauge-bar-desc">Zasilająca</div>
                  <div class="gauge-bar-formula">T_{zas} = 38°C</div>
                </div>
              </div>

              <!-- Pigułka ΔT -->
              <div class="delta-t-pill">
                <span>ΔT = 6.0°C</span>
                <span style="color:#4ade80;font-size:10px;">(Optymalna)</span>
              </div>

              <!-- Powrót 32.0°C -->
              <div class="gauge-section">
                <div class="gauge-circle gauge-blue">
                  <div class="gauge-dial-title">POWRÓT</div>
                  <div class="gauge-dial-temp">32.0°C</div>
                </div>
                <div class="gauge-meta">
                  <div class="gauge-bar-name bar-name-blue">BELKA DOLNA</div>
                  <div class="gauge-bar-desc">Powrotna</div>
                  <div class="gauge-bar-formula">T_{pow} = 32°C</div>
                </div>
              </div>
            </div>

            <!-- ŚRODEK: BELKI STALOWE + ROTAMETRY + SIŁOWNIKI -->
            <div class="station-pipes-col">
              <!-- Belka górna: Zasilanie -->
              <div class="inox-pipe">
                <span class="inox-label">INOX AISI 304 - ZASILANIE (FLOW)</span>
                <div class="rotameters-row" id="rotameters-layer"></div>
              </div>

              <!-- Belka dolna: Powrót -->
              <div class="inox-pipe">
                <span class="inox-label">INOX AISI 304 - POWRÓT (RETURN)</span>
                <div class="actuators-row" id="actuators-layer"></div>
              </div>
            </div>

            <!-- PRAWA STRONA: ODPOWIETRZNIK -->
            <div class="right-vents-col">
              <div class="brass-vent" title="Odpowietrznik automatyczny i spust"></div>
              <div class="brass-vent" title="Zawór spustowy"></div>
            </div>
          </div>
        </div>

        <!-- 4. DOLNY GRID KAFELKÓW PĘTLI -->
        <div class="grid-header-row">
          <div class="grid-title">SEKCJE PĘTLI GRZEWCZYCH (KLIKNIJ KAFELEK, ABY OTWORZYĆ IN-CARD MODAL EDYCJI)</div>
          <div class="grid-step-hint">Krok regulacji rotametru: ±0.1 l/min</div>
        </div>

        <div class="loops-cards-grid" id="loops-cards-grid"></div>
      </div>

      <!-- MODAL EDYCJI PĘTLI -->
      <div class="modal-overlay" id="edit-modal">
        <div class="modal-content">
          <div class="modal-header" id="modal-heading">Edytuj pętlę</div>
          <div class="form-row">
            <label>Nazwa pomieszczenia</label>
            <input type="text" id="modal-inp-room">
          </div>
          <div class="form-row">
            <label>Powierzchnia strefy (m²)</label>
            <input type="number" id="modal-inp-area" step="0.5" min="1">
          </div>
          <div class="form-row">
            <label>Przepływ zadany (l/min)</label>
            <input type="number" id="modal-inp-flow" step="0.1" min="0.1" max="6.0">
          </div>
          <div class="form-row">
            <label>Rodzaj wylewki / posadzki</label>
            <select id="modal-inp-screed">
              <option value="default">Domyślna rozdzielacza</option>
              <option value="cement">Wylewka cementowa tradycyjna</option>
              <option value="anhydrite">Wylewka anhydrytowa płynna</option>
              <option value="dry_screed">Sucha zabudowa (płyty gipsowe)</option>
            </select>
          </div>
          <div class="modal-actions">
            <button class="btn-modal btn-cancel" id="modal-btn-cancel">Anuluj</button>
            <button class="btn-modal btn-save" id="modal-btn-save">Zapisz</button>
          </div>
        </div>
      </div>

      <!-- MODAL ROOM-FIRST KONFIGURACJA POMIESZCZEŃ I PĘTLI -->
      <div class="rooms-modal-overlay" id="rooms-config-modal">
        <div class="rooms-modal-container">
          <div class="modal-top-bar">
            <div class="modal-top-left">
              <button class="modal-icon-btn" id="rooms-modal-close" title="Zamknij">
                <svg viewBox="0 0 24 24"><path d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z"/></svg>
              </button>
              <div>
                <h2 class="modal-title" id="rooms-modal-title">Konfiguracja pętli – Rozdzielacz Parter</h2>
                <p class="modal-subtitle">Grupuj pętle według pomieszczeń, aby szybciej skonfigurować przepływy</p>
              </div>
            </div>
            <button class="modal-icon-btn" id="rooms-modal-help-btn" title="Pomoc">
              <svg viewBox="0 0 24 24"><path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M11,16.5H13V18.5H11V16.5M12,7A3,3 0 0,0 9,10H11A1,1 0 0,1 12,9A1,1 0 0,1 13,10C13,11.5 10.75,11.25 10.75,13.5H12.75C12.75,12 15,11.75 15,10A3,3 0 0,0 12,7Z"/></svg>
            </button>
          </div>

          <div class="rooms-sticky-summary">
            <div class="summary-stat-group">
              <div class="summary-col">
                <span class="summary-label">ZAJĘTE SEKCJE (PĘTLE)</span>
                <div class="summary-val-row">
                  <span class="summary-num" id="rm-total-loops">0</span>
                  <span class="summary-sub" id="rm-max-loops">/ 10 dostępnych</span>
                </div>
              </div>
              <div class="summary-sep"></div>
              <div class="summary-col">
                <span class="summary-label">CAŁKOWITA POWIERZCHNIA</span>
                <div class="summary-val-row">
                  <span class="summary-num" id="rm-total-area">0</span>
                  <span class="summary-sub">m²</span>
                </div>
              </div>
              <div class="summary-sep"></div>
              <div class="summary-col">
                <span class="summary-label">SUMA PRZEPŁYWÓW</span>
                <div class="summary-val-row">
                  <span class="summary-num text-emerald" id="rm-total-flow">0.0</span>
                  <span class="summary-sub">l/min</span>
                </div>
              </div>
            </div>

            <div class="slots-visual-box">
              <div class="slots-dots-container" id="rm-slots-container"></div>
              <span class="slots-status-text" id="rm-slots-status">Rozdzielacz: 10-obwodowy</span>
            </div>
          </div>

          <div class="rooms-help-banner" id="rm-help-banner" style="display:none;">
            <div>
              <strong>Wskazówka:</strong> Dodaj pomieszczenie (np. <em>Salon</em>), wpisz jego łączny metraż i wybierz wylewkę. Następnie kliknij <strong>+</strong> przy liczbie pętli, jeśli w tym pomieszczeniu ułożono więcej niż jeden obwód grzewczy.
            </div>
            <button class="help-close-btn" id="rm-help-close">OK</button>
          </div>

          <div class="rooms-list-scrollable" id="rm-rooms-list"></div>

          <div class="rooms-add-bar">
            <button class="btn-dashed-add" id="rm-add-room-btn">
              <svg viewBox="0 0 24 24"><path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z"/></svg>
              Dodaj pomieszczenie
            </button>
            <div class="quick-tags-row">
              <span class="quick-tags-lbl">Szybkie dodanie:</span>
              <button class="quick-tag-chip" id="tag-wc">+ WC</button>
              <button class="quick-tag-chip" id="tag-bath">+ Łazienka</button>
              <button class="quick-tag-chip" id="tag-bed">+ Sypialnia</button>
              <button class="quick-tag-chip" id="tag-hall">+ Korytarz</button>
            </div>
          </div>

          <div class="rooms-modal-footer">
            <div class="footer-note">Wszystkie zmiany są przeliczane na bieżąco.</div>
            <div class="footer-btns">
              <button class="btn-footer-secondary" id="rm-btn-reset">Przywróć domyślne</button>
              <button class="btn-footer-primary" id="rm-btn-save">Zatwierdź</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Toast Powiadomienie -->
      <div class="toast-popup" id="card-toast">
        <span class="toast-icon" id="card-toast-icon">✓</span>
        <span class="toast-msg" id="card-toast-msg">Zapisano konfigurację!</span>
      </div>
    `;

    // Podpięcie modala
    const modalCancel = this.shadowRoot.getElementById("modal-btn-cancel");
    const modalSave = this.shadowRoot.getElementById("modal-btn-save");
    if (modalCancel) modalCancel.onclick = () => this._closeModal();
    if (modalSave) modalSave.onclick = () => this._saveModal();

    // Podpięcie modala konfiguracji pomieszczeń
    const btnMenu = this.shadowRoot.getElementById("btn-manifold-menu");
    const btnCfgRooms = this.shadowRoot.getElementById("btn-config-rooms");
    const rmClose = this.shadowRoot.getElementById("rooms-modal-close");
    const rmHelpBtn = this.shadowRoot.getElementById("rooms-modal-help-btn");
    const rmHelpClose = this.shadowRoot.getElementById("rm-help-close");
    const rmAddBtn = this.shadowRoot.getElementById("rm-add-room-btn");
    const rmResetBtn = this.shadowRoot.getElementById("rm-btn-reset");
    const rmSaveBtn = this.shadowRoot.getElementById("rm-btn-save");

    if (btnMenu) btnMenu.onclick = () => this._openRoomsConfigModal();
    if (btnCfgRooms) btnCfgRooms.onclick = () => this._openRoomsConfigModal();
    if (rmClose) rmClose.onclick = () => this._closeRoomsConfigModal();
    if (rmHelpBtn) rmHelpBtn.onclick = () => this._toggleHelp();
    if (rmHelpClose) rmHelpClose.onclick = () => this._toggleHelp();
    if (rmAddBtn) rmAddBtn.onclick = () => this._addRoom();
    if (rmResetBtn) rmResetBtn.onclick = () => this._resetRoomsToDefault();
    if (rmSaveBtn) rmSaveBtn.onclick = () => this._saveRoomsConfig();

    const tagWc = this.shadowRoot.getElementById("tag-wc");
    const tagBath = this.shadowRoot.getElementById("tag-bath");
    const tagBed = this.shadowRoot.getElementById("tag-bed");
    const tagHall = this.shadowRoot.getElementById("tag-hall");
    if (tagWc) tagWc.onclick = () => this._addQuickRoom("WC", 4, "Anhydrytowa (samopoziomująca)", [1.0]);
    if (tagBath) tagBath.onclick = () => this._addQuickRoom("Łazienka", 9, "Domyślna rozdzielacza", [1.8]);
    if (tagBed) tagBed.onclick = () => this._addQuickRoom("Sypialnia", 14, "Domyślna rozdzielacza", [1.5]);
    if (tagHall) tagHall.onclick = () => this._addQuickRoom("Korytarz", 8, "Domyślna rozdzielacza", [1.2]);


    this.updateCard();
  }

  updateCard() {
    if (!this.shadowRoot) return;

    const states = (this._hass && this._hass.states) || {};
    const manifolds = {};
    const loops = [];

    // Zbieranie rozdzielaczy i pętli z encji Home Assistant
    Object.keys(states).forEach(entityId => {
      const stateObj = states[entityId];
      if (!stateObj) return;

      if (entityId.includes("manifold_") && entityId.includes("_total_flow")) {
        const match = entityId.match(/manifold_([a-zA-Z0-9_]+)_total_flow/);
        if (match) {
          const mId = match[1];
          manifolds[mId] = {
            id: mId,
            name: stateObj.attributes.friendly_name || mId,
            total_flow: parseFloat(stateObj.state) || 0.0,
            sections_count: stateObj.attributes.sections_count || 6,
            location: stateObj.attributes.location || "Kotłownia / Parter",
            screed: stateObj.attributes.screed_type || "Wylewka anhydrytowa (45 mm, λ = 1.8 W/(m·K))",
            status: stateObj.attributes.status || "Zrównoważony hydraulicznie",
          };
        }
      }

      if (entityId.includes("loop_") && (entityId.includes("_rotameter_flow_lmin") || entityId.includes("_rotameter_flow_lh"))) {
        const isLmin = entityId.includes("lmin");
        const val = parseFloat(stateObj.state) || 0.0;
        const attrs = stateObj.attributes || {};
        const loopId = attrs.loop_id || entityId;

        const existing = loops.find(l => l.id === loopId);
        if (existing) {
          if (isLmin) {
            existing.flow_lmin = val;
            existing.flow_lh = Math.round(val * 60);
          } else {
            existing.flow_lh = val;
            existing.flow_lmin = parseFloat((val / 60.0).toFixed(1));
          }
        } else {
          loops.push({
            id: loopId,
            entity_id: entityId,
            name: attrs.friendly_name || loopId,
            room: attrs.room || attrs.zone_name || (attrs.friendly_name ? attrs.friendly_name.split(":")[1] || attrs.friendly_name : "Obieg"),
            section: attrs.section_number || (loops.length + 1),
            flow_lmin: isLmin ? val : parseFloat((val / 60.0).toFixed(1)),
            flow_lh: isLmin ? Math.round(val * 60) : val,
            length_m: attrs.estimated_length_m || 85.0,
            area_m2: attrs.area_m2 || 14.0,
            dp_kpa: attrs.pressure_drop_kpa || 12.5,
            screed: attrs.screed_type || "default",
            manifold_id: attrs.manifold_id || Object.keys(manifolds)[0] || "parter",
          });
        }
      }
    });

    // Wzorcowe dane demonstracyjne odpowiadające zrzutowi
    if (loops.length === 0) {
      manifolds["parter"] = {
        id: "parter",
        name: "Rozdzielacz Parter",
        location: "Kotłownia / Parter",
        screed: "Posadzka bazowa: Wylewka anhydrytowa (45 mm, λ = 1.8 W/(m·K))",
        status: "Zrównoważony hydraulicznie",
      };

      const demo = [
        { section: 1, room: "Salon - Strefa Okna", lmin: 2.4, area: 16.5, len: 113.3, dp: 16.8, status: "Optymalny", screed_txt: "Domyślna (Anh.)" },
        { section: 2, room: "Salon - Strefa TV", lmin: 2.1, area: 14.0, len: 96.1, dp: 11.4, status: "Optymalny", screed_txt: "Domyślna (Anh.)" },
        { section: 3, room: "Kuchnia i Jadalnia", lmin: 1.8, area: 12.0, len: 82.4, dp: 7.9, status: "Optymalny", screed_txt: "Domyślna (Anh.)" },
        { section: 4, room: "Łazienka Parter", lmin: 1.4, area: 8.5, len: 58.4, dp: 3.8, status: "Optymalny", screed_txt: "Cementowa (Nadpis.)" },
        { section: 5, room: "Gabinet / Biuro", lmin: 2.5, area: 14.5, len: 99.6, dp: 18.4, status: "Przewymiarowany", screed_txt: "Domyślna (Anh.)" },
        { section: 6, room: "Hol / Wiatrołap", lmin: 1.2, area: 7.0, len: 48.1, dp: 2.4, status: "Akceptowalny", screed_txt: "Domyślna (Anh.)" },
      ];

      demo.forEach(d => {
        loops.push({
          id: `petla_parter_${d.section}`,
          name: `Pętla ${d.section}: ${d.room}`,
          section: d.section,
          room: d.room,
          flow_lmin: d.lmin,
          flow_lh: Math.round(d.lmin * 60),
          length_m: d.len,
          area_m2: d.area,
          dp_kpa: d.dp,
          status: d.status,
          screed: d.screed_txt.includes("Cement") ? "cement" : "default",
          screed_txt: d.screed_txt,
          manifold_id: "parter",
        });
      });
    }

    this._currentLoops = loops;
    this._currentLoops.sort((a, b) => a.section - b.section);

    // Wyliczenia sumaryczne
    const totalFlowLh = this._currentLoops.reduce((acc, l) => acc + (l.flow_lh || 0), 0);
    const totalFlowLmin = (totalFlowLh / 60.0).toFixed(1);
    const maxDp = Math.max(...this._currentLoops.map(l => l.dp_kpa || 0), 0).toFixed(1);
    const powerKw = ((totalFlowLh / 3600.0) * 4.186 * 6.0).toFixed(2);

    // Aktualizacja kart metryk
    const statFlow = this.shadowRoot.getElementById("stat-sum-flow");
    const statDp = this.shadowRoot.getElementById("stat-crit-dp");
    const statDt = this.shadowRoot.getElementById("stat-delta-t");

    if (statFlow) statFlow.textContent = `${totalFlowLmin} l/min (${Math.round(totalFlowLh)} l/h)`;
    if (statDp) statDp.textContent = `${maxDp} kPa (${Math.round(maxDp * 10)} mbar)`;
    if (statDt) statDt.textContent = `6.0 °C (Moc: ~${powerKw} kW)`;

    // RYSOWANIE ROTAMETRÓW NA GÓRNEJ BELCE
    const rotLayer = this.shadowRoot.getElementById("rotameters-layer");
    if (rotLayer) {
      rotLayer.innerHTML = this._currentLoops.map((loop, idx) => {
        const fillPct = Math.min(Math.max((loop.flow_lmin / 4.0) * 100, 15), 90);
        const isSelected = idx === this._selectedLoopIndex;
        return `
          <div class="rotameter-station ${isSelected ? 'active' : ''}" data-idx="${idx}" title="${loop.room}: ${loop.flow_lmin.toFixed(1)} l/min">
            <div class="rot-top-badge ${isSelected ? 'gold' : ''}">${loop.flow_lmin.toFixed(1)} l/min</div>
            <div class="rot-cylinder">
              <div class="rot-water-col" style="height: ${fillPct}%;"></div>
              <div class="rot-red-disc" style="bottom: ${fillPct}%;"></div>
            </div>
            <div class="rot-collar"></div>
            <!-- Czerwona rurka zasilania w dół -->
            <div class="vertical-transit-pipe"></div>
          </div>
        `;
      }).join("");

      rotLayer.querySelectorAll(".rotameter-station").forEach(el => {
        el.onclick = () => {
          const idx = parseInt(el.getAttribute("data-idx"));
          this._selectLoop(idx);
        };
      });
    }

    // RYSOWANIE SIŁOWNIKÓW NA DOLNEJ BELCE
    const actLayer = this.shadowRoot.getElementById("actuators-layer");
    if (actLayer) {
      actLayer.innerHTML = this._currentLoops.map((loop, idx) => {
        const isSelected = idx === this._selectedLoopIndex;
        return `
          <div class="actuator-station ${isSelected ? 'active' : ''}" data-idx="${idx}">
            <div class="actuator-shell">
              <span class="actuator-led-pill">ON</span>
              <span class="actuator-sub-txt">230V NC</span>
            </div>
            <div class="bottom-feed-pipes">
              <div class="brass-nipple"></div>
              <div class="pipe-drop pipe-drop-blue"></div>
            </div>
            <div class="circuit-title">#${loop.section} ${loop.room.split("-")[0].trim()}</div>
          </div>
        `;
      }).join("");

      actLayer.querySelectorAll(".actuator-station").forEach(el => {
        el.onclick = () => {
          const idx = parseInt(el.getAttribute("data-idx"));
          this._selectLoop(idx);
        };
      });
    }

    // RYSOWANIE DOLNEGO GRIDU KAFELKÓW
    const grid = this.shadowRoot.getElementById("loops-cards-grid");
    if (grid) {
      grid.innerHTML = this._currentLoops.map((loop, idx) => {
        const isSelected = idx === this._selectedLoopIndex;
        const statusClass = (loop.status === "Optymalny" || !loop.status) ? "pill-opt" : (loop.status === "Przewymiarowany" ? "pill-warn" : "pill-crit");
        const statusTxt = loop.status || "Optymalny";

        return `
          <div class="loop-box ${isSelected ? 'active' : ''}" data-idx="${idx}">
            ${isSelected ? '<div class="active-edit-tag">AKTYWNA EDYCJA</div>' : ''}
            <div class="loop-top-meta">
              <span class="loop-num-area">PĘTLA #${loop.section} • ${loop.area_m2} M²</span>
              <span class="loop-status-pill ${statusClass}">${statusTxt}</span>
            </div>
            <div class="loop-room-title" title="${loop.room}">${loop.room}</div>
            
            <div class="loop-flow-row">
              <span class="flow-val-lmin">${loop.flow_lmin.toFixed(1)} <small style="font-size:0.65em">l/min</small></span>
              <span class="flow-val-lh">${Math.round(loop.flow_lh)} l/h</span>
            </div>

            <div class="loop-details-grid">
              <div class="detail-item">
                <span>Długość rury:</span>
                <strong>${loop.length_m} m</strong>
              </div>
              <div class="detail-item ${isSelected ? 'warn' : ''}">
                <span>Spadek Δp:</span>
                <strong>${loop.dp_kpa} kPa</strong>
              </div>
              <div class="detail-item">
                <span>Posadzka:</span>
                <span>${loop.screed_txt || (loop.screed === "cement" ? "Cementowa" : "Domyślna (Anh.)")}</span>
              </div>
            </div>

            <div class="stepper-row" onclick="event.stopPropagation();">
              <button class="stepper-btn" data-idx="${idx}" data-step="-0.1">[-]</button>
              <span class="stepper-step-lbl">0.1</span>
              <button class="stepper-btn" data-idx="${idx}" data-step="+0.1">[+]</button>
            </div>
          </div>
        `;
      }).join("");

      // Kliknięcie w kafelek -> zaznaczenie lub otwarcie modala
      grid.querySelectorAll(".loop-box").forEach(box => {
        box.onclick = () => {
          const idx = parseInt(box.getAttribute("data-idx"));
          if (this._selectedLoopIndex === idx) {
            this._openModal(idx);
          } else {
            this._selectLoop(idx);
          }
        };
      });

      // Przyciski [-] [+] regulacji przepływu
      grid.querySelectorAll(".stepper-btn").forEach(btn => {
        btn.onclick = e => {
          e.stopPropagation();
          const idx = parseInt(btn.getAttribute("data-idx"));
          const step = parseFloat(btn.getAttribute("data-step"));
          const targetLoop = this._currentLoops[idx];
          if (!targetLoop) return;

          const newLmin = Math.max(0.1, Math.min(6.0, parseFloat((targetLoop.flow_lmin + step).toFixed(1))));
          targetLoop.flow_lmin = newLmin;
          targetLoop.flow_lh = Math.round(newLmin * 60);

          if (this._hass && targetLoop.entity_id) {
            const isLmin = targetLoop.entity_id.includes("lmin");
            this._hass.callService("number", "set_value", {
              entity_id: targetLoop.entity_id,
              value: isLmin ? newLmin : (newLmin * 60),
            });
          }
          this._selectLoop(idx);
        };
      });
    }
  }

  _selectLoop(idx) {
    this._selectedLoopIndex = idx;
    this.updateCard();
  }

  _openModal(idx) {
    const loop = this._currentLoops[idx];
    if (!loop) return;

    this._selectedLoopIndex = idx;
    const modal = this.shadowRoot.getElementById("edit-modal");
    const heading = this.shadowRoot.getElementById("modal-heading");
    const inpRoom = this.shadowRoot.getElementById("modal-inp-room");
    const inpArea = this.shadowRoot.getElementById("modal-inp-area");
    const inpFlow = this.shadowRoot.getElementById("modal-inp-flow");
    const inpScreed = this.shadowRoot.getElementById("modal-inp-screed");

    if (heading) heading.textContent = `Edytuj Pętlę #${loop.section} (${loop.room})`;
    if (inpRoom) inpRoom.value = loop.room;
    if (inpArea) inpArea.value = loop.area_m2 || 15.0;
    if (inpFlow) inpFlow.value = loop.flow_lmin || 1.5;
    if (inpScreed) inpScreed.value = loop.screed || "default";

    if (modal) modal.style.display = "flex";
  }

  _closeModal() {
    const modal = this.shadowRoot.getElementById("edit-modal");
    if (modal) modal.style.display = "none";
  }

  _saveModal() {
    if (this._selectedLoopIndex === null) return;
    const loop = this._currentLoops[this._selectedLoopIndex];
    if (!loop) return;

    const inpRoom = this.shadowRoot.getElementById("modal-inp-room");
    const inpArea = this.shadowRoot.getElementById("modal-inp-area");
    const inpFlow = this.shadowRoot.getElementById("modal-inp-flow");
    const inpScreed = this.shadowRoot.getElementById("modal-inp-screed");

    const newRoom = inpRoom ? inpRoom.value.trim() : loop.room;
    const newArea = inpArea ? parseFloat(inpArea.value) : loop.area_m2;
    const newFlow = inpFlow ? parseFloat(inpFlow.value) : loop.flow_lmin;
    const newScreed = inpScreed ? inpScreed.value : loop.screed;

    loop.room = newRoom;
    loop.area_m2 = newArea;
    loop.flow_lmin = newFlow;
    loop.flow_lh = Math.round(newFlow * 60);
    loop.screed = newScreed;
    loop.screed_txt = newScreed === "cement" ? "Cementowa (Nadpis.)" : "Domyślna (Anh.)";

    if (this._hass) {
      if (loop.entity_id) {
        const isLmin = loop.entity_id.includes("lmin");
        this._hass.callService("number", "set_value", {
          entity_id: loop.entity_id,
          value: isLmin ? newFlow : (newFlow * 60),
        });
      }
      this._hass.callService("underfloor_heating", "update_loop", {
        loop_id: loop.id,
        name: `Pętla ${loop.section}: ${newRoom}`,
        area_m2: newArea,
        screed_type: newScreed === "default" ? "anhydrite" : newScreed,
      }).catch(() => {});
    }

    this._closeModal();
    this.updateCard();
  }

  // =========================================================================
  // METODY OBSŁUGI ROOM-FIRST KONFIGURATORA POMIESZCZEŃ I PĘTLI
  // =========================================================================

  _initRoomsConfig() {
    if (this._roomsConfig && this._roomsConfig.length > 0) return;

    if (this._currentLoops && this._currentLoops.length > 0) {
      const roomMap = new Map();
      this._currentLoops.forEach(l => {
        const raw = l.room || "Strefa";
        const rName = raw.split("-")[0].trim() || raw;
        if (!roomMap.has(rName)) {
          roomMap.set(rName, {
            id: "room-" + roomMap.size,
            name: rName,
            area: 0,
            screed: l.screed === "cement" ? "Cementowa (tradycyjna)" : (l.screed === "anhydrite" ? "Anhydrytowa (samopoziomująca)" : "Domyślna rozdzielacza"),
            loops: [],
          });
        }
        const r = roomMap.get(rName);
        r.area = +(r.area + (parseFloat(l.area_m2) || 15.0)).toFixed(1);
        r.loops.push({ flow: parseFloat(l.flow_lmin) || 1.5 });
      });
      this._roomsConfig = Array.from(roomMap.values());
    } else {
      this._roomsConfig = [
        {
          id: 'room-1',
          name: 'Salon',
          area: 30,
          screed: 'Domyślna rozdzielacza',
          loops: [{ flow: 1.5 }, { flow: 1.5 }]
        },
        {
          id: 'room-2',
          name: 'Kuchnia',
          area: 15,
          screed: 'Domyślna rozdzielacza',
          loops: [{ flow: 1.5 }]
        },
        {
          id: 'room-3',
          name: 'Łazienka',
          area: 8,
          screed: 'Anhydrytowa (samopoziomująca)',
          loops: [{ flow: 1.8 }]
        },
        {
          id: 'room-4',
          name: 'WC',
          area: 3.5,
          screed: 'Domyślna rozdzielacza',
          loops: [{ flow: 1.0 }]
        }
      ];
    }
  }

  _openRoomsConfigModal() {
    this._initRoomsConfig();
    this._renderRoomsModal();
    const modal = this.shadowRoot.getElementById("rooms-config-modal");
    if (modal) modal.style.display = "flex";
  }

  _closeRoomsConfigModal() {
    const modal = this.shadowRoot.getElementById("rooms-config-modal");
    if (modal) modal.style.display = "none";
  }

  _getTotalRoomsLoops() {
    if (!this._roomsConfig) return 0;
    return this._roomsConfig.reduce((acc, r) => acc + (r.loops ? r.loops.length : 0), 0);
  }

  _renderRoomsModal() {
    const container = this.shadowRoot.getElementById("rm-rooms-list");
    if (!container || !this._roomsConfig) return;
    container.innerHTML = "";

    const screedTypes = [
      "Domyślna rozdzielacza",
      "Cementowa (tradycyjna)",
      "Anhydrytowa (samopoziomująca)",
      "Suchy jastrych (płyty)"
    ];

    let globalLoopIdx = 1;
    let totalArea = 0;
    let totalFlow = 0;

    this._roomsConfig.forEach((room, roomIdx) => {
      totalArea += parseFloat(room.area) || 0;
      const loopsCnt = room.loops ? room.loops.length : 1;
      const areaPerLoop = (parseFloat(room.area) || 0) / loopsCnt;

      let loopsHtml = "";
      if (room.loops) {
        room.loops.forEach((loop, lIdx) => {
          const curLoopNum = globalLoopIdx++;
          const flow = parseFloat(loop.flow) || 1.5;
          totalFlow += flow;

          const desc = loopsCnt > 1
            ? `Obwód ${lIdx + 1} w: <strong>${room.name || "Bez nazwy"}</strong> (~${areaPerLoop.toFixed(1)} m²)`
            : `Obwód główny (~${areaPerLoop.toFixed(1)} m²)`;

          loopsHtml += `
            <div class="loop-row-card">
              <div class="loop-row-left">
                <span class="loop-badge-tag">Pętla #${curLoopNum}</span>
                <span class="loop-desc-txt">${desc}</span>
              </div>
              <div class="loop-flow-ctrl">
                <label>Przepływ rotametru:</label>
                <div class="flow-box-mini">
                  <button type="button" class="btn-step-flow" data-ridx="${roomIdx}" data-lidx="${lIdx}" data-delta="-0.1">−</button>
                  <input type="number" step="0.1" min="0" max="6" value="${flow.toFixed(1)}" class="inp-flow-val" data-ridx="${roomIdx}" data-lidx="${lIdx}">
                  <span style="font-size:11px;color:#78716c;margin-right:4px;">l/min</span>
                  <button type="button" class="btn-step-flow" data-ridx="${roomIdx}" data-lidx="${lIdx}" data-delta="0.1">+</button>
                </div>
              </div>
            </div>
          `;
        });
      }

      const screedOpts = screedTypes.map(t =>
        `<option value="${t}" ${room.screed === t ? "selected" : ""}>${t}</option>`
      ).join("");

      const roomCard = document.createElement("div");
      roomCard.className = "room-card";
      roomCard.innerHTML = `
        <div class="room-card-head">
          <div class="room-head-left">
            <span class="room-card-idx">${roomIdx + 1}</span>
            <span class="room-card-title-badge">Pomieszczenie</span>
          </div>
          <button class="room-delete-btn" data-ridx="${roomIdx}" title="Usuń pomieszczenie">
            <svg viewBox="0 0 24 24"><path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/></svg>
          </button>
        </div>
        <div class="room-grid">
          <div class="room-field-group">
            <label>Nazwa pomieszczenia*</label>
            <input type="text" value="${room.name}" class="inp-room-name" data-ridx="${roomIdx}" placeholder="np. Salon, Kuchnia...">
          </div>
          <div class="room-field-group">
            <label>Powierzchnia* (m²)</label>
            <input type="number" step="0.5" min="1" value="${room.area}" class="inp-room-area" data-ridx="${roomIdx}">
          </div>
          <div class="room-field-group">
            <label>Rodzaj wylewki (posadzka)</label>
            <select class="sel-room-screed" data-ridx="${roomIdx}">
              ${screedOpts}
            </select>
          </div>
        </div>
        <div class="room-loops-section">
          <div class="loops-stepper-header">
            <div class="loops-stepper-label">
              <svg viewBox="0 0 24 24"><path d="M4,4V9H4.58L6.5,7.08C7.9,5.68 9.85,4.8 12,4.8A7.2,7.2 0 0,1 19.2,12C19.2,13.75 18.57,15.35 17.53,16.59L18.95,18C20.35,16.38 21.2,14.29 21.2,12A9.2,9.2 0 0,0 12,2.8C9.3,2.8 6.88,3.9 5.12,5.68L4,4.56V4H4M4,12C4,14.7 5.1,17.12 6.88,18.88L8,20H3V15H3.58L5.5,16.92C6.9,18.32 8.85,19.2 11,19.2A7.2,7.2 0 0,0 18.2,12C18.2,10.25 17.57,8.65 16.53,7.41L15.11,6C13.71,7.62 12.86,9.71 12.86,12A9.2,9.2 0 0,1 4,12Z"/></svg>
              <span>Liczba pętli w tym pomieszczeniu</span>
            </div>
            <div class="stepper-control-box">
              <button type="button" class="stepper-btn-mini btn-room-loops-step" data-ridx="${roomIdx}" data-delta="-1" ${loopsCnt <= 1 ? "disabled" : ""}>−</button>
              <span class="stepper-num-val">${loopsCnt}</span>
              <button type="button" class="stepper-btn-mini btn-plus btn-room-loops-step" data-ridx="${roomIdx}" data-delta="1">+</button>
            </div>
          </div>
          <div class="loops-rows-container">
            ${loopsHtml}
          </div>
        </div>
      `;
      container.appendChild(roomCard);
    });

    // Podpięcie eventów pól
    container.querySelectorAll(".inp-room-name").forEach(inp => {
      inp.oninput = (e) => {
        const ridx = parseInt(e.target.dataset.ridx);
        this._roomsConfig[ridx].name = e.target.value;
      };
      inp.onchange = () => this._renderRoomsModal();
    });

    container.querySelectorAll(".inp-room-area").forEach(inp => {
      inp.oninput = (e) => {
        const ridx = parseInt(e.target.dataset.ridx);
        this._roomsConfig[ridx].area = parseFloat(e.target.value) || 0;
      };
      inp.onchange = () => this._renderRoomsModal();
    });

    container.querySelectorAll(".sel-room-screed").forEach(sel => {
      sel.onchange = (e) => {
        const ridx = parseInt(e.target.dataset.ridx);
        this._roomsConfig[ridx].screed = e.target.value;
        this._renderRoomsModal();
      };
    });

    container.querySelectorAll(".room-delete-btn").forEach(btn => {
      btn.onclick = (e) => {
        const ridx = parseInt(e.currentTarget.dataset.ridx);
        this._removeRoom(ridx);
      };
    });

    container.querySelectorAll(".btn-room-loops-step").forEach(btn => {
      btn.onclick = (e) => {
        const ridx = parseInt(e.currentTarget.dataset.ridx);
        const delta = parseInt(e.currentTarget.dataset.delta);
        this._changeRoomLoopCount(ridx, delta);
      };
    });

    container.querySelectorAll(".btn-step-flow").forEach(btn => {
      btn.onclick = (e) => {
        const ridx = parseInt(e.currentTarget.dataset.ridx);
        const lidx = parseInt(e.currentTarget.dataset.lidx);
        const delta = parseFloat(e.currentTarget.dataset.delta);
        this._adjustRoomLoopFlow(ridx, lidx, delta);
      };
    });

    container.querySelectorAll(".inp-flow-val").forEach(inp => {
      inp.onchange = (e) => {
        const ridx = parseInt(e.target.dataset.ridx);
        const lidx = parseInt(e.target.dataset.lidx);
        this._updateRoomLoopFlowInput(ridx, lidx, e.target.value);
      };
    });

    // Aktualizacja górnego paska sticky
    const totalLoops = globalLoopIdx - 1;
    const elLoops = this.shadowRoot.getElementById("rm-total-loops");
    const elArea = this.shadowRoot.getElementById("rm-total-area");
    const elFlow = this.shadowRoot.getElementById("rm-total-flow");

    if (elLoops) elLoops.textContent = totalLoops;
    if (elArea) elArea.textContent = totalArea.toFixed(1).replace('.0', '');
    if (elFlow) elFlow.textContent = totalFlow.toFixed(1);

    this._renderManifoldSlots(totalLoops);
  }

  _renderManifoldSlots(activeLoops) {
    const slotsContainer = this.shadowRoot.getElementById("rm-slots-container");
    const statusText = this.shadowRoot.getElementById("rm-slots-status");
    if (!slotsContainer || !statusText) return;
    slotsContainer.innerHTML = "";

    const maxSlots = 10;
    for (let i = 1; i <= maxSlots; i++) {
      const isOccupied = i <= activeLoops;
      const slot = document.createElement("div");
      slot.className = `slot-dot ${isOccupied ? "occupied" : "free"}`;
      slot.textContent = i;
      slot.title = isOccupied ? `Sekcja ${i}: Zajęta` : `Sekcja ${i}: Wolna`;
      slotsContainer.appendChild(slot);
    }

    if (activeLoops === maxSlots) {
      statusText.textContent = "Wszystkie 10 sekcji rozdzielacza obsadzone";
      statusText.style.color = "#34d399";
    } else if (activeLoops > maxSlots) {
      statusText.textContent = `Przekroczono liczbę sekcji o ${activeLoops - maxSlots}!`;
      statusText.style.color = "#f87171";
    } else {
      statusText.textContent = `Wolne sekcje na belce: ${maxSlots - activeLoops}`;
      statusText.style.color = "#c7d2fe";
    }
  }

  _changeRoomLoopCount(roomIdx, delta) {
    const cur = this._getTotalRoomsLoops();
    if (delta > 0 && cur >= 10) {
      this._showToast("Rozdzielacz ma maksymalnie 10 sekcji!", true);
      return;
    }
    const r = this._roomsConfig[roomIdx];
    if (!r.loops) r.loops = [];
    if (delta > 0) {
      const lastFlow = r.loops.length > 0 ? r.loops[r.loops.length - 1].flow : 1.5;
      r.loops.push({ flow: lastFlow });
    } else if (delta < 0 && r.loops.length > 1) {
      r.loops.pop();
    }
    this._renderRoomsModal();
  }

  _adjustRoomLoopFlow(roomIdx, loopIdx, delta) {
    const r = this._roomsConfig[roomIdx];
    let cur = parseFloat(r.loops[loopIdx].flow) || 1.5;
    let next = Math.max(0, Math.min(6, +(cur + delta).toFixed(1)));
    r.loops[loopIdx].flow = next;
    this._renderRoomsModal();
  }

  _updateRoomLoopFlowInput(roomIdx, loopIdx, val) {
    let parsed = parseFloat(String(val).replace(',', '.'));
    if (isNaN(parsed) || parsed < 0) parsed = 0;
    if (parsed > 6) parsed = 6;
    this._roomsConfig[roomIdx].loops[loopIdx].flow = +parsed.toFixed(1);
    this._renderRoomsModal();
  }

  _addRoom() {
    if (this._getTotalRoomsLoops() >= 10) {
      this._showToast("Wszystkie 10 sekcji na rozdzielaczu jest już zajęte.", true);
      return;
    }
    this._roomsConfig.push({
      id: "room-" + Date.now(),
      name: "Nowe pomieszczenie",
      area: 12,
      screed: "Domyślna rozdzielacza",
      loops: [{ flow: 1.5 }]
    });
    this._renderRoomsModal();
    const c = this.shadowRoot.getElementById("rm-rooms-list");
    if (c) setTimeout(() => c.scrollTo({ top: c.scrollHeight, behavior: "smooth" }), 50);
  }

  _addQuickRoom(name, area, screed, flows) {
    if (this._getTotalRoomsLoops() + flows.length > 10) {
      this._showToast("Brak wolnych sekcji na rozdzielaczu (max 10).", true);
      return;
    }
    this._roomsConfig.push({
      id: "room-" + Date.now(),
      name: name,
      area: area,
      screed: screed,
      loops: flows.map(f => ({ flow: f }))
    });
    this._renderRoomsModal();
    const c = this.shadowRoot.getElementById("rm-rooms-list");
    if (c) setTimeout(() => c.scrollTo({ top: c.scrollHeight, behavior: "smooth" }), 50);
  }

  _removeRoom(roomIdx) {
    if (this._roomsConfig.length <= 1) {
      this._showToast("Musi pozostać przynajmniej jedno pomieszczenie.", true);
      return;
    }
    this._roomsConfig.splice(roomIdx, 1);
    this._renderRoomsModal();
  }

  _toggleHelp() {
    const banner = this.shadowRoot.getElementById("rm-help-banner");
    if (banner) {
      banner.style.display = banner.style.display === "none" ? "flex" : "none";
    }
  }

  _resetRoomsToDefault() {
    this._roomsConfig = [
      {
        id: 'room-1',
        name: 'Salon',
        area: 30,
        screed: 'Domyślna rozdzielacza',
        loops: [{ flow: 1.5 }, { flow: 1.5 }]
      },
      {
        id: 'room-2',
        name: 'Kuchnia',
        area: 15,
        screed: 'Domyślna rozdzielacza',
        loops: [{ flow: 1.5 }]
      },
      {
        id: 'room-3',
        name: 'Łazienka',
        area: 8,
        screed: 'Anhydrytowa (samopoziomująca)',
        loops: [{ flow: 1.8 }]
      },
      {
        id: 'room-4',
        name: 'WC',
        area: 3.5,
        screed: 'Domyślna rozdzielacza',
        loops: [{ flow: 1.0 }]
      }
    ];
    this._renderRoomsModal();
    this._showToast("Przywrócono układ początkowy.");
  }

  _syncCurrentLoopsFromRooms() {
    const newLoops = [];
    let sec = 1;
    this._roomsConfig.forEach(room => {
      const loopsCnt = room.loops ? room.loops.length : 1;
      const areaPer = (parseFloat(room.area) || 0) / loopsCnt;

      room.loops.forEach((lp, lIdx) => {
        const flow = parseFloat(lp.flow) || 1.5;
        const pipeLen = Math.round(areaPer * 6.5 + 4.0);
        const dp = +(flow * 1.8 + pipeLen * 0.08).toFixed(1);
        let status = "Optymalny";
        if (flow > 2.2) status = "Przewymiarowany";
        else if (flow < 1.0) status = "Zbyt mały";

        const title = loopsCnt > 1 ? `${room.name} - Obwód ${lIdx + 1}` : room.name;

        newLoops.push({
          id: `petla_parter_${sec}`,
          section: sec++,
          room: title,
          area_m2: +areaPer.toFixed(1),
          flow_lmin: flow,
          flow_lh: Math.round(flow * 60),
          length_m: pipeLen,
          dp_kpa: dp,
          screed: room.screed && room.screed !== "Domyślna rozdzielacza" ? (room.screed.includes("Cement") ? "cement" : "anhydrite") : "default",
          screed_txt: room.screed === "Domyślna rozdzielacza" ? "Domyślna (Anh.)" : room.screed,
          status: status,
        });
      });
    });

    this._currentLoops = newLoops;
    if (this._selectedLoopIndex >= this._currentLoops.length) {
      this._selectedLoopIndex = 0;
    }
  }

  _saveRoomsConfig() {
    const totalLoops = this._getTotalRoomsLoops();

    if (this._hass) {
      const mId = this._activeManifoldId || "rozdzielacz_parter";
      this._hass.callService("underfloor_heating", "save_manifold_configuration", {
        manifold_id: mId,
        rooms: this._roomsConfig,
      }).catch(err => {
        console.warn("Błąd zapisu konfiguracji w HA:", err);
      });
    }

    this._syncCurrentLoopsFromRooms();
    this._closeRoomsConfigModal();
    this.updateCard();
    this._showToast(`Zapisano pomyślnie! Skonfigurowano ${this._roomsConfig.length} pomieszczeń (${totalLoops} pętli).`);
  }

  _showToast(msg, isError = false) {
    const toast = this.shadowRoot.getElementById("card-toast");
    const txt = this.shadowRoot.getElementById("card-toast-msg");
    const icon = this.shadowRoot.getElementById("card-toast-icon");
    if (!toast || !txt) return;

    txt.textContent = msg;
    if (isError) {
      icon.textContent = "!";
      icon.style.background = "rgba(244, 63, 94, 0.2)";
      icon.style.color = "#fb7185";
    } else {
      icon.textContent = "✓";
      icon.style.background = "rgba(34, 197, 94, 0.2)";
      icon.style.color = "#4ade80";
    }

    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 3200);
  }

}

customElements.define("underfloor-heating-card", UnderfloorHeatingCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "underfloor-heating-card",
  name: "Rozdzielacz Podłogówki (Visual)",
  description: "Fotorealistyczna wizualizacja rozdzielacza hydraulicznego ogrzewania podłogowego 1:1.",
  preview: true,
});
