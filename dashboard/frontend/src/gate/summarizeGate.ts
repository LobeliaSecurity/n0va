import type { TFunction } from "i18next";

import type { GateDto } from "@/api";

/** Gate 設定から一覧・概要用の短い表示文字列を作る */
export function summarizeGate(
  g: GateDto,
  t: TFunction,
): { listen: string; entrance: string } {
  const cfg = g.config;
  const listen = cfg.listen;
  let listenStr = "—";
  if (listen && typeof listen === "object") {
    const l = listen as Record<string, unknown>;
    const h = typeof l.host === "string" ? l.host : "?";
    const p = l.port;
    listenStr = `${h}:${p ?? "?"}`;
  }
  const ent = cfg.entrance;
  let entrance = t("gates.unknown");
  if (ent && typeof ent === "object") {
    const typ = String((ent as Record<string, unknown>).type || "").toLowerCase();
    if (typ === "plain") entrance = t("gates.plainTcp");
    else if (typ === "tls_sni") entrance = t("gates.tlsSni");
    else entrance = typ || t("gates.unknown");
  }
  return { listen: listenStr, entrance };
}
