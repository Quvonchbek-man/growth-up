import { useEffect, useState } from "react";

import { api, type DayView, type Task } from "../api";
import { Card, ErrorBox, Loading, TaskRow } from "../components/ui";
import { useAsync } from "../hooks";
import { alertUser, inTelegram, notify, showMainButton } from "../telegram";

export default function Tomorrow() {
  const day = useAsync<DayView>(() => api.day("tomorrow"), []);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

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

  async function addTask() {
    const text = title.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      day.setData(await api.addTask("tomorrow", text));
      setTitle("");
    } catch (error) {
      alertUser(error instanceof Error ? error.message : "Qo'shib bo'lmadi");
    } finally {
      setBusy(false);
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
            <TaskRow
              key={task.id}
              task={task}
              readonly
              onDelete={task.source === "manual" ? removeTask : undefined}
            />
          ))
        )}
      </section>

      <Card title="Qo'shimcha vazifa">
        <div className="row">
          <input
            type="text"
            value={title}
            placeholder="Masalan: hisobotni tugatish"
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void addTask();
            }}
          />
          <button className="btn" onClick={() => void addTask()} disabled={busy || !title.trim()}>
            +
          </button>
        </div>
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
