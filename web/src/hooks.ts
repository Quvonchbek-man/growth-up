/** Kichik yordamchilar: hash-marshrutlash va ma'lumot yuklash. */

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Mavjud marshrutlar. `App.tsx` dagi `TABS` shu ro'yxatning ichida bo'lishi
 * kerak (`settings` va `admin` tab emas, lekin marshrut sifatida bor).
 */
export const ROUTES = ["today", "tomorrow", "team", "stats", "habits", "settings", "admin"];

/**
 * Hash-marshrutlash (`/#/today`).
 *
 * Nega tashqi kutubxona emas: bu yerda 5 ta sahifa va ichma-ich marshrut yo'q.
 * Hash bo'lgani uchun serverda hech qanday sozlash kerak emas — bot yuborgan
 * `/#/team` havolasi to'g'ridan-to'g'ri ochiladi.
 *
 * **Telegram hash'ni o'zi ham ishlatadi.** Mini App ochilganda u o'z
 * parametrlarini shu yerga yozadi: menyu tugmasidan kelganda
 * `#tgWebAppData=...&tgWebAppVersion=...`, bot havolasidan kelganda
 * `#/today&tgWebAppData=...`. Shuning uchun birinchi bo'lakni ajratib olamiz
 * va ro'yxatdan tekshiramiz — aks holda ilova ochilishida bo'sh ekran
 * ko'rinadi (tab bosilgunicha hech qaysi sahifa mos kelmaydi).
 */
export function useRoute(): [string, (route: string) => void] {
  const read = () => {
    const first = window.location.hash.replace(/^#\/?/, "").split(/[?&]/)[0];
    return ROUTES.includes(first) ? first : "today";
  };
  const [route, setRoute] = useState(read);

  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((next: string) => {
    window.location.hash = `/${next}`;
  }, []);

  return [route, navigate];
}

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (value: T) => void;
}

/** Yuklash + xato holatini bir joyda boshqaradi. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  // Eskirgan javob yangisining ustiga yozilib qolmasin
  const latest = useRef(0);

  useEffect(() => {
    const ticket = ++latest.current;
    setLoading(true);
    loader()
      .then((value) => {
        if (ticket === latest.current) {
          setData(value);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (ticket === latest.current) {
          setError(err instanceof Error ? err.message : "Noma'lum xato");
        }
      })
      .finally(() => {
        if (ticket === latest.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return {
    data,
    error,
    loading,
    reload: () => setNonce((n) => n + 1),
    setData,
  };
}
