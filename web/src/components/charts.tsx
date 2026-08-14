/**
 * Grafiklar.
 *
 * Rang qoidalari (tekshiruvdan o'tgan palitra, `theme.css` ga qarang):
 *  • Kategoriyali slotlar qat'iy tartibda: men → 1, birinchi sherik → 2,
 *    ikkinchi → 3. Rang ODAMGA biriktiriladi, o'ringa emas — reyting
 *    o'zgarganda ranglar sakramaydi.
 *  • Uchtadan ortiq odam bir grafikda ko'rsatilmaydi: to'rtinchi rangdan
 *    boshlab juftliklar rang ko'rligida ajratilmay qoladi. Ortiqchasi
 *    jadvalga tushadi.
 *  • Holat ranglari (bajarildi/bajarilmadi) seriya rangi sifatida
 *    ishlatilmaydi va yolg'iz rangga tayanmaydi — heatmap'da to'ldirish va
 *    halqa farqi qo'shimcha belgi bo'lib xizmat qiladi.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SeriesPoint, StatsView } from "../api";
import { Legend } from "./ui";

export const SERIES_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
export const MAX_SERIES = SERIES_COLORS.length;

const AXIS_TICK = { fill: "var(--ink-muted)", fontSize: 11 };

function shortDate(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${Number(day)}.${Number(month)}`;
}

// ─── Maslahat oynasi ───────────────────────────────────────────────────────

interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
}

function ChartTooltip({
  active,
  payload,
  label,
  suffix = "",
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  suffix?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--line)",
        borderRadius: 10,
        padding: "8px 10px",
        fontSize: 12,
        color: "var(--text)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
      }}
    >
      <div style={{ color: "var(--text-dim)", marginBottom: 4 }}>{label}</div>
      {payload.map((entry, index) => (
        <div key={index} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 2,
              background: entry.color,
              display: "inline-block",
            }}
          />
          <span>{entry.name}</span>
          <strong style={{ marginLeft: "auto" }}>
            {entry.value}
            {suffix}
          </strong>
        </div>
      ))}
    </div>
  );
}

// ─── 30 kunlik bajarilish ──────────────────────────────────────────────────

interface TrendRow {
  date: string;
  [key: string]: string | number;
}

export function TrendChart({ stats }: { stats: StatsView }) {
  const partners = stats.partners.slice(0, MAX_SERIES - 1);
  const people = [{ key: "me", name: "Men", series: stats.series }].concat(
    partners.map((p) => ({ key: `u${p.user_id}`, name: p.name, series: p.series })),
  );

  // Bir kunning barcha odamlari — bitta qator
  const rows: TrendRow[] = stats.series.map((point, index) => {
    const row: TrendRow = { date: shortDate(point.date) };
    for (const person of people) {
      row[person.key] = person.series[index]?.pct ?? 0;
    }
    return row;
  });

  return (
    <>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
            {/* Faqat gorizontal to'r — vertikal chiziqlar ma'lumotni bosadi */}
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={AXIS_TICK}
              stroke="var(--axis)"
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 50, 100]}
              tick={AXIS_TICK}
              stroke="var(--axis)"
              width={44}
            />
            <Tooltip
              content={<ChartTooltip suffix="%" />}
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            />
            {people.map((person, index) => (
              <Line
                key={person.key}
                type="monotone"
                dataKey={person.key}
                name={person.name}
                stroke={SERIES_COLORS[index]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <Legend
        items={people.map((person, index) => ({
          color: SERIES_COLORS[index],
          label: person.name,
        }))}
      />

      {stats.partners.length > MAX_SERIES - 1 && (
        <p className="small muted" style={{ marginTop: 6 }}>
          Grafikda birinchi {MAX_SERIES} kishi ko'rsatilgan — ko'proq chiziq
          rang ko'rligida ajratilmay qoladi. Qolganlari reyting jadvalida.
        </p>
      )}
    </>
  );
}

// ─── Sabablar ──────────────────────────────────────────────────────────────

export function ReasonsChart({ reasons }: { reasons: StatsView["reasons"] }) {
  if (!reasons.length) {
    return <p className="empty">Bajarilmagan ish yo'q — yoki sabab ko'rsatilmagan.</p>;
  }

  const data = reasons.map((r) => ({ label: r.label, count: r.count }));
  const height = Math.max(120, data.length * 38);

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 30, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" horizontal={false} />
          <XAxis type="number" tick={AXIS_TICK} stroke="var(--axis)" allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="label"
            tick={AXIS_TICK}
            stroke="var(--axis)"
            width={112}
          />
          <Tooltip content={<ChartTooltip suffix=" marta" />} cursor={{ fill: "var(--grid)" }} />
          {/* Bitta o'lchov — bitta rang. Rang bu yerda hech narsani ajratmaydi,
              shuning uchun kategoriyali slot 1 dan boshqasi kerak emas. */}
          <Bar
            dataKey="count"
            name="Marta"
            fill="var(--series-1)"
            radius={[0, 4, 4, 0]}
            barSize={18}
            label={{ position: "right", fill: "var(--text-dim)", fontSize: 11 }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Odat × kun issiqlik xaritasi ──────────────────────────────────────────

const CELL_CLASS: Record<string, string> = {
  done: "cell cell--done",
  missed: "cell cell--missed",
  skipped: "cell cell--skipped",
};

const CELL_LABEL: Record<string, string> = {
  done: "bajarildi",
  missed: "bajarilmadi",
  skipped: "o'tkazildi",
};

export function HabitHeatmap({ matrix }: { matrix: StatsView["habit_matrix"] }) {
  if (!matrix.habits.length) {
    return <p className="empty">Hali odat qo'shilmagan.</p>;
  }

  return (
    <>
      <div className="heatmap">
        <div
          className="heatmap__grid"
          style={{
            gridTemplateColumns: `auto repeat(${matrix.dates.length}, 13px)`,
          }}
        >
          {matrix.habits.map((habit) => (
            <div key={habit.id} style={{ display: "contents" }}>
              <div className="heatmap__label" title={habit.title}>
                {habit.icon}{" "}
                {habit.title.length > 12 ? `${habit.title.slice(0, 11)}…` : habit.title}
              </div>
              {habit.cells.map((cell, index) => (
                <div
                  key={index}
                  className={cell ? CELL_CLASS[cell] : "cell"}
                  title={`${matrix.dates[index]} — ${
                    cell ? CELL_LABEL[cell] ?? cell : "reja yo'q"
                  }`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Rang yolg'iz o'zi ma'no tashimaydi: to'ldirilgan / halqa / bo'sh */}
      <div className="legend">
        <span className="legend__item">
          <span className="cell cell--done" /> bajarildi
        </span>
        <span className="legend__item">
          <span className="cell cell--missed" /> bajarilmadi
        </span>
        <span className="legend__item">
          <span className="cell" /> reja yo'q
        </span>
      </div>
    </>
  );
}

// ─── Jadval ko'rinishi (grafikka muqobil) ──────────────────────────────────

export function SeriesTable({ series }: { series: SeriesPoint[] }) {
  const rows = [...series].reverse().slice(0, 14);
  return (
    <table>
      <thead>
        <tr>
          <th>Sana</th>
          <th className="num">Reja</th>
          <th className="num">Bajarildi</th>
          <th className="num">%</th>
          <th className="num">Ball</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.date}>
            <td>{shortDate(row.date)}</td>
            <td className="num">{row.planned}</td>
            <td className="num">{row.done}</td>
            <td className="num">{row.pct}%</td>
            <td className="num">{row.score}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
