import { useEffect, useState } from "react";

import { api, type AdminView } from "../api";
import { Card, ErrorBox, Loading, Tiles } from "../components/ui";
import { MembersChart } from "../components/charts";
import { useAsync } from "../hooks";
import { showBackButton } from "../telegram";

const RANGES = [
  { days: 7, label: "7 kun" },
  { days: 30, label: "30 kun" },
  { days: 90, label: "90 kun" },
];

/**
 * Bot admini uchun kuzatuv ekrani.
 *
 * Tab emas — sozlamalardan ochiladi (`App.tsx` dagi TABS 5 tadan
 * oshmasligi kerak). Ommaviy xabar bu yerda yo'q: u botda, `/xabar`.
 */
export default function Admin({ onClose }: { onClose: () => void }) {
  const [days, setDays] = useState(30);
  const view = useAsync<AdminView>(() => api.admin(days), [days]);

  useEffect(() => showBackButton(onClose), [onClose]);

  if (view.loading && !view.data) return <Loading />;
  if (view.error) return <ErrorBox message={view.error} onRetry={view.reload} />;
  if (!view.data) return null;

  const data = view.data;
  const { users, teams, activity, results } = data;
  const sherikUlushi = users.total ? Math.round((teams.with_partner * 100) / users.total) : 0;

  return (
    <div className="page">
      <div className="row row--between">
        <h1>🛠 Admin panel</h1>
        <button className="iconbtn" aria-label="Yopish" onClick={onClose}>
          ✕
        </button>
      </div>
      <p className="small muted" style={{ marginTop: -8 }}>
        {data.date} · butun bot bo'yicha
      </p>

      <Tiles
        items={[
          { value: users.total, label: "foydalanuvchi" },
          { value: `+${users.new_today}`, label: "bugun qo'shildi" },
          { value: activity.submitted_today, label: "bugun reja tuzdi" },
        ]}
      />

      {/* Ilovaning butun qiymati sherikda: yolg'iz odam ertami-kechmi
          tashlab ketadi. Shuning uchun bu raqam eng tepada. */}
      <Card title="Sherik holati">
        <Tiles
          items={[
            { value: teams.with_partner, label: "sherigi bor" },
            { value: teams.alone, label: "yolg'iz" },
            { value: `${sherikUlushi}%`, label: "sherik topgan" },
          ]}
        />
        <p className="small muted" style={{ marginBottom: 0, marginTop: 8 }}>
          Yolg'izlar ulushi o'sib borsa — muammo jalb qilishda emas, sherik
          topishda. {teams.groups} ta jamoa, shundan {teams.paired_groups} tasi
          2+ kishilik.
        </p>
      </Card>

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

      <Card title={`A'zolar dinamikasi — ${days} kun`}>
        <MembersChart points={data.members} />
        <p className="small muted" style={{ marginBottom: 0, marginTop: 6 }}>
          Qo'shildi: bugun {users.new_today} · 7 kunda {users.new_7d} · 30 kunda{" "}
          {users.new_30d}. Botni bloklagan: {users.blocked}.
        </p>
      </Card>

      <Card title="Faollik va natija">
        <table>
          <tbody>
            <tr>
              <td>Bugun reja tasdiqlagan</td>
              <td className="num">
                <strong>{activity.submitted_today}</strong>
              </td>
            </tr>
            <tr>
              <td>7 kunda faol</td>
              <td className="num">{activity.active_7d}</td>
            </tr>
            <tr>
              <td>7 kunda ✅ bosgan</td>
              <td className="num">{activity.done_7d}</td>
            </tr>
            <tr>
              <td>O'rtacha bajarilish (7 kun)</td>
              <td className="num">{results.avg_pct_7d}%</td>
            </tr>
            <tr>
              <td>Bajarilgan vazifa (7 kun)</td>
              <td className="num">{results.tasks_done_7d}</td>
            </tr>
            <tr>
              <td>Eng uzun streak</td>
              <td className="num">🔥 {results.best_streak}</td>
            </tr>
            <tr>
              <td>Bugun yuborilgan eslatma</td>
              <td className="num">{data.reminders_today}</td>
            </tr>
          </tbody>
        </table>
      </Card>

      <Card title="Oxirgi qo'shilganlar">
        {data.recent.length === 0 ? (
          <p className="empty">Hali hech kim yo'q.</p>
        ) : (
          <table>
            <tbody>
              {data.recent.map((row) => (
                <tr key={row.user_id}>
                  <td>
                    {row.is_blocked ? "🚫" : row.has_partner ? "🤝" : "👤"} {row.name}
                    {row.username && <span className="small muted"> @{row.username}</span>}
                  </td>
                  <td className="num small muted">{(row.joined ?? "").slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="small muted" style={{ marginBottom: 0, marginTop: 8 }}>
          🤝 sherigi bor · 👤 yolg'iz · 🚫 botni bloklagan
        </p>
      </Card>

      <p className="small muted" style={{ textAlign: "center" }}>
        Ommaviy xabar botda: <code>/xabar</code>
      </p>
    </div>
  );
}
