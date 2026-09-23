# 📘 MockPulse: Comprehensive Engineering & Usage Guide (English)

> **Zero-Dependency Local API Mocking & Chaos Fault Injection Engine**  
> Designed for microservices resilience testing, local prototyping, and technical interview demonstrations.

---

## 1. Project Overview & Motivation

When engineering microservices, client libraries, or frontend SPAs, applications inevitably depend on external 3rd-party APIs (e.g., Stripe, Twilio, Salesforce, AWS). 

### The Engineering Challenge
Testing edge cases against staging environments is notoriously difficult:
- **Flaky Networks:** Simulating a transient `503 Service Unavailable` or `429 Too Many Requests` is rarely supported by vendor sandboxes.
- **Variable Latency:** Testing how circuit breakers or UI loaders behave under 400ms–800ms network jitter requires manual throttling or expensive proxy proxies.
- **Tooling Overhead:** Existing tools (WireMock, Prism, Docker-based mock servers) demand heavy JVM runtimes, Node.js installations, or complex container networks.

### The MockPulse Solution
MockPulse runs on **pure Python 3 standard libraries** (`http.server`, `threading`, `json`, `re`, `time`, `random`). It provides:
1. Sub-15ms cold start with ~18MB memory footprint.
2. Declarative route mapping via `routes.json`.
3. In-process probabilistic fault injection (Chaos Engineering).
4. Millisecond-accurate latency jitter simulation.
5. In-memory thread-safe P50, P90, P95, P99 telemetry.
6. Zero-downtime hot-reloading via filesystem VFS metadata monitoring.

---

## 2. System Architecture & Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Client / HTTP Consumer                          │
│               (VS Code REST Client / curl / Pytest)                    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP/1.1 TCP :8080
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ MockPulse Server Runtime                                               │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 1. Transport Layer (ThreadingHTTPServer)                         │  │
│  │    • Multi-threaded daemon listener                              │  │
│  │    • Isolated worker thread per connection                       │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
│                                  │                                     │
│                                  ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 2. Pipeline Dispatcher (MockPulseRequestHandler)                 │  │
│  │    • Content-Length & Body extraction                            │  │
│  │    • Header & query parameter normalization                      │  │
│  │    • Hot-reload trigger (os.stat mtime check)                    │  │
│  └───────────────┬───────────────────────────────┬──────────────────┘  │
│                  │                               │                     │
│                  ▼                               ▼                     │
│  ┌───────────────────────────────┐ ┌────────────────────────────────┐  │
│  │ 3. Router & Match Engine      │ │ 4. Chaos & Fault Injector      │  │
│  │    • Compiled Regex cache     │ │    • Latency Jitter engine     │  │
│  │    • Parameter extraction     │ │    • Probabilistic error rate  │  │
│  │    • RFC 404 vs 405 resolver  │ │    • Injected status & headers │  │
│  └───────────────┬───────────────┘ └─────────────┬──────────────────┘  │
│                  │                               │                     │
│                  └───────────────┬───────────────┘                     │
│                                  ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 5. Telemetry & Console Monitor                                   │  │
│  │    • Thread-safe In-Memory Ring Buffer (MetricsRegistry)         │  │
│  │    • Real-time percentile calculation (P50, P90, P95, P99)       │  │
│  │    • Colorized ANSI terminal logging (TerminalLogger)            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown
- **`mockpulse/server.py` (`MockPulseServer`):** Wraps `http.server.ThreadingHTTPServer`. Spawns a dedicated OS thread per incoming request, preventing blocked event loops during latency simulation.
- **`mockpulse/router.py` (`Router`):** Compiles route path templates (e.g. `/api/v1/users/{id}`) into named regex capture groups. Accurately distinguishes between `404 Not Found` and `405 Method Not Allowed` (returning the standard `Allow` header).
- **`mockpulse/chaos.py` (`ChaosEngine`):** Executes latency jitter (`random.uniform(min, max)`) and probabilistic fault injection (Bernoulli trial: `random.random() < rate`).
- **`mockpulse/config.py` (`ConfigManager`):** Parses `routes.json`, binds handlers, and provides thread-safe atomic pointer swaps when configuration file changes are detected.
- **`mockpulse/metrics.py` (`MetricsRegistry`):** High-throughput thread-safe ring buffer (`collections.deque(maxlen=2000)`) tracking transaction durations and computing latency percentiles.
- **`mockpulse/logger.py` (`TerminalLogger`):** ANSI-escaped terminal logger with support for NO_COLOR compliance, color-coded HTTP verbs, response time tags, and chaos alerts.

---

## 3. Quickstart & Command Line Usage

### Starting the Server
```bash
# Default: binds to 127.0.0.1:8080 with routes.json
python3 main.py

# Custom port and configuration file
python3 main.py --port 9000 --config my_custom_routes.json

# Disable hot-reloading (production/benchmark mode)
python3 main.py --no-hot-reload

# Quiet mode (suppresses per-request console logs)
python3 main.py --quiet
```

### CLI Arguments Reference
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `127.0.0.1` | Network interface to bind the socket to |
| `--port` | `int` | `8080` | TCP port to listen on |
| `--config` | `str` | `routes.json` | Path to declarative JSON routes file |
| `--no-hot-reload` | flag | `False` | Disables filesystem watcher for config changes |
| `--quiet` | flag | `False` | Disables per-request ANSI console logging |

---

## 4. Configuring `routes.json`

MockPulse endpoints are defined declaratively in `routes.json`:

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
          "message": "Payment provider timed out. Retry after backoff."
        }
      }
    }
  ]
}
```

### Configuration Options
1. **`latency.delay_ms`:** Fixed delay in milliseconds.
2. **`latency.jitter_min_ms` & `jitter_max_ms`:** Uniform random range for variable network latency.
3. **`fault.rate`:** Probability of failure from `0.0` (0%) to `1.0` (100%).
4. **`fault.status_code`:** HTTP status code returned upon fault (e.g. `500`, `503`, `429`).
5. **`fault.headers`:** Key-value map of HTTP headers injected into the fault response.
6. **Path Parameter Interpolation:** Use `{id}` in strings inside `response` to dynamically reflect captured path parameters.

---

## 5. Verification & Testing

### Running Automated Unit Tests
```bash
python3 -m unittest discover tests -v
```
All 18 unit tests run in ~60ms without requiring network sockets or external testing packages.

### Testing with VS Code REST Client
Open [test_scenarios.http](test_scenarios.http) in VS Code and click **Send Request** above any scenario.

### Built-in Telemetry & Test Spy Endpoints
- **`GET /_mockpulse/metrics`:** Returns real-time latency percentiles (P50, P90, P95, P99), uptime, fault count, and HTTP status distribution.
- **`GET /_mockpulse/routes`:** Lists all loaded endpoints with their active chaos and latency configurations.
- **`GET /_mockpulse/history`:** Returns the chronological log of captured requests (method, path, headers, query params, body) for assertions in integration tests.
- **`DELETE /_mockpulse/history`:** Clears the request history buffer between test suites.
- **Universal CORS:** Automatically responds to `OPTIONS` preflight requests with `204 No Content` and `Access-Control-Allow-*` headers.

---

## 6. Staff / Senior Technical Interview Talking Points

1. **Why Standard Library?**  
   *Demonstrates low-level network protocol mastery. Anyone can call a third-party framework, but engineering HTTP parsing, socket handling, framing, and RFC 405 compliance highlights core software engineering competence.*
2. **Thread-per-Request vs Event Loop for Chaos Simulation:**  
   *In an async framework (`asyncio`/FastAPI), blocking delays stall event loops unless wrapped in asynchronous tasks. With `ThreadingHTTPServer`, simulated latency halts only the dedicated worker thread in kernel space, ensuring zero performance interference on concurrent requests.*
3. **Atomic Reference Swapping for Zero Downtime:**  
   *Hot-reloading inspects filesystem inode timestamps (`os.stat(mtime)`) in sub-microseconds. Changes trigger compilation into a fresh `Router` before an atomic swap under a light lock, preventing race conditions or half-initialized routing states.*
