# Programmable HTTP server and Gate (n0va)

This document describes the **programmable surfaces** in n0va: the embedded **HTTP application server** (`n0va.Service`) and the **Gate** (TCP/TLS proxy with optional HTTP-aware routing). It is aimed at contributors and advanced users who build tooling on top of the library.

For installation, quick starts, and the optional dashboard, see the [repository README](../README.md).

---

## 1. Two complementary layers

| Layer | Primary types | Role |
|-------|----------------|------|
| **HTTP app server** | `n0va.Service`, `RequestContext`, `HttpResponse` | Run an asyncio HTTP/1.1 application: routes, static files (dev-oriented), WebSockets. |
| **Gate** | `GateService`, `HttpRoutingGateService`, `GateConfig`, `Route` | Terminate or forward TCP/TLS; observe or rewrite **raw bytes** (or full HTTP/1.x messages in HTTP dispatch mode). |

You typically **compose** them: e.g. run backends with `Service` on localhost and place `HttpRoutingGateService` in front to split traffic by path or hostname.

---

## 2. HTTP application server (`n0va.Service`)

`Service` extends the internal `n0va.handler.http.server` (async TCP accept + HTTP/1.1 handling). It is **not** a Gate; it is an **origin server** for your app logic.

### 2.1 Lifecycle and process model

- **`Start()`** runs the server via `asyncio.run`, unless the [supervisor](../n0va/core/supervisor.py) spawns a child process (default). Disable supervision with `N0VA_NO_SUPERVISE=1` or `Start(supervised=False)`.
- **`install_stop_signal_handlers`** (constructor): set to `False` if you run multiple `Service` instances in one process.

### 2.2 Routing API

- **`onGet(path)` / `onPost(path)`** — register async handlers for a single method.
- **`route(path, methods=(...))`** — register one handler for several methods (excluding `WEBSOCKET`).
- **`onWebsocket(path)`** — WebSocket handlers receive `(WebSocketSession, RequestContext)`.

Handlers receive a **`RequestContext`** and return **`HttpResponse`** (see `n0va.handler.context`).

### 2.3 Static files (development)

`root_path` is scanned into **`OnMemoryFiles`**; files are served with mtime-based reload. Options **`dev_static_cache_control`** and **`dev_static_rescan_interval`** control caching headers and how often missing paths trigger a directory rescan. This path is **intentionally simple** — not a production CDN replacement.

---

## 3. Gate: mental model

The Gate is an **asyncio `asyncio.Server`** that accepts client connections and, for each route, opens **one or more upstreams** (`Upstream`: host, port, optional TLS settings).

- **`GateConfig`** ties together **`ListenConfig`**, an **entrance** (how the client connects), and a **`routes`** map from string keys to **`Route`** instances.
- **`GateService`** implements transparent proxying with **bidirectional hooks** on each `Route`.
- **`HttpRoutingGateService`** subclasses `GateService` and overrides connection handling for routes that use **`HttpDispatchRoute`**, so HTTP/1.x requests can be routed to **different upstreams** while reusing connections where safe.

---

## 4. Entrances (client-facing)

### 4.1 `EntrancePlain`

Plain TCP. **`default_route`** names the key in `GateConfig.routes` used for every connection (commonly `"*"`).

### 4.2 `EntranceTlsSni`

TLS with **OpenSSL SNI**: each hostname maps to an **`ssl.SSLContext`**. After handshake, the route key is taken from the context’s **`DomainName`** attribute (set during `GateConfig.validate()`).

### 4.3 `EntranceTlsManual`

The client hello is parsed manually (`AsyncManualSslStream`). Use when you need control comparable to custom handshake sequencing. The base `GateService` contains specialized branches for picking upstream TLS vs plain and for ALPN negotiation with the upstream.

The first client→upstream hook may receive the **raw ClientHello** as `buf` when the client is not completing a normal TLS handshake with the gate (`isTryingHandshake` is false); the buffer can then be forwarded upstream before the entrance stream is wrapped as a plain `AsyncStream` for relay.

**Compatibility with HTTP dispatch:** `EntranceTlsManual` connections **never** call `HttpRoutingGateService._proxy_with_route`. They go straight to **`_opengate`** after setup. Therefore **`HttpDispatchRoute` does not apply**: you get **TCP chunk–level** hooks only, same as a plain `Route`. Use **`EntrancePlain`** or **`EntranceTlsSni`** when you need per-request HTTP routing and full-message hooks from `HttpDispatchRoute`.

---

## 5. `Route`: programmable hooks

Subclasses of **`Route`** implement optional **async** methods:

```text
on_entrance_to_destination(buf, entrance_connection, destination_connection) -> bytes | None
on_destination_to_entrance(buf, destination_connection, entrance_connection) -> bytes | None
```

Default behavior is the identity: return `buf` unchanged.

### 5.1 Semantics of `None`

- Returning **`None`** means: **do not send** the corresponding data on the **outbound** side for that callback invocation (client→upstream or upstream→client).
- Combined with EOF (`Recv()` returning `b""`), you can implement early teardown by closing connections in your hook (the core handlers also close on errors).

### 5.2 What is `buf`? — depends on the service mode

This distinction is **critical**:

| Mode | Service class | `buf` meaning |
|------|----------------|---------------|
| **TCP streaming** | `GateService` (non-dispatch routes) | **One read chunk** from the socket — **not** aligned to HTTP messages. A single HTTP request may span many callbacks. |
| **HTTP dispatch** | `HttpRoutingGateService` + `HttpDispatchRoute` | **One complete HTTP/1.x message** (request or response), including headers and body, up to configured size limits — see §6. |

For **`EntranceTlsManual`** in the non-handshake branch, the first client→upstream call may receive the **raw ClientHello buffer** (see `GateService._on_tls_manual_client`). After that, chunks are ordinary TCP reads on the upgraded stream.

### 5.3 Connection objects

The `entrance_connection` and `destination_connection` arguments are **`AsyncStream`** (or compatible) instances. You can inspect or use them for advanced scenarios (e.g. correlating logs). **Prefer not** to read/write them outside the hook contract unless you fully understand half-close and buffer ordering.

---

## 6. HTTP-aware routing: `HttpDispatchRoute` and `HttpRoutingGateService`

### 6.1 Why this mode exists

With **keep-alive**, one client TCP connection carries **many** HTTP requests. A naive proxy that picks an upstream only from the **first** request would mis-route later requests. `HttpRoutingGateService` parses **each** request, selects an upstream, and uses **`UpstreamConnectionPool`** so connections are reused **per upstream** safely (one in-flight request per borrowed connection, as documented on the pool).

**Entrance compatibility:** HTTP dispatch is used only when the accept handler reaches **`_proxy_with_route`** — i.e. **`EntrancePlain`** or **`EntranceTlsSni`**. It is **not** used for **`EntranceTlsManual`** (see §4.3).

### 6.2 Declarative rules: `HttpDispatchRule`

Rules are evaluated **in order**; the **first match** selects `upstream_index`. Each rule can constrain:

- **HTTP methods** (optional set; uppercased internally),
- **`path_exact`** or **`path_prefix`** (mutually exclusive),
- or **no path constraint** (method-only or unconditional).

If nothing matches, **`default_upstream_index`** is used.

### 6.3 Hook granularity in HTTP dispatch mode

For `HttpDispatchRoute`, **`on_entrance_to_destination`** and **`on_destination_to_entrance`** run **once per HTTP message** (full request / full response), **immediately before** sending to upstream or client. This is the right place for:

- structured logging or metrics,
- header or body rewrites on whole messages,
- selective blocking (return `None` to suppress forwarding — use with care).

Size limits **`max_header_bytes`** and **`max_body_bytes`** bound parsing; exceeding them closes the client connection.

### 6.4 TLS and HTTP/1.1

For TLS frontends, **`HttpRoutingGateService`** sets ALPN to **`http/1.1`** in the SNI callback so clients do not negotiate HTTP/2 and then send frames the Gate cannot interpret as HTTP/1 text (which would otherwise manifest as empty responses in browsers).

### 6.5 Resilience

The dispatch loop can **retry once** on certain **transient** upstream errors (`UpstreamConnectionPool.transient_error`). Unhealthy pooled connections are discarded.

---

## 7. Load balancing

Each **`Route`** has a **`LoadBalanceStrategy`**:

- **`LEAST_CONN`** — prefer the upstream with the smallest in-flight count (as tracked by the service).
- **`ROUND_ROBIN`** — cyclic selection.

`HttpDispatchRoute` participates in the same accounting for the **selected** upstream index per request.

---

## 8. Hot reload: `apply_routing`

**`await gate.apply_routing(new_config)`** replaces `GateConfig` atomically under a lock. **Existing** connections keep their old behavior; **new** accepts use the new configuration. `HttpRoutingGateService` also resets its **upstream connection pool** when routing changes.

Use **`config_generation`** if you need to observe updates in long-lived tasks.

---

## 9. Stopping the Gate

- **`await stop()`** — closes the listening socket and aborts accepted clients so shutdown does not hang on idle keep-alive reads.
- **`request_stop()`** — schedules `stop()` from another thread (e.g. signal handler).

---

## 10. Building configuration in code

The dashboard builds **`GateConfig`** from JSON-like dicts via **`dashboard.gate_builder.gate_config_from_dict`**. That module is the **authoritative mapping** from declarative config to:

- `ListenConfig`, `EntrancePlain`, `EntranceTlsSni`,
- plain **`Route`** vs **`HttpDispatchRoute`** (`http_dispatch` block with `rules`, limits, etc.).

For programmatic use without the dashboard, construct **`GateConfig`** and route objects directly from **`n0va.core.gate`**.

---

## 11. Design boundaries and limitations

- **HTTP/2 / QUIC:** The HTTP dispatch path is **HTTP/1.x** oriented. Do not expect HTTP/2 frame parsing or routing here.
- **Production edge:** n0va targets **local dev, tooling, and controlled research** — not a replacement for hardened edge proxies or CDNs (see README).
- **Chunk hooks on `GateService`:** Treat payload boundaries as **transport-level**. For HTTP-level safety, use **`HttpDispatchRoute`** or terminate HTTP inside your own service.

---

## 12. References in this repository

| Topic | Location |
|-------|----------|
| Gate config & `Route` hooks | `n0va/core/gate/config.py` |
| TCP/TLS proxy & `EntranceTlsManual` | `n0va/core/gate/service.py` |
| HTTP dispatch, pooling, ALPN | `n0va/core/gate/http_dispatch.py` |
| Upstream pool | `n0va/core/gate/upstream_pool.py` |
| JSON → `GateConfig` | `dashboard/gate_builder.py` |
| Integration tests (plain + dispatch) | `tests/test_integration_gate.py` |
| Public re-exports | `n0va/core/gate/__init__.py` |

---

## 13. Ethics and authorization

Gate features can terminate TLS and expose traffic to your code. That capability is **dual-use**. Use n0va only on systems and networks you **own** or are **explicitly authorized** to test. See the **Security research** section in the [README](../README.md).
