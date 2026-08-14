import { useEffect, useState } from "react";

import { api, type DayView, type Task } from "../api";
import { Card, ErrorBox, Loading, TaskComposer, TaskRow, TimeEditor } from "../components/ui";
import { useAsync } from "../hooks";
import { alertUser, inTelegram, notify, showMainButton } from "../telegram";

export default function Tomorrow() {
  const day = useAsync<DayView>(() => api.day("tomorrow"), []);
  const [editing, setEditing] = useState<number | null>(null);

  const view = day.data;
  const submitted = view?.submitted ?? false;

  // Telegram'ning pastdagi katta tugmasi — tasdiqlash uchun eng qulay joy
  useEffect(() => {
    if (!view || submitted) return;
    return showMainButton("Rejani tasdiqlash", () => {
      void submit();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view?.date, submitted, view?.planned_count]);

  if (day.loading && !view) return <Loading />;
  if (day.error) return <ErrorBox message={day.error} onRetry={day.reload} />;
  if (!view) return null;

  async function addTask(title: string, start: string, end: string) {
    try {
      day.setData(await api.addTask("tomorrow", title, { start_time: start, end_time: end }));
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

      {submitted ? (
        <div className="chip" style={{ alignSelf: "flex-start" }}>
          ✅ Reja tasdiqlangan
        </div>
      ) : (
        <div className="error">
          Reja hali tasdiqlanmagan. Tasdiqlamasangiz, sherigingizga
          «hali reja kiritmadi» degan xabar boradi.
        </div>
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

      <Card title="Qo'shimcha vazifa">
        <TaskComposer placeholder="Masalan: hisobotni tugatish" onAdd={addTask} />
        <p className="small muted" style={{ marginTop: 8 }}>
          ⏱ bilan vaqt belgilasangiz, boshlanishidan oldin eslatma keladi.
        </p>
      </Card>

      {/* Telegram'dan tashqarida MainButton yo'q — oddiy tugma kerak */}
      {!inTelegram && !submitted && (
        <button className="btn btn--block" onClick={() => void submit()}>
          Rejani tasdiqlash
        </button>
      )}
    </div>
  );
}
