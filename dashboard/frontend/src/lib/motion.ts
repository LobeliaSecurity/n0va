import type { Variants } from "framer-motion";

/** モダンなイージング（控えめ） */
export const easeOut = [0.25, 0.1, 0.25, 1] as const;

export const transitionFast = {
  duration: 0.22,
  ease: easeOut,
};

export const transitionMedium = {
  duration: 0.32,
  ease: easeOut,
};

/** ヘッダー見出し */
export const headerVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { ...transitionFast, staggerChildren: 0.06, delayChildren: 0.04 },
  },
};

export const headerChildVariants: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: transitionFast },
};

/** グリッドの子を順に */
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.055, delayChildren: 0.06 },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: transitionFast },
};

export const staggerItemSubtle: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { ...transitionFast, duration: 0.18 } },
};

/** 親の opacity は変えず、子だけ stagger したいとき */
export const staggerChildrenOnly: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.05, delayChildren: 0.04 },
  },
};

/** サイドバー項目 */
export const navListVariants: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.04, delayChildren: 0.08 },
  },
};

export const navItemVariants: Variants = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { ...transitionFast, duration: 0.2 } },
};
