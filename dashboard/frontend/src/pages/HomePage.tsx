import { useEffect, useMemo, useState } from "react";

import { clsx } from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Card } from "@heroui/react/card";
import { Text } from "@heroui/react/text";

import { PageHeader } from "@/components/PageHeader";
import { staggerChildrenOnly, staggerContainer, staggerItem, staggerItemSubtle } from "@/lib/motion";
import { toast } from "@/lib/appToast";
import { summarizeGate } from "@/gate/summarizeGate";
import {
  health,
  listCas,
  listContentServers,
  listGates,
  type CaDto,
  type GateDto,
  type ContentServerDto,
} from "@/api";

const HOME_GATE_LIMIT = 4;
const HOME_CA_LIMIT = 4;

export function HomePage() {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();
  const [db, setDb] = useState<string | null>(null);
  const [gates, setGates] = useState<GateDto[]>([]);
  const [cas, setCas] = useState<CaDto[]>([]);
  const [contentServers, setContentServers] = useState<ContentServerDto[]>([]);
  const [loading, setLoading] = useState(true);

  const quickLinks = useMemo(
    () =>
      [
        { to: "/content", titleKey: "home.quickContentTitle", bodyKey: "home.quickContentBody" },
        { to: "/gates", titleKey: "home.quickGateTitle", bodyKey: "home.quickGateBody" },
        { to: "/hosts", titleKey: "home.quickHostsTitle", bodyKey: "home.quickHostsBody" },
        { to: "/ca", titleKey: "home.quickCaTitle", bodyKey: "home.quickCaBody" },
        { to: "/password", titleKey: "home.quickPwdTitle", bodyKey: "home.quickPwdBody" },
        { to: "/settings", titleKey: "home.quickSettingsTitle", bodyKey: "home.quickSettingsBody" },
      ] as const,
    [],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const [g, c, cs, h] = await Promise.all([
          listGates(),
          listCas(),
          listContentServers(),
          health(),
        ]);
        if (!cancelled) {
          setGates(g.gates);
          setCas(c.cas);
          setContentServers(cs.content_servers);
          setDb(h.db);
        }
      } catch (e) {
        if (!cancelled) toast.danger((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const runningCount = useMemo(() => gates.filter((g) => g.running).length, [gates]);
  const contentRunningCount = useMemo(
    () => contentServers.filter((s) => s.running).length,
    [contentServers],
  );
  const issuedTotal = useMemo(() => cas.reduce((s, c) => s + (c.issued_count ?? 0), 0), [cas]);
  const gatesPreview = useMemo(() => gates.slice(0, HOME_GATE_LIMIT), [gates]);
  const casPreview = useMemo(() => cas.slice(0, HOME_CA_LIMIT), [cas]);

  return (
    <>
      <PageHeader title={t("home.title")} description={t("home.description")} />

      <motion.div
        className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
      >
          <motion.div
            variants={staggerItem}
            className="rounded-2xl border border-slate-200/90 bg-gradient-to-br from-white via-slate-50/80 to-indigo-50/40 p-5 shadow-sm ring-1 ring-slate-100/80"
          >
            <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-slate-500">
              {t("home.statGates")}
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">
              {loading ? "—" : gates.length}
            </p>
            <p className="mt-1 text-xs text-slate-600">{t("home.statGatesHint")}</p>
          </motion.div>
          <motion.div
            variants={staggerItem}
            className="rounded-2xl border border-slate-200/90 bg-gradient-to-br from-white via-slate-50/80 to-emerald-50/40 p-5 shadow-sm ring-1 ring-slate-100/80"
          >
            <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-slate-500">
              {t("home.statRunning")}
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">
              {loading ? "—" : runningCount}
            </p>
            <p className="mt-1 text-xs text-slate-600">{t("home.statRunningHint")}</p>
          </motion.div>
          <motion.div
            variants={staggerItem}
            className="rounded-2xl border border-slate-200/90 bg-gradient-to-br from-white via-slate-50/80 to-violet-50/40 p-5 shadow-sm ring-1 ring-slate-100/80 sm:col-span-1"
          >
            <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-slate-500">
              {t("home.statCas")}
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">
              {loading ? "—" : cas.length}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              {t("home.statCasHint", { count: loading ? "—" : issuedTotal })}
            </p>
          </motion.div>
          <motion.div
            variants={staggerItem}
            className="rounded-2xl border border-slate-200/90 bg-gradient-to-br from-white via-slate-50/80 to-sky-50/40 p-5 shadow-sm ring-1 ring-slate-100/80"
          >
            <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-slate-500">
              {t("home.statContent")}
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">
              {loading ? "—" : contentServers.length}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              {t("home.statContentHint", { running: loading ? "—" : contentRunningCount })}
            </p>
          </motion.div>
        </motion.div>

      <motion.div
        className="mb-10 grid gap-8 lg:grid-cols-2 lg:gap-10"
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
      >
          <motion.section variants={staggerItem} aria-labelledby="home-gates-heading">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
              <h2 id="home-gates-heading" className="text-lg font-semibold text-slate-900">
                {t("home.sectionGates")}
              </h2>
              <Link
                to="/gates"
                className="text-sm font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-900"
              >
                {t("home.viewAll")}
              </Link>
            </div>
            {loading ? (
              <p className="text-sm text-slate-500">{t("common.loading")}</p>
            ) : gatesPreview.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 px-5 py-10 text-center">
                <p className="text-sm text-slate-600">{t("home.emptyGates")}</p>
                <Link
                  to="/gates/new"
                  className="mt-3 inline-block text-sm font-medium text-indigo-700 underline hover:text-indigo-900"
                >
                  {t("home.emptyGatesCta")}
                </Link>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {gatesPreview.map((g) => {
                  const { listen, entrance } = summarizeGate(g, t);
                  return (
                    <motion.div
                      key={g.id}
                      whileHover={reduceMotion ? undefined : { y: -3 }}
                      transition={{ type: "spring", stiffness: 420, damping: 30 }}
                    >
                    <Link
                      to={`/gates/${g.id}`}
                      className="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-100/80 transition-shadow duration-200 hover:border-indigo-200 hover:shadow-md"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-slate-900">{g.name}</p>
                          <p className="mt-0.5 font-mono text-xs text-slate-400">#{g.id}</p>
                        </div>
                        <span
                          className={clsx(
                            "shrink-0 rounded-full px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide",
                            g.running
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-100 text-slate-600",
                          )}
                        >
                          {g.running ? t("common.running") : t("common.stopped")}
                        </span>
                      </div>
                      <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-600">
                        <div className="flex flex-wrap gap-x-1">
                          <span className="text-slate-400">{t("common.listen")}</span>
                          <code className="rounded bg-slate-100 px-1 font-mono text-[0.7rem] text-slate-800">
                            {listen}
                          </code>
                        </div>
                        <div>
                          <span className="text-slate-400">{t("common.entrance")} </span>
                          <span className="font-medium text-slate-800">{entrance}</span>
                        </div>
                      </div>
                      <span className="mt-3 text-xs font-medium text-indigo-600 group-hover:text-indigo-800">
                        {t("home.openGate")} →
                      </span>
                    </Link>
                    </motion.div>
                  );
                })}
              </div>
            )}
            {!loading && gates.length > HOME_GATE_LIMIT && (
              <p className="mt-3 text-center text-xs text-slate-500">
                {t("home.moreGates", { n: gates.length - HOME_GATE_LIMIT })}
              </p>
            )}
          </motion.section>

          <motion.section variants={staggerItem} aria-labelledby="home-ca-heading">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
              <h2 id="home-ca-heading" className="text-lg font-semibold text-slate-900">
                {t("home.sectionCas")}
              </h2>
              <Link
                to="/ca"
                className="text-sm font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-900"
              >
                {t("home.viewAll")}
              </Link>
            </div>
            {loading ? (
              <p className="text-sm text-slate-500">{t("common.loading")}</p>
            ) : casPreview.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 px-5 py-10 text-center">
                <p className="text-sm text-slate-600">{t("home.emptyCas")}</p>
                <Link to="/ca" className="mt-3 inline-block text-sm font-medium text-indigo-700 underline hover:text-indigo-900">
                  {t("home.emptyCasCta")}
                </Link>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {casPreview.map((c) => (
                  <motion.div
                    key={c.id}
                    whileHover={reduceMotion ? undefined : { y: -3 }}
                    transition={{ type: "spring", stiffness: 420, damping: 30 }}
                  >
                  <Link
                    to={`/ca/${c.id}`}
                    className="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-100/80 transition-shadow duration-200 hover:border-violet-200 hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-slate-900">{c.name}</p>
                        <p className="mt-0.5 font-mono text-xs text-slate-500">{c.common_name}</p>
                      </div>
                      <span className="shrink-0 rounded-full bg-violet-100 px-2 py-0.5 text-[0.65rem] font-semibold text-violet-900">
                        {t("ca.issuedBadge", { count: c.issued_count })}
                      </span>
                    </div>
                    <span className="mt-3 border-t border-slate-100 pt-3 text-xs font-medium text-violet-700 group-hover:text-violet-900">
                      {t("home.openCa")} →
                    </span>
                  </Link>
                  </motion.div>
                ))}
              </div>
            )}
            {!loading && cas.length > HOME_CA_LIMIT && (
              <p className="mt-3 text-center text-xs text-slate-500">
                {t("home.moreCas", { n: cas.length - HOME_CA_LIMIT })}
              </p>
            )}
          </motion.section>
        </motion.div>

      <motion.div
        className="mb-10"
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
      >
        <motion.p variants={staggerItemSubtle} className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          {t("home.shortcutsHeading")}
        </motion.p>
        <motion.div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" variants={staggerChildrenOnly}>
          {quickLinks.map((item) => (
            <motion.div key={item.to} variants={staggerItem}>
            <Link
              to={item.to}
              className="group block h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow duration-200 hover:border-slate-300 hover:shadow-md"
            >
              <Text className="text-sm font-semibold text-slate-900 group-hover:text-slate-950">{t(item.titleKey)}</Text>
              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-600">{t(item.bodyKey)}</p>
              <span className="mt-2 inline-block text-xs font-medium text-slate-500 group-hover:text-slate-700">
                {t("common.open")}
              </span>
            </Link>
            </motion.div>
          ))}
        </motion.div>
      </motion.div>

      <motion.div
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
        className="flex flex-col gap-6"
      >
      <motion.div variants={staggerItemSubtle}>
      <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <Card.Header className="px-6 pt-6">
          <Card.Title className="text-lg text-slate-900">{t("home.aboutTitle")}</Card.Title>
          <Card.Description className="text-slate-600">{t("home.aboutIntro")}</Card.Description>
        </Card.Header>
        <Card.Content className="space-y-3 px-6 pb-6 text-sm leading-relaxed text-slate-700">
          <p>{t("home.aboutGate")}</p>
          <p>{t("home.aboutCa")}</p>
          <p>{t("home.aboutPwd")}</p>
        </Card.Content>
      </Card.Root>
      </motion.div>

      <motion.div variants={staggerItemSubtle}>
      <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <Card.Header className="px-6 pt-6">
          <Card.Title className="text-lg text-slate-900">{t("home.apiTitle")}</Card.Title>
          <Card.Description className="text-slate-600">{t("home.apiDesc")}</Card.Description>
        </Card.Header>
        <Card.Content className="px-6 pb-6">
          {db && (
            <p className="text-sm text-slate-700">
              {t("common.database")}:{" "}
              <code className="break-all rounded-md bg-slate-100 px-2 py-1 font-mono text-xs text-slate-800">{db}</code>
            </p>
          )}
          {!db && loading && <p className="text-sm text-slate-500">{t("common.loading")}</p>}
          {!db && !loading && <p className="text-sm text-slate-500">—</p>}
        </Card.Content>
      </Card.Root>
      </motion.div>
      </motion.div>
    </>
  );
}
