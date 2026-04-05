/**
 * Gate JSON（API / gate_builder）とフォーム状態の相互変換。
 * ダッシュボードは TLS（SNI）入口のみ（平文 TCP の設定 UI はない）。
 * @see dashboard/gate_builder.py
 */

import i18n from "@/i18n/config";

export type LoadBalanceStrategy = "least_conn" | "round_robin";

export type UpstreamForm = {
  host: string;
  port: string;
  /** 上流が TLS のとき SNI（必須）。平文 TCP のときは空。 */
  tlsServerHostname: string;
  /** カンマ区切り ALPN（任意）。例: h2, http/1.1 */
  tlsAlpn: string;
};

/** HTTP/1.x 先頭リクエストに基づく上流の選び方（サーバーは上から順に評価） */
export type HttpPathMatchMode = "any" | "exact" | "prefix";

export type HttpDispatchRuleForm = {
  /** `upstreams` の 0 始まりインデックス */
  upstreamIndex: number;
  pathMode: HttpPathMatchMode;
  /** pathMode が exact / prefix のとき使用。先頭 / なしでも可（prefix は保存時に正規化） */
  path: string;
  /** カンマ区切り。空 = 全メソッド */
  methods: string;
};

export type HttpDispatchForm = {
  enabled: boolean;
  defaultUpstreamIndex: number;
  rules: HttpDispatchRuleForm[];
};

export type RouteForm = {
  /** TLS SNI: 入口のホスト名と同じ文字列（ルックアップキー）。 */
  routeKey: string;
  strategy: LoadBalanceStrategy;
  upstreams: UpstreamForm[];
  /** null = TCP 透過（既定）。有効時は先頭 HTTP リクエストで上流を選択。 */
  httpDispatch: HttpDispatchForm | null;
};

export type SniRow = {
  hostname: string;
  cert_file: string;
  key_file: string;
};

export type GateFormModel = {
  listen: {
    host: string;
    port: string;
    backlog: string;
    read_limit: string;
  };
  sniRows: SniRow[];
  routes: RouteForm[];
};

const DEFAULT_READ_LIMIT = 256 * 1024;

export function defaultGateFormModel(): GateFormModel {
  return {
    listen: {
      host: "127.0.0.1",
      port: "8443",
      backlog: "128",
      read_limit: String(DEFAULT_READ_LIMIT),
    },
    sniRows: [{ hostname: "localhost", cert_file: "", key_file: "" }],
    routes: [
      {
        routeKey: "localhost",
        strategy: "least_conn",
        upstreams: [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }],
        httpDispatch: null,
      },
    ],
  };
}

function num(v: unknown, fallback: number): number {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function parseUpstream(raw: unknown): UpstreamForm {
  if (!raw || typeof raw !== "object") {
    return { host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" };
  }
  const o = raw as Record<string, unknown>;
  const tls = o.tls;
  let tlsServerHostname = "";
  let tlsAlpn = "";
  if (tls && typeof tls === "object") {
    const t = tls as Record<string, unknown>;
    tlsServerHostname = str(t.server_hostname);
    const alpn = t.alpn;
    if (Array.isArray(alpn)) {
      tlsAlpn = alpn.map((x) => String(x)).join(", ");
    }
  }
  return {
    host: str(o.host) || "127.0.0.1",
    port: String(num(o.port, 8080)),
    tlsServerHostname,
    tlsAlpn,
  };
}

function parseStrategy(s: unknown): LoadBalanceStrategy {
  const k = String(s || "least_conn").toLowerCase();
  return k === "round_robin" ? "round_robin" : "least_conn";
}

function parseHttpDispatchFromRoute(
  r: Record<string, unknown>,
  upstreamCount: number,
): HttpDispatchForm | null {
  const hd = r.http_dispatch;
  if (!hd || typeof hd !== "object") return null;
  const h = hd as Record<string, unknown>;
  const maxIdx = Math.max(0, upstreamCount - 1);
  const defaultUpstreamIndex = Math.min(
    Math.max(0, Math.floor(Number(h.default_upstream_index ?? 0))),
    maxIdx,
  );
  const rulesRaw = h.rules;
  const rules: HttpDispatchRuleForm[] = [];
  if (Array.isArray(rulesRaw)) {
    for (const raw of rulesRaw) {
      if (!raw || typeof raw !== "object") continue;
      const o = raw as Record<string, unknown>;
      const upstreamIndex = Math.min(
        Math.max(0, Math.floor(Number(o.upstream_index ?? 0))),
        maxIdx,
      );
      const methodsArr = o.methods;
      let methods = "";
      if (Array.isArray(methodsArr)) {
        methods = methodsArr.map((x) => String(x).toUpperCase()).join(", ");
      }
      const pe = o.path_exact != null ? String(o.path_exact) : null;
      const pp = o.path_prefix != null ? String(o.path_prefix) : null;
      let pathMode: HttpPathMatchMode = "any";
      let path = "";
      if (pe != null && pe.length > 0) {
        pathMode = "exact";
        path = pe;
      } else if (pp != null && String(pp).length > 0) {
        pathMode = "prefix";
        path = String(pp);
      }
      rules.push({ upstreamIndex, pathMode, path, methods });
    }
  }
  return {
    enabled: true,
    defaultUpstreamIndex,
    rules,
  };
}

/** 上流の数が変わったあと、HTTP 振り分けのインデックスを範囲内に収める */
export function clampHttpDispatchIndices(route: RouteForm): RouteForm {
  if (!route.httpDispatch?.enabled) return route;
  const n = route.upstreams.length;
  if (n === 0) {
    return {
      ...route,
      httpDispatch: { enabled: true, defaultUpstreamIndex: 0, rules: [] },
    };
  }
  const max = n - 1;
  return {
    ...route,
    httpDispatch: {
      ...route.httpDispatch,
      defaultUpstreamIndex: Math.min(Math.max(0, route.httpDispatch.defaultUpstreamIndex), max),
      rules: route.httpDispatch.rules.map((ru) => ({
        ...ru,
        upstreamIndex: Math.min(Math.max(0, ru.upstreamIndex), max),
      })),
    },
  };
}

/**
 * 平文 TCP の保存済み設定を TLS フォームへ移行する（ダッシュボードは TLS のみのため）。
 */
function migratePlainConfigToTlsForm(
  defaultRoute: string,
  routesRaw: Record<string, unknown>,
): { sniRows: SniRow[]; routes: RouteForm[] } {
  const dr = defaultRoute.trim() || "*";
  let routes: RouteForm[] = [];
  for (const [key, rv] of Object.entries(routesRaw)) {
    if (!rv || typeof rv !== "object") continue;
    const r = rv as Record<string, unknown>;
    const ups = r.upstreams;
    const upstreams: UpstreamForm[] = Array.isArray(ups)
      ? ups.map(parseUpstream)
      : [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }];
    let routeKey = key;
    if (key === "*" || key === dr) {
      routeKey = dr !== "*" && dr !== "" ? dr : "localhost";
    }
    routes.push({
      routeKey,
      strategy: parseStrategy(r.strategy),
      upstreams: upstreams.length > 0 ? upstreams : [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }],
      httpDispatch: null,
    });
  }
  if (routes.length === 0) {
    const h = dr !== "*" && dr !== "" ? dr : "localhost";
    routes.push({
      routeKey: h,
      strategy: "least_conn",
      upstreams: [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }],
      httpDispatch: null,
    });
  }
  const byKey = new Map<string, RouteForm>();
  for (const r of routes) {
    const k = r.routeKey.trim();
    if (!k) continue;
    if (!byKey.has(k)) byKey.set(k, r);
  }
  routes = [...byKey.values()];
  const hosts = [...new Set(routes.map((x) => x.routeKey.trim()).filter(Boolean))];
  const sniRows: SniRow[] = hosts.map((hostname) => ({
    hostname,
    cert_file: "",
    key_file: "",
  }));
  return { sniRows, routes };
}

/**
 * API から返る config オブジェクトをフォームに読み込む。
 */
export function gateConfigToForm(config: Record<string, unknown>): GateFormModel {
  const listenRaw = config.listen;
  const l =
    listenRaw && typeof listenRaw === "object"
      ? (listenRaw as Record<string, unknown>)
      : {};
  const entranceRaw = config.entrance;
  const ent =
    entranceRaw && typeof entranceRaw === "object"
      ? (entranceRaw as Record<string, unknown>)
      : {};
  const et = String(ent.type || "plain").toLowerCase();

  let sniRows: SniRow[] = [{ hostname: "localhost", cert_file: "", key_file: "" }];
  let routes: RouteForm[] = [];

  const routesRaw =
    config.routes && typeof config.routes === "object" && !Array.isArray(config.routes)
      ? (config.routes as Record<string, unknown>)
      : {};

  if (et === "tls_sni") {
    const snis = ent.snis;
    if (Array.isArray(snis) && snis.length > 0) {
      sniRows = snis.map((row) => {
        const r = row && typeof row === "object" ? (row as Record<string, unknown>) : {};
        return {
          hostname: str(r.hostname) || "localhost",
          cert_file: str(r.cert_file),
          key_file: str(r.key_file),
        };
      });
    }
    for (const [key, rv] of Object.entries(routesRaw)) {
      if (!rv || typeof rv !== "object") continue;
      const r = rv as Record<string, unknown>;
      const ups = r.upstreams;
      const upstreams: UpstreamForm[] = Array.isArray(ups)
        ? ups.map(parseUpstream)
        : [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }];
      const uFinal = upstreams.length > 0 ? upstreams : [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }];
      routes.push({
        routeKey: key,
        strategy: parseStrategy(r.strategy),
        upstreams: uFinal,
        httpDispatch: parseHttpDispatchFromRoute(r, uFinal.length),
      });
    }
    if (routes.length === 0) {
      routes.push({
        routeKey: sniRows[0]?.hostname.trim() || "localhost",
        strategy: "least_conn",
        upstreams: [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }],
        httpDispatch: null,
      });
    }
  } else {
    const plainDr = str(ent.default_route) || "*";
    const migrated = migratePlainConfigToTlsForm(plainDr, routesRaw);
    sniRows = migrated.sniRows;
    routes = migrated.routes;
  }

  return {
    listen: {
      host: str(l.host) || "127.0.0.1",
      port: String(num(l.port, 8443)),
      backlog: String(num(l.backlog, 128)),
      read_limit: String(num(l.read_limit, DEFAULT_READ_LIMIT)),
    },
    sniRows,
    routes,
  };
}

function upstreamToJson(u: UpstreamForm): Record<string, unknown> {
  const host = u.host.trim() || "127.0.0.1";
  const port = Math.max(1, Math.min(65535, Math.floor(Number(u.port) || 8080)));
  const sni = u.tlsServerHostname.trim();
  if (!sni) {
    return { host, port };
  }
  const alpnPart = u.tlsAlpn
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const tls: Record<string, unknown> = { server_hostname: sni };
  if (alpnPart.length > 0) {
    tls.alpn = alpnPart;
  }
  return { host, port, tls };
}

/**
 * フォームから API 用 config を生成。検証エラー時は例外にメッセージを載せる。
 */
export function formToGateConfig(model: GateFormModel): Record<string, unknown> {
  const port = Math.floor(Number(model.listen.port));
  if (!Number.isFinite(port) || port < 1 || port > 65535) {
    throw new Error(i18n.t("errors.gate.listenPort"));
  }
  const backlog = Math.floor(Number(model.listen.backlog));
  const readLimit = Math.floor(Number(model.listen.read_limit));
  if (!Number.isFinite(backlog) || backlog < 1) {
    throw new Error(i18n.t("errors.gate.backlog"));
  }
  if (!Number.isFinite(readLimit) || readLimit < 1024) {
    throw new Error(i18n.t("errors.gate.readLimit"));
  }

  const listen = {
    host: model.listen.host.trim() || "127.0.0.1",
    port,
    backlog,
    read_limit: readLimit,
  };

  const snis = model.sniRows
    .map((row) => ({
      hostname: row.hostname.trim(),
      cert_file: row.cert_file.trim(),
      key_file: row.key_file.trim(),
    }))
    .filter((r) => r.hostname);
  if (snis.length === 0) {
    throw new Error(i18n.t("errors.gate.tlsNoHost"));
  }
  for (const r of snis) {
    if (!r.cert_file || !r.key_file) {
      throw new Error(
        i18n.t("errors.gate.tlsMissingPaths", {
          host: r.hostname || i18n.t("errors.gate.entryLabel"),
        }),
      );
    }
  }
  const entrance: Record<string, unknown> = { type: "tls_sni", snis };

  if (model.routes.length === 0) {
    throw new Error(i18n.t("errors.gate.noRoutes"));
  }

  const seen = new Set<string>();
  for (const route of model.routes) {
    const key = route.routeKey.trim();
    if (!key) {
      throw new Error(i18n.t("errors.gate.routeKey"));
    }
    if (seen.has(key)) {
      throw new Error(i18n.t("errors.gate.duplicateRouteKey", { key }));
    }
    seen.add(key);
  }

  const sniHostSet = new Set(snis.map((s) => s.hostname));
  for (const h of sniHostSet) {
    if (!model.routes.some((r) => r.routeKey.trim() === h)) {
      throw new Error(i18n.t("errors.gate.sniMissingRoute", { host: h }));
    }
  }

  const routes: Record<string, unknown> = {};
  for (const route of model.routes) {
    const key = route.routeKey.trim();
    if (!sniHostSet.has(key)) {
      throw new Error(i18n.t("errors.gate.routeKeyNotSni", { key }));
    }
    if (route.upstreams.length === 0) {
      throw new Error(i18n.t("errors.gate.routeUpstream", { key }));
    }
    const nUp = route.upstreams.length;
    const base: Record<string, unknown> = {
      upstreams: route.upstreams.map(upstreamToJson),
      strategy: route.strategy,
    };
    if (route.httpDispatch?.enabled) {
      const d = route.httpDispatch.defaultUpstreamIndex;
      if (!Number.isFinite(d) || d < 0 || d >= nUp) {
        throw new Error(i18n.t("errors.gate.httpDefaultUpstream", { key }));
      }
      for (let i = 0; i < route.httpDispatch.rules.length; i++) {
        const rule = route.httpDispatch.rules[i];
        if (!Number.isFinite(rule.upstreamIndex) || rule.upstreamIndex < 0 || rule.upstreamIndex >= nUp) {
          throw new Error(i18n.t("errors.gate.httpRuleUpstream", { key, n: i + 1 }));
        }
        if ((rule.pathMode === "exact" || rule.pathMode === "prefix") && !rule.path.trim()) {
          throw new Error(i18n.t("errors.gate.httpRulePath", { key, n: i + 1 }));
        }
      }
      const rules: Record<string, unknown>[] = route.httpDispatch.rules.map((rule) => {
        const o: Record<string, unknown> = { upstream_index: rule.upstreamIndex };
        const meth = rule.methods
          .split(",")
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean);
        if (meth.length > 0) {
          o.methods = meth;
        }
        if (rule.pathMode === "exact") {
          o.path_exact = rule.path.trim();
        } else if (rule.pathMode === "prefix") {
          let p = rule.path.trim();
          if (p && !p.startsWith("/")) {
            p = `/${p}`;
          }
          o.path_prefix = p;
        }
        return o;
      });
      base.http_dispatch = {
        default_upstream_index: route.httpDispatch.defaultUpstreamIndex,
        rules,
      };
    }
    routes[key] = base;
  }

  return {
    listen,
    entrance,
    routes,
  };
}

export function validateForm(model: GateFormModel): string | null {
  try {
    formToGateConfig(model);
    return null;
  } catch (e) {
    return e instanceof Error ? e.message : String(e);
  }
}
