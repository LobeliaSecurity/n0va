import { clsx } from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Separator } from "@heroui/react/separator";
import { Text } from "@heroui/react/text";

import { AnimatedMain } from "@/components/AnimatedMain";
import { easeOut, navItemVariants, navListVariants } from "@/lib/motion";

export function AppShell() {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();

  const NAV_ITEMS: { to: string; labelKey: string; hintKey: string; end?: boolean }[] = [
    { to: "/", labelKey: "nav.overview", hintKey: "nav.overviewHint", end: true },
    { to: "/content", labelKey: "nav.content", hintKey: "nav.contentHint" },
    { to: "/gates", labelKey: "nav.gate", hintKey: "nav.gateHint" },
    { to: "/hosts", labelKey: "nav.hosts", hintKey: "nav.hostsHint" },
    { to: "/ca", labelKey: "nav.ca", hintKey: "nav.caHint" },
    { to: "/password", labelKey: "nav.password", hintKey: "nav.passwordHint" },
    { to: "/settings", labelKey: "nav.settings", hintKey: "nav.settingsHint" },
  ];

  return (
    <div className="flex min-h-dvh flex-col bg-slate-50 text-slate-900 md:flex-row md:items-start">
      <motion.aside
        className="flex shrink-0 flex-col border-b border-slate-200 bg-white md:sticky md:top-0 md:h-dvh md:max-h-dvh md:w-60 md:overflow-hidden md:border-b-0 md:border-r"
        aria-label={t("nav.aria")}
        initial={reduceMotion ? false : { opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.38, ease: easeOut }}
      >
        <div className="flex flex-col gap-1 px-4 pb-4 pt-5 md:min-h-0 md:flex-1 md:overflow-y-auto md:px-5 md:pt-8">
          <motion.div
            className="mb-2 flex shrink-0 items-center gap-3"
            initial={reduceMotion ? false : { opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: reduceMotion ? 0 : 0.4, ease: easeOut, delay: reduceMotion ? 0 : 0.05 }}
          >
            <motion.img
              src="/logo.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 shrink-0 object-contain"
              whileHover={reduceMotion ? undefined : { scale: 1.04 }}
              transition={{ type: "spring", stiffness: 400, damping: 22 }}
            />
            <div className="min-w-0">
              <Text className="pr-[1ch] text-lg font-semibold tracking-tight text-slate-900">{t("nav.brand")}</Text>
              <Text className="text-xs font-medium uppercase tracking-wider text-slate-500">
                {t("nav.subtitle")}
              </Text>
            </div>
          </motion.div>
          <Separator className="my-2 shrink-0 bg-slate-200" />
          <motion.nav
            className="flex flex-row gap-1 overflow-x-auto pb-1 md:flex-col md:overflow-visible md:pb-0"
            variants={navListVariants}
            initial={reduceMotion ? "show" : "hidden"}
            animate="show"
          >
            {NAV_ITEMS.map((item) => (
              <motion.div
                key={item.to}
                variants={navItemVariants}
                whileHover={reduceMotion ? undefined : { y: -1 }}
                whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                transition={{ type: "spring", stiffness: 420, damping: 30 }}
              >
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    clsx(
                      "flex min-w-[7.5rem] flex-col rounded-lg px-3 py-2.5 text-left transition-colors duration-200 md:min-w-0",
                      isActive
                        ? "bg-slate-100 font-medium text-slate-900 shadow-sm ring-1 ring-slate-200/80"
                        : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                    )
                  }
                >
                  <span className="text-sm">{t(item.labelKey)}</span>
                  <span className="hidden text-xs font-normal text-slate-500 md:inline">{t(item.hintKey)}</span>
                </NavLink>
              </motion.div>
            ))}
          </motion.nav>
        </div>
        <motion.div
          className="shrink-0 border-t border-slate-100 px-5 py-4"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: reduceMotion ? 0 : 0.35, duration: reduceMotion ? 0 : 0.3 }}
        >
          <p className="hidden text-xs leading-snug text-slate-500 md:block">{t("nav.footer")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.7rem] font-medium text-indigo-800 md:mt-3">
            <a
              href="https://github.com/LobeliaSecurity/n0va"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-indigo-200 underline-offset-2 hover:text-indigo-950"
            >
              {t("nav.repoLink")}
            </a>
            <span className="text-slate-300" aria-hidden>
              ·
            </span>
            <a
              href="https://github.com/LobeliaSecurity/n0va/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-indigo-200 underline-offset-2 hover:text-indigo-950"
            >
              {t("nav.issuesLink")}
            </a>
          </div>
        </motion.div>
      </motion.aside>

      <div className="flex min-w-0 flex-1 flex-col md:min-h-dvh">
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <div className="mx-auto max-w-4xl">
            <AnimatedMain />
          </div>
        </main>
      </div>
    </div>
  );
}
