# Home Assistant: Underfloor Heating Manager 🌊🔥

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/badge/release-v1.0.0-blue.svg)]()

> **Languages / Języki / Sprachen / Idiomas:**
> [English](#-english) | [Polski](#-polski) | [Deutsch](#-deutsch) | [Español](#-español)

---

## 🇬🇧 English

### Overview
**Underfloor Heating Manager** is a Home Assistant custom integration engineered for calculation, control, and hydraulic balancing of hydronic radiant floor heating systems.

### Key Features
1. **Manifold Management**: Configure heating manifolds, monitor aggregate volume flow ($l/h$ and $l/min$), and assess maximum loop pressure drops.
2. **Zones & Screed Dynamics**: Define room areas ($m^2$), screed composition (anhydrite, cement, dry system) and thickness ($mm$). Calculates thermal mass, floor thermal resistance, and screed thermal inertia (hours).
3. **Loop Length Auto-Estimation**: Automatically computes pipe circuit lengths based on zone area, number of loops, PE pipe spacing (e.g., 10, 15, 20 cm), and manifold transit distance.
4. **Rotameters as Native HA Entities**: Direct reading and slider adjustments for flow rates ($l/h$ and $l/min$) through `number.*` entities, ready for dashboards and automations.
5. **Hydraulic Diagnostics**: Calculates flow velocity ($m/s$) and pressure drops ($\Delta p$ in $kPa$) using the Darcy-Weisbach and Colebrook-White formulations. Identifies underflowing, oversized, or excessively long loops (> 100 m for 16x2 pipes).
6. **Responsive Lovelace Card (RWD)**: Built-in visual card displaying interactive flow indicators and balancing alerts.

### Installation via Home Assistant

#### Option 1: HACS (Recommended)
1. Open **HACS** in your Home Assistant interface.
2. Click the top-right **three dots menu** and select **Custom repositories**.
3. Paste the repository URL: `https://github.com/underface/ha-underfloor-heating`
4. Select Category: **Integration**.
5. Click **Add**, locate **Underfloor Heating Manager** in the list, and select **Download**.
6. Restart Home Assistant.
7. Navigate to **Settings** $\rightarrow$ **Devices & Services** $\rightarrow$ **Add Integration**, search for **Underfloor Heating**, and follow the on-screen configuration.

#### Option 2: Manual Installation
1. Download the repository archive.
2. Copy the `custom_components/underfloor_heating` directory into your Home Assistant server's `/config/custom_components/` directory.
3. Restart Home Assistant.
4. Go to **Settings** $\rightarrow$ **Devices & Services** $\rightarrow$ **Add Integration** and select **Underfloor Heating**.

---

## 🇵🇱 Polski

### Opis wtyczki
**Zarządzanie Ogrzewaniem Podłogowym** to zaawansowana integracja dla Home Assistant służąca do parametryzacji, estymacji, regulacji oraz hydraulicznej diagnostyki wodnego ogrzewania podłogowego.

### Główne funkcje
1. **Zarządzanie rozdzielaczami**: Obsługa wielu rozdzielaczy, sumaryczny przepływ objętościowy ($l/h$ i $l/min$) oraz maksymalne straty ciśnienia na obiegach.
2. **Strefy i właściwości wylewki**: Parametryzacja powierzchni ($m^2$), rodzaju wylewki (anhydrytowa, cementowa, sucha) oraz jej grubości ($mm$). Wyliczanie masy posadzki, oporu cieplnego i bezwładności termicznej (h).
3. **Automatyczna estymacja długości pętli**: Wyliczanie długości obiegów rur PE na podstawie metrażu, liczby pętli, rozstawu (10, 15, 20 cm) oraz odległości do rozdzielacza.
4. **Rotametry jako encje w HA**: Odczyt i nastawy przepływu ($l/h$ i $l/min$) poprzez dedykowane encje `number.*` dostępne dla pulpitów i automatyzacji.
5. **Diagnostyka hydrauliczna**: Obliczanie prędkości przepływu ($m/s$) i strat ciśnienia ($\Delta p$ w $kPa$) równaniem Darcy-Weisbacha. Automatyczne wykrywanie obiegów zdławionych, przewymiarowanych oraz pętli za długich (> 100 m dla rury 16x2).
6. **Responsywna karta Lovelace (RWD)**: Zintegrowana karta z animowanymi rotametrami, pływakami i wskaźnikami zrównoważenia.

### Instalacja przez serwer Home Assistant

#### Sposób 1: Przez HACS (Rekomendowany)
1. Otwórz **HACS** w menu Home Assistant.
2. W prawym górnym rogu kliknij menu **trzy kropki** i wybierz **Niestandardowe repozytoria** (*Custom repositories*).
3. Wklej adres URL repozytorium: `https://github.com/underface/ha-underfloor-heating`
4. Wybierz kategorię: **Integracja** (*Integration*).
5. Kliknij **Dodaj** (*Add*), znajdź **Zarządzanie Ogrzewaniem Podłogowym** na liście i kliknij **Pobierz** (*Download*).
6. Zrestartuj Home Assistant.
7. Wejdź w **Ustawienia** $\rightarrow$ **Urządzenia i usługi** $\rightarrow$ **Dodaj integrację**, wyszukaj **Zarządzanie Ogrzewaniem Podłogowym** i skonfiguruj instalację.

#### Sposób 2: Instalacja ręczna
1. Pobierz archiwum projektu.
2. Skopiuj katalog `custom_components/underfloor_heating` do folderu `/config/custom_components/` na swoim serwerze Home Assistant.
3. Zrestartuj Home Assistant.
4. Przejdź do **Ustawienia** $\rightarrow$ **Urządzenia i usługi** $\rightarrow$ **Dodaj integrację** i wybierz wtyczkę z listy.

---

## 🇩🇪 Deutsch

### Übersicht
**Fußbodenheizungs-Manager** ist eine benutzerdefinierte Home Assistant-Integration zur Berechnung, Steuerung und hydraulischen Optimierung wassergeführter Fußbodenheizungssysteme.

### Hauptfunktionen
1. **Verteiler-Verwaltung**: Konfiguration von Heizkreisverteilern, Erfassung des Gesamtdurchflusses ($l/h$ und $l/min$) sowie des maximalen Druckverlusts.
2. **Heizzonen & Estrich-Dynamik**: Definition von Raumflächen ($m^2$), Estrichart (Anhydrit, Zement, Trockenbau) und Estrichdicke ($mm$). Berechnung von thermischer Masse, Wärmedurchgangswiderstand und thermischer Trägheit (Stunden).
3. **Automatische Heizkreislängen-Schätzung**: Exakte Berechnung der Rohrlängen basierend auf Raumgröße, Heizkreisanzahl, Verlegeabstand (10, 15, 20 cm) und Anbindeleitung zum Verteiler.
4. **Durchflussmesser als native HA-Entitäten**: Direktes Einstellen und Auslesen der Soll-Durchflüsse ($l/h$ und $l/min$) über `number.*`-Entitäten für Dashboards und Automatisierungen.
5. **Hydraulische Fehlerdiagnose**: Berechnung von Strömungsgeschwindigkeit ($m/s$) und Druckabfall ($\Delta p$ in $kPa$) nach Darcy-Weisbach. Erkennt hydraulisch unterversorgte, überdimensionierte oder zu lange Heizkreise (> 100 m bei 16x2 Rohr).
6. **Responsive Lovelace-Karte (RWD)**: Integrierte Benutzeroberfläche mit dynamischen Durchflussanzeigen und Abgleich-Status.

### Installation über Home Assistant

#### Option 1: HACS (Empfohlen)
1. Öffnen Sie **HACS** in Home Assistant.
2. Klicken Sie oben rechts auf das **Drei-Punkte-Menü** und wählen Sie **Benutzerdefinierte Repositories**.
3. Fügen Sie die Repository-URL ein: `https://github.com/underface/ha-underfloor-heating`
4. Wählen Sie als Kategorie: **Integration**.
5. Klicken Sie auf **Hinzufügen**, suchen Sie nach **Fußbodenheizungs-Manager** und wählen Sie **Herunterladen**.
6. Starten Sie Home Assistant neu.
7. Navigieren Sie zu **Einstellungen** $\rightarrow$ **Geräte & Dienste** $\rightarrow$ **Integration hinzufügen**, suchen Sie nach **Fußbodenheizung** und schließen Sie die Einrichtung ab.

#### Option 2: Manuelle Installation
1. Laden Sie das Projektarchiv herunter.
2. Kopieren Sie den Ordner `custom_components/underfloor_heating` in das Verzeichnis `/config/custom_components/` Ihres Home Assistant-Servers.
3. Starten Sie Home Assistant neu.
4. Gehen Sie zu **Einstellungen** $\rightarrow$ **Geräte & Dienste** $\rightarrow$ **Integration hinzufügen** und wählen Sie die Integration aus.

---

## 🇪🇸 Español

### Descripción general
**Gestor de Suelo Radiante** es una integración personalizada para Home Assistant diseñada para el cálculo, control y equilibrado hidráulico de sistemas de calefacción por suelo radiante por agua.

### Características principales
1. **Gestión de colectores**: Control de colectores de distribución, monitorización del caudal volumétrico total ($l/h$ y $l/min$) y pérdidas de carga máximas.
2. **Zonas y propiedades del recrecido**: Configuración de superficie ($m^2$), tipo de recrecido (anhidrita, cemento, solera seca) y espesor ($mm$). Cálculo de masa térmica, resistencia térmica e inercia térmica de la estancia (horas).
3. **Estimación automática de longitud de circuitos**: Cálculo automático de los metros de tubería PE según superficie, número de circuitos, separación entre tubos (10, 15, 20 cm) y distancia de conexión al colector.
4. **Caudalímetros como entidades nativas de HA**: Lectura y ajuste directo de los caudales ($l/h$ y $l/min$) mediante entidades `number.*`, preparadas para tarjetas y automatizaciones.
5. **Diagnóstico hidráulico**: Estimación de velocidad del fluido ($m/s$) y pérdidas de presión ($\Delta p$ en $kPa$) mediante la formulación de Darcy-Weisbach. Detección automática de circuitos estrangulados, sobredimensionados o con longitud excesiva (> 100 m para tubo 16x2).
6. **Tarjeta Lovelace adaptable (RWD)**: Interfaz gráfica integrada con indicadores visuales de caudalímetro y estado de equilibrio térmico.

### Instalación en el servidor Home Assistant

#### Opción 1: Mediante HACS (Recomendado)
1. Abra **HACS** en la interfaz de Home Assistant.
2. Haga clic en el **menú de tres puntos** (arriba a la derecha) y seleccione **Repositorios personalizados** (*Custom repositories*).
3. Introduzca la URL del repositorio: `https://github.com/underface/ha-underfloor-heating`
4. Seleccione la categoría: **Integración** (*Integration*).
5. Haga clic en **Añadir**, busque **Gestor de Suelo Radiante** en la lista y presione **Descargar**.
6. Reinicie Home Assistant.
7. Vaya a **Ajustes** $\rightarrow$ **Dispositivos y servicios** $\rightarrow$ **Añadir integración**, busque **Suelo Radiante** y siga el asistente de configuración.

#### Opción 2: Instalación manual
1. Descargue el archivo del repositorio.
2. Copie la carpeta `custom_components/underfloor_heating` dentro del directorio `/config/custom_components/` de su servidor Home Assistant.
3. Reinicie Home Assistant.
4. Vaya a **Ajustes** $\rightarrow$ **Dispositivos y servicios** $\rightarrow$ **Añadir integración** y seleccione la integración.
