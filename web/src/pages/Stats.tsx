import { useState } from "react";

import { api, type StatsView } from "../api";
import { HabitHeatmap, ReasonsChart, SeriesTable, TrendChart } from "../components/charts";
import { Card, ErrorBox, Loading, Tiles } from "../components/ui";
import { useAsync } from "../hooks";

const RANGES = [
  { days: 7, label: "7 kun" },
  { days: 30, label: "30 kun" },
  { days: 90, label: "90 kun" },
];

export default function Stats() {
  const [days, setDays] = useState(30);
  const [asTable, setAsTable] = useState(false);
  const stats = useAsync<StatsView>(() => api.stats(days), [days]);

  if (stats.loading && !stats.data) return <Loading />;
  if (stats.error) return <ErrorBox message={stats.error} onRetry={stats.reload} />;
  if (!stats.data) return null;

  const view = stats.data;
  const planned = view.series.filter((point) => point.planned > 0);
  const avgPct = planned.length
    ? Math.round(planned.reduce((sum, point) => sum + point.pct, 0) / planned.length)
    : 0;
  const totalScore = view.series.reduce((sum, point) => sum + point.score, 0);

  return (
    <div className="page">
      <h1>Statistika</h1>

      {/* Filtrlar bitta qatorda, grafiklardan yuqorida */}
      <div className="row" style={{ gap: 8 }}>
        {RANGES.map((range) => (
          <button
            key={range.days}
            className={`btn btn--small ${days === range.days ? "" : "btn--ghost"}`}
            onClick={() => setDays(range.days)}
          >
            {range.label}
          </button>
        ))}
      </div>

      <Tiles
        items={[
          { value: `🔥 ${view.streak}`, label: `ketma-ket (eng yaxshi ${view.best_streak})` },
          { value: `${avgPct}%`, label: "o'rtacha bajarilish" },
          { value: totalScore, label: "jami ball" },
        ]}
      />

      <Card title={`Bajarilish — ${days} kun`}>
        {asTable ? <SeriesTable series={view.series} /> : <TrendChart stats={view} />}
        <button
          className="btn btn--small btn--ghost"
          style={{ marginTop: 10 }}
          onClick={() => setAsTable((value) => !value)}
        >
          {asTable ? "Grafik ko'rinishi" : "Jadval ko'rinishi"}
        </button>
      </Card>

      <Card title="Nega bajarilmadi">
        <ReasonsChart reasons={view.reasons} />
        <p className="small muted" style={{ marginBottom: 0, marginTop: 6 }}>
          Bu ro'yxatda bitta sabab ustun bo'lsa — muammo irodada emas, tizimda.
          «Vaqt yetmadi» ko'p bo'lsa, reja hajmi katta.
        </p>
      </Card>

      <Card title="Odatlar bo'yicha">
        <HabitHeatmap matrix={view.habit_matrix} />
        <p className="small muted" style={{ marginBottom: 0, marginTop: 8 }}>
          Chapdan o'ngga — kunlar. Bir qatorda bo'sh halqalar to'planib qolsa,
          o'sha odat sizga to'g'ri kelmayapti.
        </p>
      </Card>
    </div>
  );
}
