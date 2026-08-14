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
};

export default function Habits() {
  const habits = useAsync<Habit[]>(() => api.habits(), []);
  const me = useAsync<Me>(() => api.me(), []);
  const [draft, setDraft] = useState<Partial<Habit> | null>(null);

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
