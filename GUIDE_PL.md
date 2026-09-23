# 📘 MockPulse: Kompleksowy Przewodnik Inżynieryjny (Polski)

> **Zero-Dependency Local API Mocking & Chaos Fault Injection Engine**  
> Silnik do lokalnego mockowania API oraz testów inżynierii chaosu, stworzony wyłącznie przy użyciu biblioteki standardowej Pythona. Zaprojektowany z myślą o testowaniu odporności mikrousług oraz prezentacji w procesach rekrutacyjnych na stanowiska Senior / Staff Software Engineer.

---

## 1. Przegląd Projektu i Motywacja Biznesowa

Podczas tworzenia nowoczesnych mikrousług, aplikacji internetowych oraz integracji backendowych, systemy niemal zawsze komunikują się z zewnętrznymi API (np. bramki płatności Stripe, serwisy powiadomień Twilio, systemy kurierskie czy dostawcy tożsamości).

### Wyzwanie Inżynieryjne
Testowanie sytuacji brzegowych na środowiskach stagingowych dostawców jest niezwykle trudne:
- **Niestabilne sieci:** Wywołanie kontrolowanego błędu `503 Service Unavailable` lub limitu zapytań `429 Too Many Requests` jest rzadko wspierane w piaskownicach (sandboxach) 3rd-party.
- **Zmienne opóźnienia sieciowe (Jitter):** Sprawdzenie, jak zachowa się Circuit Breaker lub mechanizm ponawiania (retry with exponential backoff) przy nagłym wzroście opóźnienia do 600 ms, wymaga skomplikowanych konfiguracji sieciowych.
- **Narzut narzędziowy:** Istniejące narzędzia (WireMock, Prism, kontenery Docker) wymagają ciężkich środowisk uruchomieniowych (JVM, Node.js), długiego czasu uruchamiania i skomplikowanej konfiguracji.

### Rozwiązanie: MockPulse
MockPulse działa w oparciu o **wyłącznie bibliotekę standardową Pythona 3** (`http.server`, `threading`, `json`, `re`, `time`, `random`). Gwarantuje:
1. Start w czasie **< 15 milisekund** przy zużyciu pamięci rzędu zaledwie **~18 MB**.
2. Deklaratywne definiowanie tras za pomocą pliku `routes.json`.
3. Prawdopodobieństwową inżynierię chaosu (Fault Injection) bezpośrednio w procesie.
4. Symulację fluktuacji opóźnień sieciowych (Latency Jitter) z dokładnością do milisekundy.
5. Bezpieczną wielowątkowo (thread-safe) telemetrię czasów odpowiedzi (P50, P90, P95, P99) w pamięci operacyjnej.
6. Przeładowywanie konfiguracji w locie (zero-downtime hot-reload) poprzez monitorowanie metadanych systemu plików VFS.

---

## 2. Architektura Systemu i Komponenty

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Klient / Konsument HTTP                         │
│               (VS Code REST Client / curl / Pytest)                    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Żądania HTTP/1.1 (TCP :8080)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Środowisko Uruchomieniowe MockPulse                                    │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 1. Warstwa Transportowa (ThreadingHTTPServer)                    │  │
│  │    • Wielowątkowy proces nasłuchujący połączeń TCP               │  │
│  │    • Dedykowany wątek roboczy (thread-per-request)               │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
│                                  │                                     │
│                                  ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 2. Dyspozytor Potoku (MockPulseRequestHandler)                   │  │
│  │    • Ekstrakcja nagłówka Content-Length oraz ciała żądania       │  │
│  │    • Normalizacja nagłówków i parametrów zapytania (query params)│  │
│  │    • Wykrywanie zmian pliku konfiguracyjnego (os.stat mtime)     │  │
│  └───────────────┬───────────────────────────────┬──────────────────┘  │
│                  │                               │                     │
│                  ▼                               ▼                     │
│  ┌───────────────────────────────┐ ┌────────────────────────────────┐  │
│  │ 3. Silnik Tras (Router)       │ │ 4. Moduł Chaosu i Błędów       │  │
│  │    • Pamięć podręczna Regex   │ │    • Symulator jittera opóźnień│  │
│  │    • Ekstrakcja parametrów    │ │    • Prawdopodobieństwo błędu  │  │
│  │    • Rozróżnianie RFC 404/405 │ │    • Wstrzykiwane nagłówki     │  │
│  └───────────────┬───────────────┘ └─────────────┬──────────────────┘  │
│                  │                               │                     │
│                  └───────────────┬───────────────┘                     │
│                                  ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 5. Telemetria i Konsola                                          │  │
│  │    • Bufor pierścieniowy w pamięci RAM (MetricsRegistry)         │  │
│  │    • Agregacja percentyli czasu odpowiedzi (P50, P90, P95, P99)  │  │
│  │    • Kolorowe logi terminala ANSI (TerminalLogger)               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Szczegóły Modułów
- **`mockpulse/server.py` (`MockPulseServer`):** Oparty na `http.server.ThreadingHTTPServer`. Przypisuje każde przychodzące połączenie do osobnego wątku roboczego. Dzięki temu sztucznie wprowadzone opóźnienie (np. 500 ms) zatrzymuje jedynie dany wątek, nie blokując innych jednoczesnych żądań.
- **`mockpulse/router.py` (`Router`):** Kompiluje ścieżki z parametrami (np. `/api/v1/users/{id}`) do nazwanych grup wyrażeń regularnych (`re.Pattern`). Ściśle realizuje standard RFC: odróżnia brak zasobu (`404 Not Found`) od nieobsługiwanej metody (`405 Method Not Allowed`), automatycznie dołączając nagłówek `Allow`.
- **`mockpulse/chaos.py` (`ChaosEngine`):** Realizuje losowe opóźnienia (`random.uniform`) oraz probabilistyczne wstrzykiwanie błędów oparte na próbie Bernoulliego (`random.random() < rate`).
- **`mockpulse/config.py` (`ConfigManager`):** Wczytuje i waliduje `routes.json`. Gdy plik zostanie zmodyfikowany na dysku, w ułamku mikrosekundy kompiluje nowy router i dokonuje atomowej zamiany referencji pod lekką blokadą (`threading.Lock`).
- **`mockpulse/metrics.py` (`MetricsRegistry`):** Wątkowo bezpieczny bufor pierścieniowy (`collections.deque(maxlen=2000)`). Rejestruje czasy wykonania i liczy percentyle P50, P90, P95 i P99 na żądanie.
- **`mockpulse/logger.py` (`TerminalLogger`):** Wyświetla czytelne logi ANSI z kolorami metod HTTP (GET, POST itd.), kodami stanu, czasem trwania oraz oznaczeniami `[💥 FAULT INJECTED]`. Obsługuje standard `NO_COLOR`.

---

## 3. Szybki Start i Obsługa z Wiersza Poleceń

### Uruchomienie Serwera
```bash
# Domyślny start na 127.0.0.1:8080 z plikiem routes.json
python3 main.py

# Wskazanie własnego portu i pliku konfiguracyjnego
python3 main.py --port 9000 --config wlasne_trasy.json

# Wyłączenie automatycznego przeładowywania (tryb produkcyjny/benchmark)
python3 main.py --no-hot-reload

# Tryb cichy (wyłącza logowanie pojedynczych zapytań w konsoli)
python3 main.py --quiet
```

### Parametry CLI
| Flaga | Typ | Wartość domyślna | Opis |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `127.0.0.1` | Interfejs sieciowy do nasłuchiwania |
| `--port` | `int` | `8080` | Port TCP serwera |
| `--config` | `str` | `routes.json` | Ścieżka do pliku konfiguracyjnego tras |
| `--no-hot-reload` | flaga | `False` | Wyłącza automatyczne odświeżanie po edycji pliku |
| `--quiet` | flaga | `False` | Wycisza kolorowe logi żądań w konsoli |

---

## 4. Konfiguracja Tras (`routes.json`)

Trasy definiowane są w formacie JSON w pliku `routes.json`:

```json
{
  "routes": [
    {
      "method": "POST",
      "path": "/api/v1/payments/charge",
      "status_code": 200,
      "headers": {
        "Content-Type": "application/json"
      },
      "response": {
        "transaction_id": "txn_849201",
        "status": "succeeded"
      },
      "latency": {
        "delay_ms": 200,
        "jitter_min_ms": 150,
        "jitter_max_ms": 400
      },
      "fault": {
        "rate": 0.25,
        "status_code": 503,
        "headers": {
          "Retry-After": "3"
        },
        "response": {
          "error": "UpstreamGatewayTimeout",
          "message": "Bramka płatności nie odpowiedziała na czas."
        }
      }
    }
  ]
}
```

### Opcje Konfiguracyjne
1. **`latency.delay_ms`:** Stałe opóźnienie w milisekundach.
2. **`latency.jitter_min_ms` i `jitter_max_ms`:** Przedział losowego opóźnienia symulujący zmienny stan sieci WAN.
3. **`fault.rate`:** Prawdopodobieństwo wystąpienia błędu od `0.0` (0%) do `1.0` (100%).
4. **`fault.status_code`:** Zwracany kod statusu HTTP w przypadku błędu (np. `500`, `503`, `429`).
5. **`fault.headers`:** Słownik nagłówków dołączanych do odpowiedzi w przypadku awarii (np. `Retry-After`).
6. **Enterpolacja parametrów ścieżki:** Zmienna `{id}` wewnątrz ciągów tekstowych obiektu `response` jest dynamicznie zastępowana wartością przechwyconą z adresu URL.

---

## 5. Weryfikacja i Testowanie

### Uruchomienie Testów Jednostkowych
```bash
python3 -m unittest discover tests -v
```
Wszystkie 18 testów wykonuje się w około **60 milisekund** bez konieczności otwierania gniazd sieciowych i bez zewnętrznych bibliotek testowych.

### Testowanie w VS Code
Otwórz plik [test_scenarios.http](test_scenarios.http) w VS Code z zainstalowanym rozszerzeniem **REST Client** i klikaj **Send Request** nad wybranymi scenariuszami.

### Wbudowane Punkty Końcowe Telemetrii i Szpieg Testów (Spy)
- **`GET /_mockpulse/metrics`:** Zwraca statystyki na żywo: percentyle czasu odpowiedzi (P50, P90, P95, P99), czas działania serwera (uptime), liczbę wywołanych awarii oraz rozkład kodów odpowiedzi HTTP.
- **`GET /_mockpulse/routes`:** Zwraca pełną listę zarejestrowanych tras wraz ze statusem wstrzykiwania opóźnień i błędów.
- **`GET /_mockpulse/history`:** Zwraca chronologiczną historię przechwyconych żądań (metoda, ścieżka, nagłówki, treść) do asercji w testach integracyjnych (Pytest, Jest, Cypress).
- **`DELETE /_mockpulse/history`:** Czyści bufor historii żądań pomiędzy zestawami testów.
- **Uniwersalna obsługa CORS:** Automatycznie odpowiada na zapytania preflight `OPTIONS` kodem `204 No Content` i nagłówkami `Access-Control-Allow-*`.

---

## 6. Kluczowe Argumenty na Rozmowę Rekrutacyjną (Staff / Senior)

1. **Dlaczego Biblioteka Standardowa zamiast FastAPI / Flask?**  
   *Użycie gotowego frameworka jest proste, ale zbudowanie własnego routera, parsowania protokołu HTTP, obsługi gniazd TCP i pełnej zgodności z RFC 405 dowodzi gruntownego zrozumienia działania sieci i systemów pod spodem wysokopoziomowych bibliotek.*
2. **Model Wielowątkowy (Thread-per-Request) a Pętla Zdarzeń (Asyncio) w Testach Chaosu:**  
   *W architekturze asynchronicznej blokujące wywołanie `time.sleep` wstrzymuje całą pętlę zdarzeń, chyba że zostanie opakowane w mechanizmy asynchroniczne. W architekturze opartej na `ThreadingHTTPServer` sztuczne opóźnienie usypia wyłącznie wątek danego klienta na poziomie jądra systemu, nie wpływając na pozostałe żądania.*
3. **Atomowa Zamiana Referencji przy Hot-Reload:**  
   *Sprawdzanie `os.stat(mtime)` na poziomie pamięci podręcznej VFS trwa ułamek mikrosekundy. W przypadku wykrycia zmian plik jest kompilowany w tle do nowej instancji routera, a następnie wskaźnik jest atomowo podmieniany pod lekką blokadą, co zapobiega przerwaniu obsługi trwających zapytań.*
