import type { ComponentProps } from "react";

import { Link } from "@heroui/react/link";
import { useHref } from "react-router-dom";

type AppLinkProps = {
  to: string;
  children: React.ReactNode;
  className?: string;
} & Omit<ComponentProps<typeof Link.Root>, "href" | "children">;

export function AppLink({ to, children, className, ...rest }: AppLinkProps) {
  const href = useHref(to);
  return (
    <Link.Root href={href} className={className} {...rest}>
      {children}
    </Link.Root>
  );
}
