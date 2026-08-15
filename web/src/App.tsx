import { useRef } from "react";

import { useRoute } from "./hooks";
import { haptic } from "./telegram";
import Admin from "./pages/Admin";
import Habits from "./pages/Habits";
import Settings from "./pages/Settings";
import Stats from "./pages/Stats";
import Team from "./pages/Team";
import Today from "./pages/Today";
import Tomorrow from "./pages/Tomorrow";

// `id` lar `hooks.ts` dagi ROUTES ichida bo'lishi shart — aks holda o'sha tab
// bosilganda bo'sh ekran chiqadi
const TABS = [
  { id: "today", icon: "☀️", label: "Bugun" },
  { id: "tomorrow", icon: "🌙", label: "Ertaga" },
  { id: "team", icon: "👥", label: "Jamoa" },
  { id: "stats", icon: "📊", label: "Statistika" },
  { id: "habits", icon: "🔁", label: "Odatlar" },
];

export default function App() {
  const [route, navigate] = useRoute();

  // Sozlamalar va admin paneli tab emas — yopilganda qaysi tabdan
  // kelganini eslab qolamiz
  const lastTab = useRef("today");
  if (route !== "settings" && route !== "admin") lastTab.current = route;

  if (route === "settings") {
    return <Settings onClose={() => navigate(lastTab.current)} />;
  }

  // Ochiq marshrut, lekin ma'lumotni server faqat adminga beradi (403).
  // Manzilni qo'lda yozgan odam bo'sh ekran ko'radi, xolos.
  if (route === "admin") {
    return <Admin onClose={() => navigate("settings")} />;
  }

  return (
    <>
      {route === "today" && <Today />}
      {route === "tomorrow" && <Tomorrow />}
      {route === "team" && <Team />}
      {route === "stats" && <Stats />}
      {route === "habits" && <Habits />}

      <button
        className="iconbtn iconbtn--float"
        aria-label="Sozlamalar"
        onClick={() => {
          haptic();
          navigate("settings");
        }}
      >
        ⚙️
      </button>

      <nav className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab${route === tab.id ? " tab--active" : ""}`}
            onClick={() => {
              haptic();
              navigate(tab.id);
            }}
          >
            <span className="tab__icon">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>
    </>
  );
}
