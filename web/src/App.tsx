import { useRef } from "react";

import { useRoute } from "./hooks";
import { haptic } from "./telegram";
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

  // Sozlamalar tab emas — yopilganda qaysi tabdan kelganini eslab qolamiz
  const lastTab = useRef("today");
  if (route !== "settings") lastTab.current = route;

  if (route === "settings") {
    return <Settings onClose={() => navigate(lastTab.current)} />;
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
