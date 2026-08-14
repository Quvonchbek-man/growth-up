import { useEffect, useState } from "react";

import { api, type Me } from "../api";
import { Card, ErrorBox, Loading } from "../components/ui";
import { useAsync, useRoute } from "../hooks";
import { alertUser, confirmUser, haptic, notify, showBackButton } from "../telegram";

/**
 * Sozlamalar — tab emas, yaxlit oyna: har sahifadagi ⚙️ tugmasi ochadi.
 *
 * Nega ajratilgan: odatlar ilovaning o'zagi, eslatma vaqti esa bir marta
 * qo'yiladigan narsa. Bir sahifada tursa, odat "sozlama" darajasiga tushadi.
 */
export default function Settings({ onClose }: { onClose: () => void }) {
  const me = useAsync<Me>(() => api.me(), []);
  const [, navigate] = useRoute();
  // null — nom tahrirlanmayapti; satr — kiritilayotgan yangi nom
  const [draftName, setDraftName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Telegram'ning o'z «orqaga» tugmasi — oynani yopish uchun tabiiy joy
  useEffect(() => showBackButton(onClose), [onClose]);

  async function save(patch: Partial<Me>) {
    try {
      me.setData(await api.updateMe(patch));
      haptic();
    } catch (error) {
      alertUser(error instanceof Error ? error.message : "Saqlanmadi");
      me.reload();
    }
  }

  // ─── Sardor amallari ─────────────────────────────────────────────────────
  // Nomi ham, kodi ham kamdan-kam tegiladigan narsalar — shuning uchun
  // Jamoa sahifasida emas, shu yerda.

  async function saveName() {
    const name = draftName?.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      await api.renameTeam(name);
      setDraftName(null);
      me.reload();
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Nom saqlanmadi");
    } finally {
      setBusy(false);
    }
  }

  async function resetCode() {
    const ok = await confirmUser(
      "Yangi kod berilsa, eskisi darhol ishlamay qoladi. Davom etamizmi?",
    );
    if (!ok) return;
    setBusy(true);
    try {
      await api.resetCode();
      me.reload();
      notify("success");
      alertUser("Yangi taklif kodi tayyor.");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Kod yangilanmadi");
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(id: number, name: string) {
    const ok = await confirmUser(
      `${name} jamoadan chiqarilsinmi?\n\n` +
        "Unga bu haqda xabar boradi. Uning rejalari va statistikasi o'chmaydi, " +
        "lekin sizga ko'rinmay qoladi. Qaytib kirmasligi uchun taklif kodini " +
        "ham yangilang.",
    );
    if (!ok) return;
    setBusy(true);
    try {
      await api.removeMember(id);
      me.reload();
      notify("success");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Chiqarib bo'lmadi");
    } finally {
      setBusy(false);
    }
  }

  /**
   * Jamoadan chiqish. Ilovaning butun kuchi sherik ko'rib turishida —
   * shuning uchun bu tugma tasdiqsiz ishlamaydi va jim ketib bo'lmaydi:
   * qolganlarga bot xabar yuboradi.
   */
  async function leave() {
    const group = me.data?.group;
    if (!group) return;

    const ok = await confirmUser(
      `«${group.name}» jamoasidan chiqasizmi?\n\n` +
        (group.is_owner ? "Sardorlik jamoadagi eng eski a'zoga o'tadi.\n" : "") +
        "Sherigingizga xabar boradi. Rejalaringiz, odatlaringiz va statistikangiz " +
        "saqlanib qoladi, lekin qaytish uchun yangi taklif kodi kerak bo'ladi.",
    );
    if (!ok) return;

    try {
      await api.leaveTeam();
      notify("success");
      navigate("team");
    } catch (error) {
      notify("error");
      alertUser(error instanceof Error ? error.message : "Chiqib bo'lmadi");
    }
  }

  const profile = me.data;

  return (
    <div className="page">
      <div className="sheet__head">
        <button className="iconbtn" onClick={onClose} aria-label="Yopish">
          ✕
        </button>
        <h1>Sozlamalar</h1>
      </div>

      {me.loading && !profile && <Loading />}
      {me.error && <ErrorBox message={me.error} onRetry={me.reload} />}

      {profile && (
        <>
          <Card title="Eslatmalar">
            <label className="row row--between" style={{ marginBottom: 12 }}>
              <span>🌙 Kechki eslatma</span>
              <input
                type="time"
                style={{ width: 130 }}
                value={profile.plan_reminder_at}
                onChange={(event) => void save({ plan_reminder_at: event.target.value })}
              />
            </label>
            <label className="row row--between" style={{ marginBottom: 12 }}>
              <span>☀️ Ertalabki ro'yxat</span>
              <input
                type="time"
                style={{ width: 130 }}
                value={profile.digest_at}
                onChange={(event) => void save({ digest_at: event.target.value })}
              />
            </label>
            <label className="row row--between">
              <span className="spread">
                ⏰ Vazifadan oldin
                <div className="small muted">
                  Vaqti belgilangan ish boshlanishidan necha daqiqa oldin
                  eslatilsin. 0 — o'chirilgan.
                </div>
              </span>
              <input
                type="number"
                min={0}
                max={120}
                step={5}
                style={{ width: 80 }}
                value={profile.task_lead_min}
                onChange={(event) =>
                  void save({ task_lead_min: Number(event.target.value) })
                }
              />
            </label>
          </Card>

          <Card title="Sherik bilan">
            <Toggle
              label="Reja kiritmasam, sherigimga xabar ketsin"
              hint="Ilovaning asosiy kuchi shu bosimda"
              checked={profile.allow_nag_about_me}
              onChange={(value) => void save({ allow_nag_about_me: value })}
            />
            <Toggle
              label="Sherigim bajarmasa menga xabar kelsin"
              checked={profile.notify_about_partner}
              onChange={(value) => void save({ notify_about_partner: value })}
            />
            <Toggle
              label="Reyting jadvalini ko'rsatish"
              hint="O'chirilsa raqobat yo'qoladi, faqat ko'rinish qoladi"
              checked={profile.show_ranking}
              onChange={(value) => void save({ show_ranking: value })}
            />
          </Card>

          {profile.group && (
            <Card title="Jamoa">
              {draftName === null ? (
                <div className="row row--between" style={{ marginBottom: 12 }}>
                  <span className="spread">
                    {profile.group.name}
                    <div className="small muted">
                      {profile.group.partner_count} sherik
                      {profile.group.is_owner && " · siz sardorsiz"}
                    </div>
                  </span>
                  {profile.group.is_owner && (
                    <button
                      className="btn btn--small btn--ghost"
                      onClick={() => {
                        haptic();
                        setDraftName(profile.group!.name);
                      }}
                    >
                      ✏️ Nomi
                    </button>
                  )}
                </div>
              ) : (
                <div className="row" style={{ marginBottom: 12 }}>
                  <input
                    type="text"
                    value={draftName}
                    maxLength={64}
                    autoFocus
                    onChange={(event) => setDraftName(event.target.value)}
                  />
                  <button
                    className="btn btn--small"
                    onClick={() => void saveName()}
                    disabled={busy || !draftName.trim()}
                  >
                    Saqlash
                  </button>
                  <button
                    className="btn btn--small btn--ghost"
                    onClick={() => setDraftName(null)}
                  >
                    Bekor
                  </button>
                </div>
              )}

              {profile.group.is_owner && profile.group.partners.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div className="small muted" style={{ marginBottom: 4 }}>
                    A'zolar
                  </div>
                  {profile.group.partners.map((partner) => (
                    <div className="row row--between" key={partner.user_id}>
                      <span className="spread">{partner.name}</span>
                      <button
                        className="btn btn--small btn--danger"
                        onClick={() => void removeMember(partner.user_id, partner.name)}
                        disabled={busy}
                      >
                        Chiqarish
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {profile.group.invite_code && (
                <>
                  <div className="row row--between">
                    <span className="code">{profile.group.invite_code}</span>
                    <button
                      className="btn btn--small btn--ghost"
                      onClick={() => {
                        void navigator.clipboard?.writeText(
                          profile.group?.invite_code ?? "",
                        );
                        haptic();
                        alertUser("Kod nusxalandi");
                      }}
                    >
                      Nusxalash
                    </button>
                  </div>
                  <p className="small muted" style={{ marginTop: 8 }}>
                    Sherigingiz botda <code>/qoshil {profile.group.invite_code}</code>{" "}
                    deb yozsa qo'shiladi.
                  </p>
                  <button
                    className="btn btn--small btn--ghost"
                    onClick={() => void resetCode()}
                    disabled={busy}
                  >
                    🔄 Kodni yangilash
                  </button>
                </>
              )}

              {/* Yolg'iz odamga ko'rsatilmaydi: chiqib, keyingi ochilishda yana
                  o'ziga jamoa yaratardi — foydasiz tugma */}
              {profile.group.partner_count > 0 && (
                <>
                  <button
                    className="btn btn--block btn--danger"
                    style={{ marginTop: 14 }}
                    onClick={() => void leave()}
                  >
                    Jamoadan chiqish
                  </button>
                  <p className="small muted" style={{ marginBottom: 0 }}>
                    Sherigingizga xabar boradi. Tarixingiz o'chmaydi.
                  </p>
                </>
              )}
            </Card>
          )}

          <p className="small muted" style={{ textAlign: "center" }}>
            Kun {profile.streak_success_pct}% bajarilsa, streak uzilmaydi.
            <br />
            Vaqt mintaqasi: {profile.tz}
          </p>
        </>
      )}
    </div>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="row row--between" style={{ padding: "9px 0", alignItems: "flex-start" }}>
      <span className="spread">
        {label}
        {hint && <div className="small muted">{hint}</div>}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        style={{ width: 22, height: 22, marginTop: 2 }}
      />
    </label>
  );
}
