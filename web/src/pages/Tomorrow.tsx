import { useState } from "react";

import { api, type DayView, type Habit, type Task } from "../api";
import { Card, ErrorBox, Loading, TaskComposer, TaskRow, TimeEditor } from "../components/ui";
import { useAsync } from "../hooks";
import { alertUser, haptic, notify, popupConfirm } from "../telegram";

export default function Tomorrow() {
  const day = useAsync<DayView>(() => api.day("tomorrow"), []);
  const habits = useAsync<Habit[]>(() => api.habits(), []);
  const [editing, setEditing] = useState<number | null>(null);

  const view = day.data;
  const submitted = view?.submitted ?? false;

  if (day.loading && !view) return <Loading />;
  if (day.error) return <ErrorBox message={day.error} onRetry={day.reload} />;
  if (!view) return null;

  // Ro'yxatda yo'q odatlar = ertangi kunning jadvaliga tushmaganlari
  // (tushganlari server tomonidan o'zi qo'shilgan)
  const inPlan = new Set(view.tasks.map((task) => task.habit_id));
  const offDay = (habits.data ?? []).filter((habit) => !inPlan.has(habit.id));

  async function addTask(title: string, start: string, end: string) {
    try {
      day.setData(await api.addTask("tomorrow", title, { start_time: start, end_time: end }));
    } catch (error) {
      alertUser(error instanceof Error ? error.message : "Qo'shib bo'lmadi");
    }
  }

  async function addHabit(habit: Habit) {
    haptic();
    try {
      day.setData(await api.addHabitTask("tomorrow", habit.id));
    } catch (error) {
      alertUser(error instanceof Error ? error.message : "Qo'shib bo'lmadi");
    }
  }

  async function removeTask(task: Task) {
    try {
      await api.deleteTask(task.id);
      day.setData(await api.day("tomorrow"));
    } catch {
      day.reload();
    }
  }

  async function saveTime(task: Task, start: string, end: string) {
    try {
      day.setData(await api.setTaskTime(task.id, start, end));
      setEditing(null);
    } catch (error) {
      alertUser(error instanceof Error ? error.message : "Vaqtni saqlab bo'lmadi");
    }
  }

  async function submit() {
    // Tasdiq — bexosdan bosishdan yagona himoya: `submitted_at` bir marta
    // qo'yiladi va uni qaytarish yo'li yo'q
    const ok = await popupConfirm(
      "Rejani tasdiqlash",
      "Ertangi kun rejasini tasdiqlashga tayyormisiz?",
      "Ha, ishonchim komil",
      "Yo'q, o'zgartiraman",
    );
    if (!ok) return;

    try {
      day.setData(await api.submitDay("tomorrow"));
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Tasdiqlab bo'lmadi");
    }
  }

  return (
    <div className="page">
      <h1>Ertaga</h1>
      <p className="small muted" style={{ marginTop: -8 }}>
        {view.date} · {view.planned_count} ish · {view.max_score} ball imkoni
      </p>

      {/* Tugma ATAYLAB tepada: pastda turganda tab qatorining ustiga tushib,
          tab bosgan barmoq unga tegib ketardi */}
      {submitted ? (
        <div className="chip" style={{ alignSelf: "flex-start" }}>
          ✅ Reja tasdiqlangan
        </div>
      ) : (
        <>
          <button className="btn btn--block" onClick={() => void submit()}>
            Rejani tasdiqlash
          </button>
          <div className="error">
            Reja hali tasdiqlanmagan. Tasdiqlamasangiz, do'stingizga
            «hali reja kiritmadi» degan xabar boradi.
          </div>
        </>
      )}

      <section className="card card--tight">
        {view.tasks.length === 0 ? (
          <p className="empty">Hali vazifa yo'q. Odatlar avtomatik qo'shiladi.</p>
        ) : (
          view.tasks.map((task) => (
            <div key={task.id}>
              <TaskRow
                task={task}
                readonly
                onEditTime={() => setEditing(editing === task.id ? null : task.id)}
                onDelete={task.source === "manual" ? removeTask : undefined}
              />
              {editing === task.id && (
                <TimeEditor
                  task={task}
                  onSave={(start, end) => saveTime(task, start, end)}
                  onCancel={() => setEditing(null)}
                />
              )}
            </div>
          ))
        )}
      </section>

      {/* Jadvalga kirmagan odatlar: avtomatik qo'shilmaydi, lekin bir bosishda
          qo'shsa bo'ladi — qo'lda qo'shilgani ✕ bilan chiqadi */}
      {offDay.length > 0 && (
        <Card title="Odatlardan qo'shish">
          <p className="small muted" style={{ marginTop: 0 }}>
            Bu kunga rejalashtirilmagan odatlar. Kerak bo'lsa qo'shib qo'ying.
          </p>

          {offDay.map((habit) => (
            <div className="task" key={habit.id} style={{ cursor: "default" }}>
              <span style={{ fontSize: 19 }}>{habit.icon}</span>
              <span className="task__title">
                {habit.start_time && (
                  <span className="task__time">
                    {habit.end_time ? `${habit.start_time}–${habit.end_time}` : habit.start_time}
                  </span>
                )}
                {habit.title}
              </span>
              <span className="task__meta">{habit.points} ball</span>
              <button
                className="btn btn--small"
                onClick={() => void addHabit(habit)}
                aria-label={`${habit.title} — ertangi rejaga qo'shish`}
              >
                +
              </button>
            </div>
          ))}
        </Card>
      )}

      <Card title="Qo'shimcha vazifa">
        <TaskComposer placeholder="Masalan: hisobotni tugatish" onAdd={addTask} />
        <p className="small muted" style={{ marginTop: 8 }}>
          ⏱ bilan vaqt belgilasangiz, boshlanishidan oldin eslatma keladi.
        </p>
      </Card>
    </div>
  );
}
