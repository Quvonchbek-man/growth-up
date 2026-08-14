import { useState } from "react";

import { api, type Habit, type Me, type Visibility } from "../api";
import { Card, ErrorBox, Loading } from "../components/ui";
import { useAsync } from "../hooks";
import { alertUser, notify } from "../telegram";

const WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];

const VISIBILITY_OPTIONS: { value: Visibility; label: string; hint: string }[] = [
  { value: "public", label: "Ochiq", hint: "Sherik nomini ham, holatini ham ko'radi" },
  { value: "stats_only", label: "Faqat foiz", hint: "Nomi yashirin, foizga qo'shiladi" },
  { value: "private", label: "Yashirin", hint: "Sherik ko'rmaydi, reytingga kirmaydi" },
];

const EMPTY_HABIT: Partial<Habit> = {
  title: "",
  icon: "✅",
  points: 1,
  visibility: "public",
  schedule_kind: "daily",
  weekdays_mask: 127,
  start_time: null,
  end_time: null,
};

/**
 * Yangi odam uchun namunalar. Ular **avtomatik yaratilmaydi** — ko'rinadi,
 * odam o'zi tanlab qo'shadi.
 *
 * Nega avtomatik emas: o'zi tanlamagan 6 ta odat bilan boshlagan odam
 * birinchi kuniyoq yarmini bajarolmaydi, foiz past chiqadi va streak
 * uziladi. Ilova uni hech qachon va'da bermagan ishi uchun jazolagan
 * bo'lardi — sherigi esa buni ko'rib turadi.
 */
const NAMUNA_ODATLAR: Partial<Habit>[] = (
  [
    { title: "Ertalabki sport", icon: "🏃", points: 3, visibility: "public" },
    { title: "30 daqiqa kitob", icon: "📖", points: 2, visibility: "public" },
    { title: "Ingliz tili", icon: "🇬🇧", points: 2, visibility: "public" },
    { title: "2 litr suv", icon: "💧", points: 1, visibility: "public" },
    { title: "Erta yotish", icon: "🌙", points: 2, visibility: "stats_only" },
    { title: "Meditatsiya", icon: "🧘", points: 1, visibility: "private" },
  ] satisfies Partial<Habit>[]
).map((h) => ({ ...h, schedule_kind: "daily" as const, weekdays_mask: 127 }));

export default function Habits() {
  const habits = useAsync<Habit[]>(() => api.habits(), []);
  const me = useAsync<Me>(() => api.me(), []);
  const [draft, setDraft] = useState<Partial<Habit> | null>(null);
  // Qo'shilgani ro'yxatdan chiqadi; `null` — bo'lim yopilgan
  const [namunalar, setNamunalar] = useState<Partial<Habit>[] | null>(NAMUNA_ODATLAR);
  const [busy, setBusy] = useState(false);

  if (habits.loading && !habits.data) return <Loading />;
  if (habits.error) return <ErrorBox message={habits.error} onRetry={habits.reload} />;

  const list = habits.data ?? [];

  async function saveHabit() {
    if (!draft?.title?.trim()) return;
    try {
      if (draft.id) await api.updateHabit(draft.id, draft);
      else await api.createHabit(draft);
      setDraft(null);
      habits.reload();
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Saqlanmadi");
    }
  }

  async function namunaQosh(namuna: Partial<Habit>) {
    if (busy) return;
    setBusy(true);
    try {
      await api.createHabit(namuna);
      setNamunalar((oldingi) => {
        const qolgan = (oldingi ?? []).filter((n) => n.title !== namuna.title);
        return qolgan.length ? qolgan : null;
      });
      habits.reload();
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Qo'shilmadi");
    } finally {
      setBusy(false);
    }
  }

  async function hammasiniQosh() {
    if (busy || !namunalar) return;
    setBusy(true);
    try {
      for (const namuna of namunalar) {
        await api.createHabit(namuna);
      }
      setNamunalar(null);
      habits.reload();
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Qo'shilmadi");
      habits.reload();
    } finally {
      setBusy(false);
    }
  }

  async function archive(habit: Habit) {
    try {
      await api.archiveHabit(habit.id);
      habits.reload();
    } catch {
      notify("error");
    }
  }

  return (
    <div className="page">
      <h1>Odatlar</h1>
      <p className="small muted" style={{ marginTop: -8 }}>
        Har kuni takrorlanadigan ishlaringiz. Kunlik ro'yxatga o'zi qo'shiladi.
      </p>

      <section className="card card--tight">
        {list.map((habit) => (
          <div className="task" key={habit.id} style={{ cursor: "default" }}>
            <span style={{ fontSize: 19 }}>{habit.icon}</span>
            <span className="task__title">
              {habit.start_time && (
                <span className="task__time">
                  {habit.end_time ? `${habit.start_time}–${habit.end_time}` : habit.start_time}
                </span>
              )}
              {habit.title}
              <span className="small muted">
                {" "}
                · {habit.points} ball ·{" "}
                {habit.schedule_kind === "daily" ? "har kuni" : maskLabel(habit.weekdays_mask)}
                {habit.visibility !== "public" && (
                  <> · {habit.visibility === "private" ? "yashirin" : "faqat foiz"}</>
                )}
              </span>
            </span>
            <button className="btn btn--small btn--ghost" onClick={() => setDraft({ ...habit })}>
              ✏️
            </button>
            <button className="btn btn--small btn--danger" onClick={() => void archive(habit)}>
              🗑
            </button>
          </div>
        ))}

        {list.length === 0 && <p className="empty">Hali odat yo'q. Birinchisini qo'shing.</p>}
      </section>

      {/* Namunalar faqat ro'yxat bo'sh bo'lganda: nima yozish mumkinligini
          ko'rsatadi, lekin tanlashni odamning o'ziga qoldiradi */}
      {list.length === 0 && namunalar && (
        <Card title="Namuna odatlar">
          <p className="small muted" style={{ marginTop: 0 }}>
            Boshlash uchun namunalar. Kerakligini bosing — keyin nomini ham,
            ballini ham o'zgartirsangiz bo'ladi.
          </p>

          {namunalar.map((namuna) => (
            <div className="task" key={namuna.title} style={{ cursor: "default" }}>
              <span style={{ fontSize: 19 }}>{namuna.icon}</span>
              <span className="task__title">
                {namuna.title}
                <span className="small muted">
                  {" "}
                  · {namuna.points} ball
                  {namuna.visibility !== "public" && (
                    <> · {namuna.visibility === "private" ? "yashirin" : "faqat foiz"}</>
                  )}
                </span>
              </span>
              <button
                className="btn btn--small"
                onClick={() => void namunaQosh(namuna)}
                disabled={busy}
              >
                + Qo'shish
              </button>
            </div>
          ))}

          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn spread" onClick={() => void hammasiniQosh()} disabled={busy}>
              Hammasini qo'shish
            </button>
            <button className="btn btn--ghost" onClick={() => setNamunalar(null)} disabled={busy}>
              Kerak emas
            </button>
          </div>
        </Card>
      )}

      {!draft && (
        <button className="btn btn--block" onClick={() => setDraft({ ...EMPTY_HABIT })}>
          + Odat qo'shish
        </button>
      )}

      {draft && (
        <Card title={draft.id ? "Odatni tahrirlash" : "Yangi odat"}>
          <div className="row" style={{ marginBottom: 10 }}>
            <input
              type="text"
              style={{ width: 58, textAlign: "center" }}
              value={draft.icon ?? ""}
              onChange={(event) => setDraft({ ...draft, icon: event.target.value.slice(0, 2) })}
            />
            <input
              type="text"
              placeholder="Odat nomi"
              value={draft.title ?? ""}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
          </div>

          <label className="row row--between" style={{ marginBottom: 10 }}>
            <span className="small">Ball (og'irligi)</span>
            <input
              type="number"
              min={1}
              max={10}
              style={{ width: 80 }}
              value={draft.points ?? 1}
              onChange={(event) => setDraft({ ...draft, points: Number(event.target.value) })}
            />
          </label>

          {/* Vaqt shu yerda — odatga qo'yilsa, har kungi nusxaga o'zi
              ko'chadi va eslatma o'z-o'zidan ishlaydi */}
          <div style={{ marginBottom: 10 }}>
            <div className="small muted" style={{ marginBottom: 6 }}>
              Vaqt oralig'i (ixtiyoriy) — belgilansa, eslatma keladi
            </div>
            <div className="row row--times">
              <input
                type="time"
                aria-label="Boshlanish vaqti"
                value={draft.start_time ?? ""}
                onChange={(event) =>
                  setDraft({ ...draft, start_time: event.target.value || null })
                }
              />
              <span className="muted">–</span>
              <input
                type="time"
                aria-label="Tugash vaqti"
                value={draft.end_time ?? ""}
                onChange={(event) => setDraft({ ...draft, end_time: event.target.value || null })}
              />
            </div>
          </div>

          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <button
              className={`btn btn--small ${draft.schedule_kind === "daily" ? "" : "btn--ghost"}`}
              onClick={() => setDraft({ ...draft, schedule_kind: "daily", weekdays_mask: 127 })}
            >
              Har kuni
            </button>
            <button
              className={`btn btn--small ${draft.schedule_kind === "weekdays" ? "" : "btn--ghost"}`}
              onClick={() => setDraft({ ...draft, schedule_kind: "weekdays" })}
            >
              Tanlangan kunlar
            </button>
          </div>

          {draft.schedule_kind === "weekdays" && (
            <div className="row" style={{ gap: 5, marginBottom: 10, flexWrap: "wrap" }}>
              {WEEKDAYS.map((name, index) => {
                const bit = 1 << index;
                const on = ((draft.weekdays_mask ?? 0) & bit) !== 0;
                return (
                  <button
                    key={name}
                    className={`btn btn--small ${on ? "" : "btn--ghost"}`}
                    onClick={() =>
                      setDraft({
                        ...draft,
                        weekdays_mask: on
                          ? (draft.weekdays_mask ?? 0) & ~bit
                          : (draft.weekdays_mask ?? 0) | bit,
                      })
                    }
                  >
                    {name}
                  </button>
                );
              })}
            </div>
          )}

          <div style={{ marginBottom: 12 }}>
            <div className="small muted" style={{ marginBottom: 6 }}>
              Sherik nimani ko'radi
            </div>
            {VISIBILITY_OPTIONS.map((option) => (
              <label
                key={option.value}
                className="row"
                style={{ alignItems: "flex-start", marginBottom: 6 }}
              >
                <input
                  type="radio"
                  name="visibility"
                  checked={draft.visibility === option.value}
                  onChange={() => setDraft({ ...draft, visibility: option.value })}
                  style={{ width: "auto", marginTop: 3 }}
                />
                <span>
                  {option.label}
                  <div className="small muted">{option.hint}</div>
                </span>
              </label>
            ))}
          </div>

          <div className="row">
            <button
              className="btn spread"
              onClick={() => void saveHabit()}
              disabled={
                !draft.title?.trim() || (draft.schedule_kind === "weekdays" && !draft.weekdays_mask)
              }
            >
              Saqlash
            </button>
            <button className="btn btn--ghost" onClick={() => setDraft(null)}>
              Bekor
            </button>
          </div>
        </Card>
      )}

      {me.data && (
        <p className="small muted" style={{ textAlign: "center" }}>
          Kun {me.data.streak_success_pct}% bajarilsa, streak uzilmaydi.
        </p>
      )}
    </div>
  );
}

function maskLabel(mask: number): string {
  return WEEKDAYS.filter((_, index) => (mask & (1 << index)) !== 0).join(", ") || "hech qachon";
}
