# Contributing

Thank you for your interest in n0va. This document states **minimal style rules** that apply **only to the n0va library package** (the `n0va/` tree under the repository root). They do **not** apply to the dashboard, sample scripts, or other top-level code unless explicitly adopted there.

## Structure and placement

Do **not** use module top level for constants (e.g. `MAX_RETRIES = 3`), type aliases, top-level `def`, other loose bindings, top-level `if` / control flow for application behavior, or similar—**except** where Python syntax makes any other placement impossible. In those rare cases, keep the surface area minimal.

Group code by **domain** (clear responsibility boundaries) and keep implementation **under classes**—methods, nested types, and class attributes as appropriate—so that modules primarily define types and wiring, not free-floating procedures or globals.

Do **not** extract a **method** (or similar named helper) when it would be called from **only one** place **and** is neither covered by unit tests **nor** part of the library’s externally used surface. In that situation, keep the logic inline (e.g. inside the calling method or as a small local closure) unless a real reuse, test hook, or public API need appears later.

## Imports

There is **no** required import style. Rigid rules here tend to **increase the risk of circular imports**, so choose imports that keep the dependency graph healthy and readable.

**Optional:** when it helps readability, you may use **fully qualified** imports to make namespaces explicit (e.g. `import n0va.handler.router` and `n0va.handler.router.SomeClass`). Treat this as a local clarity choice, not an obligation.

Use `from ... import ...`, `import ... as ...`, and other selective forms whenever they suit the module—for example to break or avoid import cycles, to resolve name clashes, or to **re-export** names or submodules from `__init__.py` (and similar public-API aggregators). Keep selective imports scoped sensibly and document the reason if it is not obvious from context.
