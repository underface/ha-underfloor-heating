# Zarządzanie Ogrzewaniem Podłogowym dla Home Assistant 🌊🔥

Zaawansowana integracja niestandardowa (`custom_components`) do Home Assistant, służąca do parametryzacji, estymacji, sterowania i pełnej diagnostyki hydrauliczno-termicznej instalacji ogrzewania podłogowego.

---

## 🚀 Jak dodać ten projekt do swojego GitHub i zainstalować na serwerze Home Assistant

Poniżej znajduje się kompletny poradnik krok po kroku.

---

### Krok 1: Utworzenie repozytorium na GitHub

1. Zaloguj się na swoje konto na [GitHub](https://github.com).
2. W prawym górnym rogu kliknij ikonę **`+`** i wybierz **New repository** (Nowe repozytorium).
3. Wpisz nazwę repozytorium, np.: `ha-underfloor-heating` lub `podlogowka-ha`.
4. Wybierz widoczność: **Public** (jeśli chcesz łatwo pobierać przez HACS) lub **Private**.
5. **Ważne:** Nie zaznaczaj opcji *"Add a README file"*, *"Add .gitignore"* ani licencji (te pliki są już przygotowane w Twoim projekcie).
6. Kliknij **Create repository**.
7. Skopiuj wygenerowany adres URL repozytorium, np.:
   `https://github.com/TWOJ_NICK/ha-underfloor-heating.git`

---

### Krok 2: Wysłanie kodu z Twojego komputera na GitHub

Otwórz terminal (PowerShell lub Git Bash) w folderze projektu `floor_heating_manager` i wykonaj poniższe komendy:

```powershell
# 1. Przejdź do folderu wtyczki (jeśli jeszcze w nim nie jesteś):
cd c:\_code\Podłogówka\floor_heating_manager

# 2. Zainicjalizuj lokalne repozytorium Git:
git init

# 3. Dodaj wszystkie pliki projektu:
git add .

# 4. Zrób pierwszy commit:
git commit -m "feat: Pierwsze wydanie integracji ogrzewania podłogowego v1.0.0"

# 5. Ustaw główną gałąź na main:
git branch -M main

# 6. Połącz lokalne repozytorium z Twoim GitHubem (wklej swój skopiowany link):
git remote add origin https://github.com/TWOJ_NICK/ha-underfloor-heating.git

# 7. Wyślij kod na GitHub:
git push -u origin main
```

*(Opcjonalnie dla wydań HACS)*: Warto utworzyć tag wydania (release):
```powershell
git tag 1.0.0
git push origin 1.0.0
```

---

### Krok 3: Dodanie integracji do Twojego serwera Home Assistant

Masz do wyboru 3 wygodne metody:

#### Metoda A: Instalacja przez HACS (Zalecana i najwygodniejsza)
Dzięki obecności pliku `hacs.json` w repozytorium, wtyczka jest w 100% zgodna z HACS:

1. Otwórz swój Home Assistant i przejdź do zakładki **HACS**.
2. Kliknij w prawe górne menu (trzy kropki) i wybierz **Niestandardowe repozytoria** (*Custom repositories*).
3. W polu **Repozytorium** wklej adres URL z GitHuba:
   `https://github.com/TWOJ_NICK/ha-underfloor-heating`
4. W polu **Kategoria** wybierz: **Integracja** (*Integration*).
5. Kliknij **Dodaj** (*Add*).
6. Wyszukaj integrację **Zarządzanie Ogrzewaniem Podłogowym** na liście HACS i kliknij **Pobierz** (*Download*).
7. Zrestartuj Home Assistant.
8. Przejdź do: **Ustawienia -> Urządzenia i usługi -> Dodaj integrację** i wyszukaj **Zarządzanie Ogrzewaniem Podłogowym**.

---

#### Metoda B: Instalacja bezpośrednio przez SSH / Terminal na serwerze HA
Jeśli posiadasz dodatek *Terminal & SSH* w Home Assistant:

1. Otwórz terminal w Home Assistant.
2. Przejdź do katalogu konfiguracji:
   ```bash
   cd /config
   ```
3. Upewnij się, że istnieje folder `custom_components`:
   ```bash
   mkdir -p custom_components
   ```
4. Sklonuj repozytorium lub skopiuj folder integracji:
   ```bash
   git clone https://github.com/TWOJ_NICK/ha-underfloor-heating.git /tmp/podlogowka
   cp -r /tmp/podlogowka/custom_components/underfloor_heating /config/custom_components/
   cp -r /tmp/podlogowka/www/underfloor-heating-card.js /config/www/
   rm -rf /tmp/podlogowka
   ```
5. Zrestartuj Home Assistant.

---

#### Metoda C: Przez zasób sieciowy Samba Share
1. Zainstaluj dodatek **Samba share** w Home Assistant.
2. Otwórz w Eksploratorze Windows udział sieciowy serwera HA: `\\homeassistant\config`.
3. Skopiuj folder:
   `c:\_code\Podłogówka\floor_heating_manager\custom_components\underfloor_heating`
   do folderu:
   `\\homeassistant\config\custom_components\underfloor_heating`
4. Skopiuj plik:
   `c:\_code\Podłogówka\floor_heating_manager\www\underfloor-heating-card.js`
   do folderu:
   `\\homeassistant\config\www\`
5. Zrestartuj Home Assistant.

---

### Krok 4: Dodanie karty graficznej Lovelace na pulpit

1. W Home Assistant przejdź do: **Pulpity -> Edytuj pulpit -> Trzy kropki -> Zarządzaj zasobami**.
2. Dodaj zasób:
   - URL: `/local/underfloor-heating-card.js`
   - Typ: `Moduł JavaScript`
3. Na wybranym pulpicie dodaj kartę manualną (kod yaml):
   ```yaml
   type: custom:underfloor-heating-card
   ```

---

## 🛠️ Zawartość i możliwości wtyczki:
1. **Rozdzielacze podłogówki**: Definiowanie rozdzielaczy, lokalizacji i liczby sekcji z sumarycznymi przepływami i maksymalnymi spadkami ciśnienia.
2. **Strefy i Pomieszczenia**: Konfiguracja powierzchni ($m^2$), typu wylewki (cementowa, anhydrytowa) oraz jej grubości (mm).
3. **Pętle podłogówki**: Powiązanie obwodów ze strefami i rozdzielaczami.
4. **Automatyczna estymacja długości pętli**: Wyliczanie długości rur PE na podstawie $m^2$, liczby pętli, rozstawu (10, 15, 20 cm) i podejścia do szafki.
5. **Ustawienia rotametrów jako encje HA**: Encje typu `number` w $l/h$ oraz $l/min$ do bezpośredniego odczytu i wprowadzania nastaw z dashboardu oraz automatyzacji.
6. **Silnik Diagnostyki Hydraulicznej**:
   - Obliczanie oporów i spadków ciśnienia $\Delta p$ w kPa.
   - Obliczanie prędkości liniowej cieczy $v$ (m/s).
   - Ocena czy pętla jest zdławiona, przewymiarowana czy zrównoważona.
   - Wykrywanie pętli zbyt długich (> 100m dla rury 16x2) oraz zbyt krótkich.
7. **Wylewka i bezwładność**: Wyliczanie masy wylewki, pojemności cieplnej (kWh/K) oraz bezwładności termicznej (h).
8. **Karta Lovelace RWD**: Responsywna karta z animowanymi słupkami rotametrów i pływakami.
