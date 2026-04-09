import { useEffect } from "react";

const BRAND = "n0va";

export function usePageTitle(title: string) {
  useEffect(() => {
    const trimmed = title.trim();
    document.title = trimmed ? `${trimmed} · ${BRAND}` : BRAND;
  }, [title]);
}
