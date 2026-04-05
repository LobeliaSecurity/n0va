# n0va

**n0va** is a small **asyncio** toolkit for Python 3.10+: a lightweight **HTTP/1.1** server, a **TCP proxy (“Gate”)** you can observe and extend, and an optional **dashboard** for local ops. Built for prototypes, labs, and dev workflows—not a replacement for large production frontends or CDNs.

**License:** [MIT](LICENSE)

---

## Why n0va?

- **Gate — inspect traffic without giving up transparency.** Forward TCP end-to-end, terminate TLS when you need to, route by SNI or HTTP, load-balance upstreams, and hook **bidirectional streams** to log or reshape bytes—useful for debugging, security research, and custom routing.
- **Simple HTTP & WebSocket surface.** Decorate routes, serve static files for **local dev**, optional TLS—enough to ship a demo or internal tool quickly.
- **Optional dashboard.** Manage Gate configs, certificates, and a few helper utilities from the browser when you want a UI instead of only code.

---

## Install

```bash
pip install git+https://github.com/LobeliaSecurity/n0va.git
```

Requires **Python ≥ 3.10** and `pyOpenSSL` (see `setup.py`).

---

## Quick start (HTTP)

```python
import pathlib
import n0va


class Service(n0va.Service):
    def __init__(self, host, port, root_path):
        super().__init__(host=host, port=port, root_path=root_path)


service = Service(
    host="127.0.0.1",
    port=8080,
    root_path=pathlib.Path("./documents").resolve().as_posix(),
)


@service.onGet("/hello")
async def hello(ctx: n0va.RequestContext) -> n0va.HttpResponse:
    return n0va.HttpResponse(status=200, body=b"ok", content_type=b"text/plain")


service.Start()
```

More patterns (WebSocket, routing, Gate) live under **`example/`** and **`gate_sample.py`**.

---

## Dashboard (optional)

Build the frontend, then from the repo root run `python dashboard/run.py`. By default the app listens on **`127.0.0.1:8765`** and serves REST under **`/api/v1/`**. Use `N0VA_DASHBOARD_DATA` to change where persistent data is rooted.

---

## Environment hints

| Variable | Purpose |
| -------- | ------- |
| `N0VA_NO_SUPERVISE` | Disable parent/child supervision; run as a single process |
| `N0VA_DASHBOARD_DATA` | Base path for dashboard data (see dashboard docs / `.n0va/` layout) |
| `N0VA_GATE_VERBOSE` | Extra logging for Gate samples (e.g. `1`) |

---

## Repository layout

| Path | Role |
| ---- | ---- |
| `n0va/` | Core library |
| `dashboard/` | Web UI + API |
| `example/` | App examples |

Built-in static file serving is meant for **development**; use your own stack for heavy production traffic.
