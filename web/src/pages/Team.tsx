import { useState } from "react";

import { api, type PartnerCard, type TeamView } from "../api";
import { SERIES_COLORS } from "../components/charts";
import { Card, ErrorBox, Loading, ProgressBar, TaskRow } from "../components/ui";
import { useAsync } from "../hooks";
import { alertUser, haptic, notify } from "../telegram";

const REACTIONS = ["👍", "🔥", "💪", "👏"];

export default function Team() {
  const team = useAsync<TeamView>(() => api.team(), []);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  if (team.loading && !team.data) return <Loading />;
  if (team.error) return <ErrorBox message={team.error} onRetry={team.reload} />;
  if (!team.data) return null;

  const view = team.data;
  const alone = view.partners.length === 0;

  async function join() {
    if (!code.trim() || busy) return;
    setBusy(true);
    try {
      await api.join(code.trim().toUpperCase());
      setCode("");
      team.reload();
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Qo'shilib bo'lmadi");
    } finally {
      setBusy(false);
    }
  }

  // Jamoani boshqarish (nom, kod, a'zoni chiqarish) ⚙️ sozlamalarga
  // ko'chdi — bu sahifada faqat kunlik amallar qoldi.

  async function nudge(partner: PartnerCard) {
    haptic("medium");
    try {
      await api.nudge(partner.user_id);
      notify("success");
      alertUser(`${partner.name} ga turtki yuborildi 👉`);
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Yuborilmadi");
    }
  }

  async function react(partner: PartnerCard, emoji: string) {
    haptic();
    try {
      await api.react(partner.user_id, emoji);
      notify("success");
    } catch {
      notify("error");
    }
  }

  // Sherigi yo'q odamga jamoa sahifasining o'rniga chaqiruv ekrani. Unga
  // reyting ham, o'z kartochkasi ham kerak emas — bitta vazifa bor: sherik
  // topish. Ilovaning butun qiymati shunga bog'liq.
  if (alone) {
    return <Invite view={view} code={code} setCode={setCode} busy={busy} onJoin={join} />;
  }

  return (
    <div className="page">
      <h1 style={{ marginBottom: 0 }}>{view.group.name}</h1>
      {/* Nomni o'zgartirish va taklif kodi — ⚙️ sozlamalarda. Bu sahifa
          har kuni ochiladi, ular esa kamdan-kam kerak bo'ladi. */}
      <p className="small muted" style={{ marginTop: -4 }}>
        {view.group.member_count}/{view.group.max_members} kishi
      </p>

      {/* O'zim — har doim 1-rang, sheriklar keyingi ranglarda */}
      <PersonCard
        name="Men"
        color={SERIES_COLORS[0]}
        pct={view.me.today.completion_pct}
        done={view.me.today.done_count}
        planned={view.me.today.planned_count}
        score={view.me.today.score}
        extraDone={view.me.today.extra_done_count}
      />

      {view.partners.map((partner, index) => (
        <div key={partner.user_id}>
          <PersonCard
            name={partner.name}
            color={SERIES_COLORS[Math.min(index + 1, SERIES_COLORS.length - 1)]}
            pct={partner.today.completion_pct}
            done={partner.today.done_count}
            planned={partner.today.planned_count}
            score={partner.today.score}
            streak={partner.streak}
            extraDone={partner.today.extra_done_count}
          />

          <section className="card card--tight" style={{ marginTop: 8 }}>
            {partner.today.tasks.length === 0 ? (
              <p className="empty">Bugunga rejasi ko'rinmayapti.</p>
            ) : (
              partner.today.tasks.map((task) => (
                <TaskRow key={task.id} task={task} readonly />
              ))
            )}
          </section>

          <div className="row" style={{ marginTop: 8, flexWrap: "wrap" }}>
            {REACTIONS.map((emoji) => (
              <button
                key={emoji}
                className="btn btn--small btn--ghost"
                onClick={() => void react(partner, emoji)}
              >
                {emoji}
              </button>
            ))}
            <span className="spread" />
            <button className="btn btn--small" onClick={() => void nudge(partner)}>
              👉 Turtki
            </button>
          </div>

          {!partner.tomorrow_submitted && (
            <p className="small muted" style={{ marginTop: 6 }}>
              ⚠️ {partner.name} ertangi rejani hali kiritmagan.
            </p>
          )}

        </div>
      ))}

      {view.show_ranking && view.leaderboard.length > 1 && (
        <Card title="Bu hafta">
          <table>
            <thead>
              <tr>
                <th style={{ width: 28 }} />
                <th>Kim</th>
                <th className="num">Ball</th>
                <th className="num">Ish</th>
                <th className="num">🔥</th>
              </tr>
            </thead>
            <tbody>
              {view.leaderboard.map((row, index) => (
                <tr key={row.user_id}>
                  <td>
                    <span
                      className="legend__swatch"
                      style={{
                        background:
                          index < SERIES_COLORS.length
                            ? SERIES_COLORS[index]
                            : "var(--ink-muted)",
                        display: "inline-block",
                      }}
                    />
                  </td>
                  <td>
                    {row.rank}. {row.name}
                  </td>
                  <td className="num">
                    <strong>{row.score}</strong>
                  </td>
                  <td className="num">{row.done_count}</td>
                  <td className="num">{row.streak}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted" style={{ marginBottom: 0, marginTop: 8 }}>
            Yashirin vazifalar ballari reytingga kirmaydi.
          </p>
        </Card>
      )}
    </div>
  );
}

/**
 * Sherigi yo'q foydalanuvchi uchun ekran: nima uchun sherik kerakligi va
 * ikkita yo'l — o'zi chaqirish yoki chaqiruvni qabul qilish.
 */
function Invite({
  view,
  code,
  setCode,
  busy,
  onJoin,
}: {
  view: TeamView;
  code: string;
  setCode: (value: string) => void;
  busy: boolean;
  onJoin: () => Promise<void>;
}) {
  const inviteCode = view.group.invite_code;

  return (
    <div className="page">
      <h1>Sherik qo'shing</h1>

      <Card>
        <p style={{ marginTop: 0 }}>
          Bu ilova yolg'iz ishlamaydi. Butun kuchi bitta narsada:{" "}
          <strong>rejangizni boshqa odam ko'rib turadi</strong>.
        </p>
        <p className="small muted" style={{ marginBottom: 0 }}>
          O'zingizga bergan va'dani tashlab yuborish oson. Sherigingiz ko'rib
          turganda esa — yo'q. Shuning uchun birinchi qadam shu.
        </p>
      </Card>

      {inviteCode && (
        <Card title="Sherikni chaqirish">
          <div className="row row--between">
            <span className="code">{inviteCode}</span>
            <button
              className="btn btn--small btn--ghost"
              onClick={() => {
                void navigator.clipboard?.writeText(inviteCode);
                haptic();
                alertUser("Kod nusxalandi");
              }}
            >
              Nusxalash
            </button>
          </div>
          <p className="small muted" style={{ marginTop: 8, marginBottom: 0 }}>
            Shu kodni sherigingizga bering. U botda <code>/qoshil {inviteCode}</code>{" "}
            deb yozsa, jamoangizga qo'shiladi.
          </p>
        </Card>
      )}

      <Card title="Yoki sizni chaqirishgan bo'lsa">
        <p className="small muted" style={{ marginTop: 0 }}>
          Sherigingizning kodini kiriting — uning jamoasiga qo'shilasiz.
        </p>
        <div className="row">
          <input
            type="text"
            value={code}
            placeholder="ABC123"
            maxLength={6}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
          />
          <button className="btn" onClick={() => void onJoin()} disabled={busy || !code.trim()}>
            Qo'shilish
          </button>
        </div>
      </Card>

      <p className="small muted" style={{ textAlign: "center" }}>
        Shu paytgacha odatlaringizni yolg'iz ham yuritishingiz mumkin — streak va
        statistika ishlayveradi.
      </p>
    </div>
  );
}

function PersonCard({
  name,
  color,
  pct,
  done,
  planned,
  score,
  streak,
  extraDone = 0,
}: {
  name: string;
  color: string;
  pct: number;
  done: number;
  planned: number;
  score: number;
  streak?: number;
  extraDone?: number;
}) {
  return (
    <section className="card">
      <div className="row row--between" style={{ marginBottom: 10 }}>
        <span className="row" style={{ gap: 7 }}>
          <span className="legend__swatch" style={{ background: color }} />
          <strong>{name}</strong>
        </span>
        <span className="small muted">
          {done}/{planned}
          {/* Qo'shimcha foizga kirmaydi, lekin ko'rinishi kerak — sherik
              rejadan tashqari ish qilganini bilmasa, adolatsiz tuyuladi */}
          {extraDone > 0 && <> +{extraDone}</>} · {score} ball
          {streak !== undefined ? ` · 🔥 ${streak}` : ""}
        </span>
      </div>
      <ProgressBar pct={pct} />
    </section>
  );
}
