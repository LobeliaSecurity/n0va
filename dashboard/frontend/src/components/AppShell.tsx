import { clsx } from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Link } from "@heroui/react/link";
import { Separator } from "@heroui/react/separator";
import { Text } from "@heroui/react/text";
import { Tooltip } from "@heroui/react/tooltip";

import { AnimatedMain } from "@/components/AnimatedMain";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SkipToMainLink } from "@/components/SkipToMainLink";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { easeOut, navItemVariants, navListVariants } from "@/lib/motion";

export function AppShell() {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();
  const location = useLocation();
  const compactNav = useMediaQuery("(max-width: 767px)");
  const wideMain =
    /^\/gates\/[^/]+$/.test(location.pathname) && location.pathname !== "/gates/new";

  const NAV_ITEMS: { to: string; labelKey: string; hintKey: string; end?: boolean }[] = [
    { to: "/", labelKey: "nav.overview", hintKey: "nav.overviewHint", end: true },
    { to: "/content", labelKey: "nav.content", hintKey: "nav.contentHint" },
    { to: "/gates", labelKey: "nav.gate", hintKey: "nav.gateHint" },
    { to: "/hosts", labelKey: "nav.hosts", hintKey: "nav.hostsHint" },
    { to: "/ca", labelKey: "nav.ca", hintKey: "nav.caHint" },
    { to: "/password", labelKey: "nav.password", hintKey: "nav.passwordHint" },
    { to: "/settings", labelKey: "nav.settings", hintKey: "nav.settingsHint" },
  ];

  const navClass = ({ isActive }: { isActive: boolean }) =>
    clsx(
      "flex min-w-[7.5rem] flex-col rounded-lg px-3 py-2.5 text-left transition-colors duration-200 md:min-w-0",
      isActive
        ? "bg-slate-100 font-medium text-slate-900 shadow-sm ring-1 ring-slate-200/80 dark:bg-slate-800 dark:text-slate-50 dark:ring-slate-600/80"
        : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/80 dark:hover:text-slate-50",
    );

  return (
    <div className="flex min-h-dvh flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 md:flex-row md:items-start">
      <SkipToMainLink />
      <motion.aside
        className="flex shrink-0 flex-col border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 md:sticky md:top-0 md:h-dvh md:max-h-dvh md:w-60 md:overflow-hidden md:border-b-0 md:border-r md:border-slate-200 md:dark:border-slate-800"
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
              <Text className="pr-[1ch] text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50">
                {t("nav.brand")}
              </Text>
              <Text className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {t("nav.subtitle")}
              </Text>
            </div>
          </motion.div>
          <Separator className="my-2 shrink-0 bg-slate-200 dark:bg-slate-700" />
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
                {compactNav ? (
                  <Tooltip.Root delay={250}>
                    <Tooltip.Trigger className="block w-full cursor-default border-0 bg-transparent p-0 text-left">
                      <NavLink to={item.to} end={item.end} className={navClass}>
                        <span className="text-sm">{t(item.labelKey)}</span>
                        <span className="hidden text-xs font-normal text-slate-500 md:inline dark:text-slate-400">
                          {t(item.hintKey)}
                        </span>
                      </NavLink>
                    </Tooltip.Trigger>
                    <Tooltip.Content className="max-w-xs">
                      <p className="text-xs">{t(item.hintKey)}</p>
                    </Tooltip.Content>
                  </Tooltip.Root>
                ) : (
                  <NavLink to={item.to} end={item.end} className={navClass}>
                    <span className="text-sm">{t(item.labelKey)}</span>
                    <span className="hidden text-xs font-normal text-slate-500 md:inline dark:text-slate-400">
                      {t(item.hintKey)}
                    </span>
                  </NavLink>
                )}
              </motion.div>
            ))}
          </motion.nav>
        </div>
        <motion.div
          className="shrink-0 border-t border-slate-100 px-5 py-4 dark:border-slate-800"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: reduceMotion ? 0 : 0.35, duration: reduceMotion ? 0 : 0.3 }}
        >
          <LanguageSwitcher compact className="mb-3" />
          <p className="hidden text-xs leading-snug text-slate-500 md:block dark:text-slate-400">{t("nav.footer")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.7rem] font-medium text-indigo-800 md:mt-3 dark:text-indigo-300">
            <Link.Root
              href="https://github.com/LobeliaSecurity/n0va"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-indigo-200 underline-offset-2 hover:text-indigo-950 dark:hover:text-indigo-100"
            >
              {t("nav.repoLink")}
            </Link.Root>
            <span className="text-slate-300 dark:text-slate-600" aria-hidden>
              ·
            </span>
            <Link.Root
              href="https://github.com/LobeliaSecurity/n0va/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-indigo-200 underline-offset-2 hover:text-indigo-950 dark:hover:text-indigo-100"
            >
              {t("nav.issuesLink")}
            </Link.Root>
          </div>
        </motion.div>
      </motion.aside>

      <div className="flex min-w-0 flex-1 flex-col md:min-h-dvh">
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 px-4 py-6 outline-none sm:px-6 lg:px-10 lg:py-10"
        >
          <div className={clsx("mx-auto", wideMain ? "max-w-6xl" : "max-w-4xl")}>
            <AnimatedMain />
          </div>
        </main>
      </div>
    </div>
  );
}
