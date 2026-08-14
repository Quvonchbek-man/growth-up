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
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
    setText: (text: string) => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
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

/** Qaytarib bo'lmaydigan amallar uchun tasdiq (a'zoni chiqarish, kodni yangilash). */
export function confirmUser(message: string): Promise<boolean> {
  if (tg?.showConfirm) {
    return new Promise((resolve) => tg.showConfirm!(message, resolve));
  }
  return Promise.resolve(window.confirm(message));
}

/**
 * Telegram'ning pastdagi katta tugmasini ko'rsatadi.
 *
 * Bu React hook EMAS (nomi `use` bilan boshlanmasligi ataylab) — uni
 * `useEffect` ichidan chaqirib, qaytgan funksiyani tozalash uchun ishlatamiz.
 */
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

export function showMainButton(text: string, onClick: () => void): () => void {
  if (!tg) return () => {};
  const button = tg.MainButton;
  button.setText(text);
  button.show();
  button.onClick(onClick);
  return () => {
    button.offClick(onClick);
    button.hide();
  };
}
