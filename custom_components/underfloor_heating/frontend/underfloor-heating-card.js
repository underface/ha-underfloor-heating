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
      </style>

      <div class="card-container">
        <!-- 1. GŁÓWNY NAGŁÓWEK -->
        <div class="main-header">
          <div class="menu-btn" title="Opcje rozdzielacza">
            <svg viewBox="0 0 24 24"><path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"/></svg>
          </div>
          <div class="title-block">
            <div class="title-row">
              <span class="manifold-title" id="card-title">Rozdzielacz Parter</span>
              <span class="status-badge" id="card-status-badge">
                <span style="font-size:8px;">●</span> <span id="card-status-txt">Zrównoważony hydraulicznie</span>
              </span>
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
    `;

    // Podpięcie modala
    const modalCancel = this.shadowRoot.getElementById("modal-btn-cancel");
    const modalSave = this.shadowRoot.getElementById("modal-btn-save");
    if (modalCancel) modalCancel.onclick = () => this._closeModal();
    if (modalSave) modalSave.onclick = () => this._saveModal();

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
}

customElements.define("underfloor-heating-card", UnderfloorHeatingCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "underfloor-heating-card",
  name: "Rozdzielacz Podłogówki (Visual)",
  description: "Fotorealistyczna wizualizacja rozdzielacza hydraulicznego ogrzewania podłogowego 1:1.",
  preview: true,
});
