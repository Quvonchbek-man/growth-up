/**
 * Grafiklar.
 *
 * Rang qoidalari (tekshiruvdan o'tgan palitra, `theme.css` ga qarang):
 *  • Uchtadan ortiq odam bir grafikda ko'rsatilmaydi: to'rtinchi rangdan
 *    boshlab juftliklar rang ko'rligida ajratilmay qoladi.
 *  • Rang **ROLGA** biriktiriladi, shaxsga emas: 1 — men, 2 — eng zo'r
 *    ketayotgan sherik, 3 — o'zim tanlagan odam. Ikkinchi slotdagi odam
 *    kundan kunga o'zgarishi mumkin (kim oldinda bo'lsa — o'sha), ya'ni
 *    rangni odamga bog'lab bo'lmaydi. **Shaxsni izoh (legend) ko'rsatadi**,
 *    shuning uchun izoh ixtiyoriy emas — usiz grafik o'qilmay qoladi.
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

// Uchta slot: men · eng zo'r sherik · tanlangan sherik.
// Chegara `comparePeople()` da amalga oshadi.
export const SERIES_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

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

type PartnerSeries = StatsView["partners"][number];

/** Grafikdagi bitta chiziq. `userId` faqat sheriklarda bo'ladi. */
export interface ComparePerson {
  key: string;
  name: string;
  note?: string;
  userId?: number;
  series: SeriesPoint[];
}

export interface CompareChoice {
  people: ComparePerson[];
  /** Tanlash mumkin bo'lgan sheriklar (eng zo'ri ro'yxatda yo'q) */
  options: PartnerSeries[];
  /** Uchinchi slotda kim turibdi */
  selectedId: number | null;
}

/**
 * Reja bo'lgan kunlarning o'rtacha bajarilish foizi.
 *
 * Bo'sh kunlar (`planned = 0`) hisobga kirmaydi: ilovaga kirmagan kun
 * odamni sun'iy pastga tortmasligi kerak. `Stats.tsx` dagi `avgPct` bilan
 * bir xil qoida.
 */
function avgPct(series: SeriesPoint[]): number {
  const planned = series.filter((point) => point.planned > 0);
  if (!planned.length) return 0;
  return planned.reduce((sum, point) => sum + point.pct, 0) / planned.length;
}

function totalScore(series: SeriesPoint[]): number {
  return series.reduce((sum, point) => sum + point.score, 0);
}

/**
 * Kim grafikka tushishini hal qiladi: **men → eng zo'r → tanlangan**.
 *
 * Nega qo'shilish tartibi emas: 10 kishilik jamoada birinchi ikki sherik
 * bilan taqqoslash tasodifiy raqam beradi. Oldinda ketayotgan odam esa
 * «qayerda turibman» degan savolga javob beradi.
 *
 * Tanlangan odam jamoadan chiqib ketgan bo'lsa (yoki aynan eng zo'r bo'lib
 * qolsa) — ikkinchi o'rindagi odamga tushadi, ya'ni uchinchi chiziq hech
 * qachon bo'sh qolmaydi.
 */
export function comparePeople(
  stats: StatsView,
  selectedId: number | null,
): CompareChoice {
  const me: ComparePerson = { key: "me", name: "Men", series: stats.series };

  // Tenglikda: yuqori ball, keyin ism — tartib barqaror bo'lsin
  const ranked = [...stats.partners].sort((a, b) => {
    const byPct = avgPct(b.series) - avgPct(a.series);
    if (byPct !== 0) return byPct;
    const byScore = totalScore(b.series) - totalScore(a.series);
    if (byScore !== 0) return byScore;
    return a.name.localeCompare(b.name);
  });

  if (!ranked.length) {
    return { people: [me], options: [], selectedId: null };
  }

  const [best, ...rest] = ranked;
  const asPerson = (p: PartnerSeries, note?: string): ComparePerson => ({
    key: `u${p.user_id}`,
    name: p.name,
    note,
    userId: p.user_id,
    series: p.series,
  });

  if (!rest.length) {
    // Yolg'iz sherik — «eng zo'r» deb belgilashning ma'nosi yo'q
    return { people: [me, asPerson(best)], options: [], selectedId: null };
  }

  const chosen = rest.find((p) => p.user_id === selectedId) ?? rest[0];
  return {
    people: [me, asPerson(best, "eng zo'r"), asPerson(chosen)],
    options: rest,
    selectedId: chosen.user_id,
  };
}

export function TrendChart({
  stats,
  selectedId = null,
  onSelect,
}: {
  stats: StatsView;
  selectedId?: number | null;
  onSelect?: (userId: number) => void;
}) {
  const { people, options, selectedId: shownId } = comparePeople(stats, selectedId);

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

      {/* Rang rolga biriktirilgani uchun izoh majburiy — kim qaysi chiziq
          ekanini faqat shu yer aytadi */}
      <Legend
        items={people.map((person, index) => ({
          color: SERIES_COLORS[index],
          label: person.note ? `${person.name} · ${person.note}` : person.name,
        }))}
      />

      {options.length > 1 && onSelect && (
        <label className="row row--between" style={{ marginTop: 10, gap: 10 }}>
          <span className="small muted">Kim bilan taqqoslay?</span>
          <select
            value={shownId ?? ""}
            onChange={(event) => onSelect(Number(event.target.value))}
            style={{ width: "auto", flex: 1, maxWidth: 190 }}
          >
            {options.map((partner) => (
              <option key={partner.user_id} value={partner.user_id}>
                {partner.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {options.length > 0 && (
        <p className="small muted" style={{ marginTop: 6 }}>
          Ikkinchi chiziq — shu davrda eng yaxshi ketayotgan sherigingiz.
          {options.length > 1
            ? " Uchinchisini o'zingiz tanlaysiz."
            : " Uchinchisi — qolgan sherigingiz."}{" "}
          Uchtadan ko'p chiziq bir grafikda ajratilmay qoladi; hammasi reyting
          jadvalida.
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

// ─── A'zolar dinamikasi (admin paneli) ─────────────────────────────────────

export interface MemberPoint {
  date: string;
  total: number;
  active: number;
  joined: number;
  left: number;
}

/**
 * A'zolar dinamikasi — jamg'arma chiziq.
 *
 * Nega ustun emas, chiziq: kunlik qo'shilish ustunlari o'sish qanday
 * ketayotganini ko'rsatmaydi. 10 kishi kelib 9 tasi ketgan kun ham, 10
 * kishi kelib hech kim ketmagan kun ham bir xil ustun beradi. Ikki chiziq
 * orasidagi masofa esa aynan yo'qotishni ko'rsatadi.
 */
export function MembersChart({ points }: { points: MemberPoint[] }) {
  if (!points.length) return <p className="empty">Ma'lumot yo'q.</p>;

  const data = points.map((p) => ({
    date: shortDate(p.date),
    total: p.total,
    active: p.active,
    joined: p.joined,
    left: p.left,
  }));
  const oxirgi = points[points.length - 1];
  const birinchi = points[0];
  const yoqotish = oxirgi.total - oxirgi.active;

  return (
    <>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={AXIS_TICK}
              stroke="var(--axis)"
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              tick={AXIS_TICK}
              stroke="var(--axis)"
              width={44}
              allowDecimals={false}
              domain={[0, "auto"]}
            />
            <Tooltip
              content={<ChartTooltip suffix=" kishi" />}
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            />
            <Line
              type="monotone"
              dataKey="total"
              name="Jami"
              stroke={SERIES_COLORS[0]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
            />
            <Line
              type="monotone"
              dataKey="active"
              name="Faol"
              stroke={SERIES_COLORS[1]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <Legend
        items={[
          { color: SERIES_COLORS[0], label: "Jami ro'yxatdan o'tgan" },
          { color: SERIES_COLORS[1], label: "Faol (bloklamagan)" },
        ]}
      />

      <p className="small muted" style={{ marginTop: 6, marginBottom: 0 }}>
        Davr boshida {birinchi.total} → hozir <strong>{oxirgi.total}</strong> kishi
        {yoqotish > 0 && <> · ikki chiziq orasidagi {yoqotish} — botni bloklaganlar</>}
      </p>
    </>
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
