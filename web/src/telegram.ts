/**
 * Telegram WebApp SDK ustidan yupqa qatlam.
 *
 * Brauzerda ochilganda SDK yo'q — o'shanda hamma narsa "bo'sh" ishlaydi va
 * ilova baribir ochiladi. Aks holda har grafik o'zgarishini ko'rish uchun
 * telefonda Telegram ochish kerak bo'lardi.
 */

type HapticStyle = "light" | "medium" | "heavy" | "soft" | "rigid";

interface TgWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  ready: () => void;
  expand: () => void;
  close: () => void;
  onEvent: (event: string, cb: () => void) => void;
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: HapticStyle) => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
  };
  showAlert?: (message: string) => void;
  showConfirm?: (message: string, cb: (ok: boolean) => void) => void;
  showPopup?: (
    params: {
      title?: string;
      message: string;
      buttons: { id: string; type?: string; text?: string }[];
    },
    cb: (buttonId: string) => void,
  ) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp };
  }
}

export const tg: TgWebApp | undefined = window.Telegram?.WebApp;

/** Telegram ichida ishlayapmizmi (initData bo'lsa — ha). */
export const inTelegram = Boolean(tg?.initData);

export function initTelegram(): void {
  if (!tg) {
    // Brauzer rejimi: OS mavzusiga ergashamiz
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    return;
  }

  tg.ready();
  tg.expand();
  applyScheme();
  // Foydalanuvchi Telegram mavzusini almashtirsa, ilova ham almashsin
  tg.onEvent("themeChanged", applyScheme);
}

function applyScheme(): void {
  document.documentElement.dataset.theme = tg?.colorScheme ?? "light";
}

export function haptic(style: HapticStyle = "light"): void {
  tg?.HapticFeedback?.impactOccurred(style);
}

export function notify(type: "error" | "success" | "warning"): void {
  tg?.HapticFeedback?.notificationOccurred(type);
}

export function alertUser(message: string): void {
  if (tg?.showAlert) tg.showAlert(message);
  else window.alert(message);
}

/**
 * SDK metodini chaqirib, javobini `Promise` qilib qaytaradi.
 *
 * `undefined` qaytsa — metodni ishlatib bo'lmaydi. Ikki sabab bor va
 * ikkalasi ham haqiqiy: metod umuman yo'q (juda eski SDK) yoki **bor,
 * lekin chaqirilganda `WebAppMethodUnsupported` deb otiladi** — Telegram
 * mijozining versiyasi yetmaganda shunday bo'ladi (`showConfirm` va
 * `showPopup` — 6.2 dan). Ikkinchisini `new Promise` ichida ushlab
 * bo'lmaydi: u xatoni `reject` ga aylantiradi va tugma bosilganda
 * ilova jimgina hech narsa qilmay qo'yadi.
 */
function askViaSdk(call: (resolve: (ok: boolean) => void) => void): Promise<boolean> | undefined {
  let settle!: (ok: boolean) => void;
  const answer = new Promise<boolean>((resolve) => {
    settle = resolve;
  });
  try {
    call(settle);
  } catch {
    return undefined;
  }
  return answer;
}

/** Qaytarib bo'lmaydigan amallar uchun tasdiq (a'zoni chiqarish, kodni yangilash). */
export function confirmUser(message: string): Promise<boolean> {
  if (tg?.showConfirm) {
    const answer = askViaSdk((resolve) => tg.showConfirm!(message, resolve));
    if (answer) return answer;
  }
  return Promise.resolve(window.confirm(message));
}

/**
 * Tugmalari o'z matniga ega tasdiq oynasi.
 *
 * `showConfirm` dan farqi shu: undagi tugmalar doim OK/Bekor, ya'ni
 * «nimani tasdiqlayapman?» degan savolga javob bermaydi. `showPopup`
 * eski mijozlarda yo'q — o'shanda `showConfirm` ga, brauzerda esa
 * `window.confirm` ga tushamiz (matn savol qatorida bo'lgani uchun
 * ma'no ikkalasida ham saqlanadi).
 */
export function popupConfirm(
  title: string,
  message: string,
  okText: string,
  cancelText: string,
): Promise<boolean> {
  if (tg?.showPopup) {
    const answer = askViaSdk((resolve) =>
      tg.showPopup!(
        {
          title,
          message,
          buttons: [
            { id: "ok", type: "default", text: okText },
            { id: "cancel", type: "default", text: cancelText },
          ],
        },
        (buttonId) => resolve(buttonId === "ok"),
      ),
    );
    if (answer) return answer;
  }
  return confirmUser(message);
}

/**
 * Telegram'ning yuqoridagi «orqaga» tugmasi (sozlamalar oynasini yopish uchun).
 *
 * `showMainButton` kabi: hook emas, `useEffect` ichidan chaqiriladi va qaytgan
 * funksiya tozalaydi. Brauzerda tugma yo'q — o'shanda ✕ tugmasi ishlaydi.
 */
export function showBackButton(onClick: () => void): () => void {
  const button = tg?.BackButton;
  if (!button) return () => {};
  button.onClick(onClick);
  button.show();
  return () => {
    button.offClick(onClick);
    button.hide();
  };
}
