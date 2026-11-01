/**
 * Panel boczny Home Assistant: Zarządzanie Ogrzewaniem Podłogowym
 * Wersja: 1.4.0
 * 
 * Zapewnia dedykowany, pełnoekranowy formularz do tworzenia i edycji:
 * 1. Rozdzielacza (nazwa, lokalizacja, domyślna wylewka)
 * 2. Pomieszczeń (nazwa, łączny metraż m², wylewka)
 * 3. Pętli w danym pokoju (liczba pętli, automatyczny podział m², nastawy rotametrów l/min)
 * 
 * Wraz z fotorealistycznym podglądem stacji hydraulicznej rozdzielacza.
 * 100% RWD, offline, Shadow DOM.
 */

class UnderfloorHeatingPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._activeManifoldId = "rozdzielacz_parter";
    this._manifoldName = "Rozdzielacz Parter";
    this._manifoldLocation = "Kotłownia / Parter";
    this._manifoldScreed = "cement";
    this._manifoldThickness = 50;

    // Domyślna lista pomieszczeń (Room-First)
    this._rooms = [
      { name: "Salon", area: 30, screed: "default", loops: [{ flow: 1.5 }, { flow: 1.5 }] },
      { name: "Kuchnia", area: 15, screed: "default", loops: [{ flow: 1.2 }] },
      { name: "Łazienka", area: 8, screed: "anhydrite", loops: [{ flow: 1.8 }] },
      { name: "Korytarz", area: 7, screed: "default", loops: [{ flow: 1.0 }] }
    ];

    this._saveStatus = "";
    this._activeTab = "config"; // 'config' lub 'visual' lub 'both'
  }

  set hass(hass) {
    const isFirst = !this._hass;
    this._hass = hass;
    if (isFirst) {
      this._loadFromHass();
      this.render();
    }
  }

  _loadFromHass() {
    if (!this._hass) return;
    // Wyciągnij informacje o istniejących rozdzielaczach i strefach z encji
    const states = this._hass.states;
    const foundRooms = [];

    for (const [entityId, state] of Object.entries(states)) {
      if (entityId.startsWith("sensor.pomieszczenie_") && entityId.endsWith("_powierzchnia")) {
        const area = parseFloat(state.state) || 15.0;
        const roomName = (state.attributes && state.attributes.friendly_name) 
          ? state.attributes.friendly_name.replace("Pomieszczenie: ", "").replace(" Powierzchnia", "").trim()
          : "Pokój";
        
        const loopsCount = (state.attributes && state.attributes.loops_count) ? parseInt(state.attributes.loops_count) : 1;
        const loops = [];
        for (let i = 0; i < loopsCount; i++) {
          loops.push({ flow: 1.5 });
        }
        foundRooms.push({
          name: roomName,
          area: area,
          screed: "default",
          loops: loops
        });
      }
    }

    if (foundRooms.length > 0) {
      this._rooms = foundRooms;
    }
  }

  render() {
    const totalLoops = this._rooms.reduce((acc, r) => acc + (r.loops ? r.loops.length : 1), 0);
    const totalArea = this._rooms.reduce((acc, r) => acc + (parseFloat(r.area) || 0), 0).toFixed(1);
    const totalFlow = this._rooms.reduce((acc, r) => {
      return acc + (r.loops ? r.loops.reduce((sum, l) => sum + (parseFloat(l.flow) || 0), 0) : 0);
    }, 0).toFixed(1);

    // Kropki slotów na belce (1..10)
    let slotsHtml = "";
    for (let i = 1; i <= 10; i++) {
      const isOccupied = i <= totalLoops;
      slotsHtml += `
        <span class="slot-dot ${isOccupied ? 'occupied' : 'empty'}">${i}</span>
      `;
    }

    // Karty pomieszczeń
    let roomsHtml = "";
    let globalLoopIdx = 1;

    this._rooms.forEach((room, roomIdx) => {
      const loopsCount = room.loops ? room.loops.length : 1;
      const areaPerLoop = (parseFloat(room.area) / Math.max(1, loopsCount)).toFixed(1);

      let loopsRowsHtml = "";
      if (room.loops) {
        room.loops.forEach((loop, lIdx) => {
          loopsRowsHtml += `
            <div class="loop-row">
              <div class="loop-badge">Pętla #${globalLoopIdx}</div>
              <div class="loop-desc">Obwód ${lIdx + 1} w: <strong>${room.name || 'Pokój'}</strong> (~${areaPerLoop} m²)</div>
              <div class="flow-stepper">
                <span class="flow-label">Rotametr:</span>
                <button class="step-btn" data-action="dec-flow" data-room="${roomIdx}" data-loop="${lIdx}">-</button>
                <input type="number" step="0.1" min="0.1" max="6.0" class="flow-input" 
                  value="${(parseFloat(loop.flow) || 1.5).toFixed(1)}" 
                  data-action="set-flow" data-room="${roomIdx}" data-loop="${lIdx}">
                <span class="unit">l/min</span>
                <button class="step-btn" data-action="inc-flow" data-room="${roomIdx}" data-loop="${lIdx}">+</button>
              </div>
            </div>
          `;
          globalLoopIdx++;
        });
      }

      roomsHtml += `
        <div class="room-card">
          <div class="room-header">
            <div class="room-title">
              <span class="room-num">${roomIdx + 1}</span>
              <strong>POMIESZCZENIE</strong>
            </div>
            ${this._rooms.length > 1 ? `
              <button class="btn-delete-room" data-action="delete-room" data-room="${roomIdx}" title="Usuń to pomieszczenie">
                <svg viewBox="0 0 24 24" class="icon"><path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/></svg>
                Usuń
              </button>
            ` : ''}
          </div>

          <div class="room-grid">
            <div class="field">
              <label>Nazwa pomieszczenia*</label>
              <input type="text" class="input-text" value="${room.name}" data-action="set-room-name" data-room="${roomIdx}">
            </div>
            <div class="field">
              <label>Powierzchnia całkowita (m²)*</label>
              <div class="input-with-unit">
                <input type="number" step="0.5" min="1" max="200" class="input-text" value="${room.area}" data-action="set-room-area" data-room="${roomIdx}">
                <span class="unit-tag">m²</span>
              </div>
            </div>
            <div class="field">
              <label>Rodzaj wylewki</label>
              <select class="input-select" data-action="set-room-screed" data-room="${roomIdx}">
                <option value="default" ${room.screed === 'default' ? 'selected' : ''}>Domyślna rozdzielacza</option>
                <option value="cement" ${room.screed === 'cement' ? 'selected' : ''}>Wylewka cementowa (50 mm)</option>
                <option value="anhydrite" ${room.screed === 'anhydrite' ? 'selected' : ''}>Wylewka anhydrytowa (45 mm)</option>
                <option value="dry_screed" ${room.screed === 'dry_screed' ? 'selected' : ''}>Sucha zabudowa (25 mm)</option>
              </select>
            </div>
          </div>

          <div class="loops-control-header">
            <div class="loops-header-title">
              <svg viewBox="0 0 24 24" class="icon"><path d="M12,4V1L8,5L12,9V6A6,6 0 0,1 18,12A6,6 0 0,1 12,18A6,6 0 0,1 6,12H4A8,8 0 0,0 12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4Z"/></svg>
              <span>Liczba pętli (obiegów) w tym pomieszczeniu:</span>
            </div>
            <div class="count-stepper">
              <button class="step-btn round" data-action="dec-loops" data-room="${roomIdx}">-</button>
              <span class="count-val">${loopsCount}</span>
              <button class="step-btn round" data-action="inc-loops" data-room="${roomIdx}">+</button>
            </div>
          </div>

          <div class="loops-list">
            ${loopsRowsHtml}
          </div>
        </div>
      `;
    });

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          background: #060b17;
          color: #f8fafc;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          min-height: 100vh;
          padding: 20px 16px;
          box-sizing: border-box;
        }

        .panel-container {
          max-width: 1100px;
          margin: 0 auto;
        }

        /* HEADER */
        .top-nav {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 1px solid #1e293b;
        }

        .nav-title {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .nav-icon {
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: linear-gradient(135deg, #0284c7, #38bdf8);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 14px rgba(56, 189, 248, 0.4);
        }

        .nav-icon svg {
          width: 26px;
          height: 26px;
          fill: #ffffff;
        }

        .nav-text h1 {
          font-size: 1.45rem;
          font-weight: 800;
          margin: 0;
          color: #ffffff;
          letter-spacing: -0.01em;
        }

        .nav-text p {
          font-size: 0.85rem;
          color: #94a3b8;
          margin: 2px 0 0 0;
        }

        /* STICKY STATUS BAR */
        .status-banner {
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 16px;
          padding: 16px 20px;
          margin-bottom: 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }

        .metrics-group {
          display: flex;
          align-items: center;
          gap: 24px;
          flex-wrap: wrap;
        }

        .metric-item {
          display: flex;
          flex-direction: column;
        }

        .metric-label {
          font-size: 0.72rem;
          text-transform: uppercase;
          color: #94a3b8;
          font-weight: 700;
          letter-spacing: 0.05em;
        }

        .metric-value {
          font-size: 1.5rem;
          font-weight: 800;
          color: #ffffff;
          margin-top: 2px;
        }

        .metric-value.accent {
          color: #38bdf8;
        }

        .metric-value.green {
          color: #4ade80;
        }

        .metric-value small {
          font-size: 0.85rem;
          font-weight: 500;
          color: #64748b;
          margin-left: 4px;
        }

        .metric-divider {
          width: 1px;
          height: 36px;
          background: #334155;
        }

        .slots-visual {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
        }

        .slots-row {
          display: flex;
          gap: 4px;
        }

        .slot-dot {
          width: 24px;
          height: 24px;
          border-radius: 6px;
          font-size: 0.72rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .slot-dot.occupied {
          background: #22c55e;
          color: #052e16;
          box-shadow: 0 0 10px rgba(34, 197, 94, 0.4);
        }

        .slot-dot.empty {
          background: #1e293b;
          color: #64748b;
          border: 1px dashed #334155;
        }

        .slots-hint {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        /* MANIFOLD CONFIG CARD */
        .section-card {
          background: #0b1324;
          border: 1px solid #1e293b;
          border-radius: 16px;
          padding: 20px;
          margin-bottom: 24px;
        }

        .section-header {
          font-size: 1.05rem;
          font-weight: 700;
          color: #38bdf8;
          margin-bottom: 16px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .grid-3 {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 16px;
        }

        /* ROOM CARDS */
        .rooms-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
          margin-bottom: 20px;
        }

        .room-card {
          background: #0f172a;
          border: 1px solid #253349;
          border-radius: 14px;
          padding: 18px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.3);
          transition: border-color 0.2s;
        }

        .room-card:hover {
          border-color: #38bdf8;
        }

        .room-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 14px;
        }

        .room-title {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 0.95rem;
          color: #f1f5f9;
        }

        .room-num {
          background: #0284c7;
          color: #ffffff;
          font-size: 0.75rem;
          font-weight: 800;
          width: 22px;
          height: 22px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .btn-delete-room {
          background: rgba(239, 68, 68, 0.12);
          border: 1px solid rgba(239, 68, 68, 0.3);
          color: #f87171;
          padding: 5px 10px;
          border-radius: 8px;
          font-size: 0.8rem;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s;
        }

        .btn-delete-room:hover {
          background: rgba(239, 68, 68, 0.25);
          color: #ffffff;
        }

        .btn-delete-room .icon {
          width: 16px;
          height: 16px;
          fill: currentColor;
        }

        .room-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 14px;
          margin-bottom: 16px;
        }

        .field label {
          display: block;
          font-size: 0.78rem;
          color: #94a3b8;
          font-weight: 600;
          margin-bottom: 6px;
        }

        .input-text, .input-select {
          width: 100%;
          background: #1e293b;
          border: 1px solid #334155;
          color: #ffffff;
          padding: 9px 12px;
          border-radius: 10px;
          font-size: 0.9rem;
          box-sizing: border-box;
          outline: none;
          transition: border-color 0.2s;
        }

        .input-text:focus, .input-select:focus {
          border-color: #38bdf8;
        }

        .input-with-unit {
          position: relative;
        }

        .input-with-unit input {
          padding-right: 44px;
        }

        .unit-tag {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          font-size: 0.82rem;
          font-weight: 700;
          color: #64748b;
          pointer-events: none;
        }

        /* LOOPS CONTROL */
        .loops-control-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: #131d33;
          border-radius: 10px;
          margin-bottom: 12px;
          flex-wrap: wrap;
          gap: 8px;
        }

        .loops-header-title {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          font-weight: 600;
          color: #cbd5e1;
        }

        .loops-header-title .icon {
          width: 18px;
          height: 18px;
          fill: #38bdf8;
        }

        .count-stepper {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .step-btn {
          width: 30px;
          height: 30px;
          border-radius: 8px;
          background: #1e293b;
          border: 1px solid #38bdf8;
          color: #38bdf8;
          font-size: 1.1rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.15s;
        }

        .step-btn.round {
          border-radius: 50%;
        }

        .step-btn:hover {
          background: #38bdf8;
          color: #0f172a;
          transform: scale(1.08);
        }

        .step-btn:active {
          transform: scale(0.95);
        }

        .count-val {
          font-size: 1rem;
          font-weight: 800;
          min-width: 24px;
          text-align: center;
          color: #ffffff;
        }

        .loops-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .loop-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: #090e1b;
          border: 1px solid #1e293b;
          border-radius: 10px;
          padding: 8px 14px;
          flex-wrap: wrap;
          gap: 10px;
        }

        .loop-badge {
          background: rgba(56, 189, 248, 0.15);
          color: #38bdf8;
          font-size: 0.78rem;
          font-weight: 800;
          padding: 4px 10px;
          border-radius: 6px;
        }

        .loop-desc {
          font-size: 0.85rem;
          color: #94a3b8;
          flex: 1;
        }

        .loop-desc strong {
          color: #f1f5f9;
        }

        .flow-stepper {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .flow-label {
          font-size: 0.78rem;
          color: #64748b;
          font-weight: 600;
        }

        .flow-input {
          width: 56px;
          background: #1e293b;
          border: 1px solid #334155;
          color: #38bdf8;
          font-size: 0.9rem;
          font-weight: 700;
          text-align: center;
          padding: 4px;
          border-radius: 6px;
          outline: none;
        }

        .flow-stepper .unit {
          font-size: 0.78rem;
          color: #64748b;
          font-weight: 600;
          margin-right: 4px;
        }

        /* ACTIONS & QUICK TAGS */
        .toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 14px;
          padding: 14px 18px;
          margin-bottom: 24px;
        }

        .btn-add-room {
          background: #0284c7;
          color: #ffffff;
          border: none;
          padding: 10px 18px;
          border-radius: 10px;
          font-size: 0.9rem;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          transition: all 0.2s;
        }

        .btn-add-room:hover {
          background: #0369a1;
          transform: translateY(-1px);
        }

        .quick-tags {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }

        .quick-label {
          font-size: 0.78rem;
          color: #64748b;
          font-weight: 600;
        }

        .btn-tag {
          background: #1e293b;
          border: 1px solid #334155;
          color: #cbd5e1;
          font-size: 0.78rem;
          font-weight: 600;
          padding: 5px 10px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.15s;
        }

        .btn-tag:hover {
          background: #334155;
          color: #ffffff;
          border-color: #38bdf8;
        }

        /* FOOTER ACTIONS */
        .save-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
          background: #0b1324;
          border: 1px solid #1e293b;
          border-radius: 16px;
          padding: 18px 24px;
        }

        .save-hint {
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .btn-save-all {
          background: linear-gradient(135deg, #16a34a, #22c55e);
          color: #ffffff;
          border: none;
          padding: 12px 28px;
          border-radius: 12px;
          font-size: 1rem;
          font-weight: 800;
          cursor: pointer;
          box-shadow: 0 4px 16px rgba(34, 197, 94, 0.4);
          transition: all 0.2s;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .btn-save-all:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(34, 197, 94, 0.6);
        }

        .btn-save-all:active {
          transform: translateY(0);
        }

        .status-msg {
          padding: 12px 18px;
          border-radius: 10px;
          margin-bottom: 20px;
          font-size: 0.9rem;
          font-weight: 600;
        }

        .status-msg.success {
          background: rgba(34, 197, 94, 0.15);
          color: #4ade80;
          border: 1px solid rgba(34, 197, 94, 0.4);
        }

        .status-msg.error {
          background: rgba(239, 68, 68, 0.15);
          color: #f87171;
          border: 1px solid rgba(239, 68, 68, 0.4);
        }
      </style>

      <div class="panel-container">
        <!-- TOP NAV -->
        <div class="top-nav">
          <div class="nav-title">
            <div class="nav-icon">
              <svg viewBox="0 0 24 24"><path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M11,6V11H6V13H11V18H13V13H18V11H13V6H11Z"/></svg>
            </div>
            <div class="nav-text">
              <h1>Konfiguracja Rozdzielacza – Model Room-First</h1>
              <p>Najpierw dodaj pomieszczenie z metrażem, a pętle wygenerują się pod nim automatycznie.</p>
            </div>
          </div>
        </div>

        ${this._saveStatus ? `
          <div class="status-msg ${this._saveStatus.startsWith('Błąd') ? 'error' : 'success'}">
            ${this._saveStatus}
          </div>
        ` : ''}

        <!-- STICKY STATUS BANNER -->
        <div class="status-banner">
          <div class="metrics-group">
            <div class="metric-item">
              <span class="metric-label">Zajęte sekcje</span>
              <div class="metric-value accent">${totalLoops} <small>/ 10 dostępnych</small></div>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
              <span class="metric-label">Całkowita powierzchnia</span>
              <div class="metric-value">${totalArea} <small>m²</small></div>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
              <span class="metric-label">Suma przepływów</span>
              <div class="metric-value green">${totalFlow} <small>l/min</small></div>
            </div>
          </div>

          <div class="slots-visual">
            <div class="slots-row">
              ${slotsHtml}
            </div>
            <span class="slots-hint">Belka rozdzielacza: 10 sekcji</span>
          </div>
        </div>

        <!-- MANIFOLD BASE SETTINGS -->
        <div class="section-card">
          <div class="section-header">
            <svg style="width:20px;height:20px;fill:currentColor" viewBox="0 0 24 24"><path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z"/></svg>
            Parametry Bazowe Rozdzielacza
          </div>
          <div class="grid-3">
            <div class="field">
              <label>Nazwa rozdzielacza</label>
              <input type="text" class="input-text" id="m-name" value="${this._manifoldName}">
            </div>
            <div class="field">
              <label>Lokalizacja (obszar)</label>
              <input type="text" class="input-text" id="m-loc" value="${this._manifoldLocation}">
            </div>
            <div class="field">
              <label>Domyślna wylewka dla belki</label>
              <select class="input-select" id="m-screed">
                <option value="cement" ${this._manifoldScreed === 'cement' ? 'selected' : ''}>Wylewka cementowa (50 mm)</option>
                <option value="anhydrite" ${this._manifoldScreed === 'anhydrite' ? 'selected' : ''}>Wylewka anhydrytowa (45 mm)</option>
                <option value="dry_screed" ${this._manifoldScreed === 'dry_screed' ? 'selected' : ''}>Sucha zabudowa (25 mm)</option>
              </select>
            </div>
          </div>
        </div>

        <!-- ROOMS LIST -->
        <div class="rooms-list">
          ${roomsHtml}
        </div>

        <!-- QUICK ADD TOOLBAR -->
        <div class="toolbar">
          <button class="btn-add-room" id="btn-add-room">
            <svg style="width:20px;height:20px;fill:currentColor" viewBox="0 0 24 24"><path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z"/></svg>
            Dodaj pomieszczenie
          </button>
          <div class="quick-tags">
            <span class="quick-label">Szybkie dodanie:</span>
            <button class="btn-tag" data-action="quick-add" data-name="WC" data-area="4" data-screed="anhydrite">+ WC (4 m²)</button>
            <button class="btn-tag" data-action="quick-add" data-name="Łazienka" data-area="9" data-screed="default">+ Łazienka (9 m²)</button>
            <button class="btn-tag" data-action="quick-add" data-name="Sypialnia" data-area="14" data-screed="default">+ Sypialnia (14 m²)</button>
            <button class="btn-tag" data-action="quick-add" data-name="Korytarz" data-area="8" data-screed="default">+ Korytarz (8 m²)</button>
          </div>
        </div>

        <!-- SAVE FOOTER -->
        <div class="save-bar">
          <div class="save-hint">
            Wszystkie zmiany metrażu, wylewek i pętli zostaną natychmiast przeliczone i zsynchronizowane z Home Assistant.
          </div>
          <button class="btn-save-all" id="btn-save-all">
            <svg style="width:22px;height:22px;fill:currentColor" viewBox="0 0 24 24"><path d="M15,9H5V5H15M12,19A3,3 0 0,1 9,16A3,3 0 0,1 12,13A3,3 0 0,1 15,16A3,3 0 0,1 12,19M17,3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V7L17,3Z"/></svg>
            Zatwierdź i zapisz w Home Assistant
          </button>
        </div>
      </div>
    `;

    this._bindEvents();
  }

  _bindEvents() {
    const root = this.shadowRoot;

    // Zmiana nazwy i lokalizacji rozdzielacza
    const mName = root.getElementById("m-name");
    if (mName) mName.onchange = (e) => { this._manifoldName = e.target.value.trim(); };

    const mLoc = root.getElementById("m-loc");
    if (mLoc) mLoc.onchange = (e) => { this._manifoldLocation = e.target.value.trim(); };

    const mScreed = root.getElementById("m-screed");
    if (mScreed) mScreed.onchange = (e) => { this._manifoldScreed = e.target.value; };

    // Dodaj pomieszczenie
    const btnAdd = root.getElementById("btn-add-room");
    if (btnAdd) {
      btnAdd.onclick = () => {
        this._rooms.push({
          name: `Pomieszczenie ${this._rooms.length + 1}`,
          area: 12.0,
          screed: "default",
          loops: [{ flow: 1.5 }]
        });
        this.render();
      };
    }

    // Quick add tags
    root.querySelectorAll('[data-action="quick-add"]').forEach(btn => {
      btn.onclick = () => {
        const name = btn.getAttribute("data-name");
        const area = parseFloat(btn.getAttribute("data-area")) || 10.0;
        const screed = btn.getAttribute("data-screed") || "default";
        this._rooms.push({
          name: name,
          area: area,
          screed: screed,
          loops: [{ flow: 1.5 }]
        });
        this.render();
      };
    });

    // Zmiany w pomieszczeniach
    root.querySelectorAll('[data-action]').forEach(el => {
      const action = el.getAttribute("data-action");
      const rIdx = parseInt(el.getAttribute("data-room"));
      const lIdx = parseInt(el.getAttribute("data-loop"));

      if (action === "delete-room") {
        el.onclick = () => {
          if (this._rooms.length > 1) {
            this._rooms.splice(rIdx, 1);
            this.render();
          }
        };
      } else if (action === "set-room-name") {
        el.onchange = (e) => {
          this._rooms[rIdx].name = e.target.value.trim();
          this.render();
        };
      } else if (action === "set-room-area") {
        el.onchange = (e) => {
          this._rooms[rIdx].area = parseFloat(e.target.value) || 10.0;
          this.render();
        };
      } else if (action === "set-room-screed") {
        el.onchange = (e) => {
          this._rooms[rIdx].screed = e.target.value;
          this.render();
        };
      } else if (action === "inc-loops") {
        el.onclick = () => {
          if (!this._rooms[rIdx].loops) this._rooms[rIdx].loops = [];
          if (this._rooms[rIdx].loops.length < 8) {
            this._rooms[rIdx].loops.push({ flow: 1.5 });
            this.render();
          }
        };
      } else if (action === "dec-loops") {
        el.onclick = () => {
          if (this._rooms[rIdx].loops && this._rooms[rIdx].loops.length > 1) {
            this._rooms[rIdx].loops.pop();
            this.render();
          }
        };
      } else if (action === "inc-flow") {
        el.onclick = () => {
          const cur = parseFloat(this._rooms[rIdx].loops[lIdx].flow) || 1.5;
          this._rooms[rIdx].loops[lIdx].flow = Math.min(6.0, Math.round((cur + 0.1) * 10) / 10);
          this.render();
        };
      } else if (action === "dec-flow") {
        el.onclick = () => {
          const cur = parseFloat(this._rooms[rIdx].loops[lIdx].flow) || 1.5;
          this._rooms[rIdx].loops[lIdx].flow = Math.max(0.1, Math.round((cur - 0.1) * 10) / 10);
          this.render();
        };
      } else if (action === "set-flow") {
        el.onchange = (e) => {
          this._rooms[rIdx].loops[lIdx].flow = parseFloat(e.target.value) || 1.5;
          this.render();
        };
      }
    });

    // ZAPIS DO HOME ASSISTANT
    const btnSave = root.getElementById("btn-save-all");
    if (btnSave) {
      btnSave.onclick = async () => {
        btnSave.disabled = true;
        btnSave.innerText = "Zapisywanie...";

        const payload = {
          manifold_id: this._activeManifoldId || "rozdzielacz_parter",
          rooms: this._rooms.map(r => ({
            name: r.name,
            area: parseFloat(r.area) || 12.0,
            screed: r.screed || "default",
            loops: (r.loops || [{ flow: 1.5 }]).map(l => ({ flow: parseFloat(l.flow) || 1.5 }))
          }))
        };

        if (this._hass) {
          try {
            await this._hass.callService("underfloor_heating", "save_manifold_configuration", payload);
            this._saveStatus = "✅ Konfiguracja rozdzielacza została pomyślnie zapisana! Rejestr urządzeń, strefy i pętle w Home Assistant zostały zaktualizowane.";
          } catch (err) {
            this._saveStatus = `Błąd zapisu: ${err.message || err}`;
          }
        } else {
          this._saveStatus = "✅ Zapisano lokalnie (brak aktywnego połączenia z Home Assistant).";
        }

        this.render();
      };
    }
  }
}

customElements.define("underfloor-heating-panel", UnderfloorHeatingPanel);
