# Zarządzanie Ogrzewaniem Podłogowym dla Home Assistant 🌊🔥

Zaawansowana integracja niestandardowa (`custom_components`) do Home Assistant, służąca do parametryzacji, estymacji, sterowania i pełnej diagnostyki hydrauliczno-termicznej instalacji ogrzewania podłogowego.

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
