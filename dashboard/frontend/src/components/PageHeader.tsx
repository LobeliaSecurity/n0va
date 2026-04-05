import { motion, useReducedMotion } from "framer-motion";

import { headerChildVariants, headerVariants } from "@/lib/motion";

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className="mb-8 flex flex-col gap-3 border-b border-slate-200 pb-6 sm:flex-row sm:items-start sm:justify-between"
      variants={headerVariants}
      initial={reduceMotion ? false : "hidden"}
      animate="show"
    >
      <motion.div variants={headerChildVariants} className="min-w-0 space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p>}
      </motion.div>
      {actions && (
        <motion.div variants={headerChildVariants} className="flex shrink-0 flex-wrap gap-2">
          {actions}
        </motion.div>
      )}
    </motion.div>
  );
}
