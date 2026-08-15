import { api, type DayView, type Me, type Task } from "../api";
import {
  Card,
  ErrorBox,
  Loading,
  ProgressBar,
  TaskComposer,
  TaskRow,
  Tiles,
} from "../components/ui";
import { useAsync, useRoute } from "../hooks";
import { alertUser, notify } from "../telegram";

export default function Today() {
  const day = useAsync<DayView>(() => api.day("today"), []);
  const me = useAsync<Me>(() => api.me(), []);
  const [, navigate] = useRoute();

  // Sherigi yo'q odam ilovaning yarmini ishlatmayapti — birinchi ekrandan
  // yo'l ko'rsatamiz. Majburlamaymiz: odatlar yolg'iz ham ishlaydi.
  const alone = me.data?.group != null && me.data.group.partner_count === 0;

  if (day.loading && !day.data) return <Loading />;
  if (day.error) return <ErrorBox message={day.error} onRetry={day.reload} />;
  if (!day.data) return null;

  const view = day.data;
  // Reja — kechqurun berilgan va'da, qo'shimcha — kun ichida qo'shilgani.
  // Ular ataylab alohida ro'yxatda: aralashtirilsa "bu ish rejada bormidi"
  // degan savolga javob yo'qoladi va foizning nega o'zgarmagani tushunarsiz
  // bo'lib qoladi.
  const plan = view.tasks.filter((t) => !t.is_extra);
  const extras = view.tasks.filter((t) => t.is_extra);

  async function toggle(task: Task) {
    const next = task.status === "done" ? "planned" : "done";
    try {
      const updated = await api.setStatus(task.id, next);
      day.setData(updated);
      if (next === "done") notify("success");
    } catch {
      notify("error");
      day.reload();
    }
  }

  async function addExtra(title: string, start: string, end: string) {
    try {
      day.setData(await api.addTask("today", title, { start_time: start, end_time: end }));
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Qo'shib bo'lmadi");
    }
  }

  async function removeExtra(task: Task) {
    try {
      await api.deleteTask(task.id);
      day.setData(await api.day("today"));
    } catch {
      day.reload();
    }
  }

  return (
    <div className="page">
      <h1>Bugun</h1>

      {alone && (
        <Card>
          <div className="row row--between" style={{ gap: 10 }}>
            <span className="spread">
              <strong>Do'stingiz yo'q</strong>
              <div className="small muted">
                Ilovaning asosiy kuchi — do'stingiz ko'rib turishida.
              </div>
            </span>
            <button className="btn btn--small" onClick={() => navigate("team")}>
              Qo'shish
            </button>
          </div>
        </Card>
      )}

      <Tiles
        items={[
          { value: `${view.completion_pct}%`, label: "bajarildi" },
          { value: view.score, label: "ball" },
          { value: `🔥 ${view.streak ?? 0}`, label: "kun ketma-ket" },
        ]}
      />

      <Card>
        <div className="row row--between" style={{ marginBottom: 10 }}>
          <span className="small muted">
            {view.done_count} / {view.planned_count} ish
          </span>
          {view.closed && <span className="chip">Kun yopilgan</span>}
        </div>
        <ProgressBar pct={view.completion_pct} />
      </Card>

      {plan.length === 0 ? (
        <Card>
          <p className="empty">
            Bugunga reja yo'q.
            <br />
            <br />
            Kechqurun ertangi kunni yozib qo'yish — butun tizimning kaliti.
          </p>
          <button className="btn btn--block" onClick={() => navigate("tomorrow")}>
            Ertangi rejani tuzish
          </button>
        </Card>
      ) : (
        <>
          <h2 className="section">Reja</h2>
          <section className="card card--tight">
            {plan.map((task) => (
              <TaskRow key={task.id} task={task} onToggle={toggle} readonly={view.closed} />
            ))}
          </section>
        </>
      )}

      {/* Qo'shimcha bo'limi. Kun yopilgach faqat ro'yxat qoladi. */}
      {(extras.length > 0 || !view.closed) && (
        <>
          <h2 className="section">
            Qo'shimcha
            {extras.length > 0 && (
              <span className="section__meta">
                {view.extra_done_count} / {view.extra_count}
              </span>
            )}
          </h2>

          {extras.length > 0 && (
            <section className="card card--tight">
              {extras.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onToggle={toggle}
                  onDelete={view.closed ? undefined : removeExtra}
                  readonly={view.closed}
                />
              ))}
            </section>
          )}

          {!view.closed && (
            <Card>
              <TaskComposer placeholder="Bugun yana nima chiqdi?" onAdd={addExtra} />
              <p className="small muted" style={{ marginTop: 8 }}>
                Qo'shimcha foizga ham, ballga ham kirmaydi — reja kechqurun
                berilgan va'da, bu esa uning ustiga qilgan ishingiz.
              </p>
            </Card>
          )}
        </>
      )}

      {!view.closed && plan.length > 0 && (
        <button className="btn btn--ghost btn--block" onClick={() => navigate("tomorrow")}>
          🌙 Ertangi rejani tayyorlash
        </button>
      )}
    </div>
  );
}
