import { api, type DayView, type Me, type Task } from "../api";
import { Card, ErrorBox, Loading, ProgressBar, TaskRow, Tiles } from "../components/ui";
import { useAsync, useRoute } from "../hooks";
import { notify } from "../telegram";

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

  return (
    <div className="page">
      <h1>Bugun</h1>

      {alone && (
        <Card>
          <div className="row row--between" style={{ gap: 10 }}>
            <span className="spread">
              <strong>Sherigingiz yo'q</strong>
              <div className="small muted">
                Ilovaning asosiy kuchi — sherik ko'rib turishida.
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

      {view.tasks.length === 0 ? (
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
        <section className="card card--tight">
          {view.tasks.map((task) => (
            <TaskRow key={task.id} task={task} onToggle={toggle} readonly={view.closed} />
          ))}
        </section>
      )}

      {!view.closed && view.tasks.length > 0 && (
        <button className="btn btn--ghost btn--block" onClick={() => navigate("tomorrow")}>
          🌙 Ertangi rejani tayyorlash
        </button>
      )}
    </div>
  );
}
