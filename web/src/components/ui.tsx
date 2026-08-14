/** Kichik takrorlanuvchi bo'laklar. */

import { useState, type ReactNode } from "react";

import type { Task } from "../api";
import { haptic } from "../telegram";

export function Loading() {
  return <div className="spinner">Yuklanmoqda…</div>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="page">
      <div className="error">
        {message}
        {onRetry && (
          <div style={{ marginTop: 10 }}>
            <button className="btn btn--small btn--ghost" onClick={onRetry}>
              Qayta urinish
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="card">
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}

export function Tiles({ items }: { items: { value: ReactNode; label: string }[] }) {
  return (
    <div className="tiles">
      {items.map((tile) => (
        <div className="tile" key={tile.label}>
          <div className="tile__value">{tile.value}</div>
          <div className="tile__label">{tile.label}</div>
        </div>
      ))}
    </div>
  );
}

export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="bar__fill" style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
    </div>
  );
}

const VISIBILITY_MARK: Record<string, string> = {
  stats_only: "🔒",
  private: "🙈",
};

/** "07:00–07:45" · "07:00" · "" — serverdagi `clock.fmt_range` bilan bir xil. */
export function timeRange(task: Pick<Task, "start_time" | "end_time">): string {
  if (!task.start_time) return "";
  return task.end_time ? `${task.start_time}–${task.end_time}` : task.start_time;
}

export function TaskRow({
  task,
  onToggle,
  onDelete,
  onEditTime,
  readonly = false,
}: {
  task: Task;
  onToggle?: (task: Task) => void;
  onDelete?: (task: Task) => void;
  onEditTime?: (task: Task) => void;
  readonly?: boolean;
}) {
  const done = task.status === "done";
  const missed = task.status === "missed";
  const mark = VISIBILITY_MARK[task.visibility];
  const span = timeRange(task);

  return (
    <div
      className={`task${done ? " task--done" : ""}`}
      onClick={() => {
        if (readonly || !onToggle) return;
        haptic();
        onToggle(task);
      }}
      style={readonly ? { cursor: "default" } : undefined}
    >
      <div
        className={`task__box${done ? " task__box--done" : ""}${
          missed ? " task__box--missed" : ""
        }`}
      >
        {done ? "✓" : missed ? "✕" : ""}
      </div>

      <span className="task__title">
        {span && <span className="task__time">{span}</span>}
        {task.title} {mark && <span title="Maxfiylik">{mark}</span>}
      </span>

      {/* Qo'shimcha ball bermaydi — "1 ball" yozuvi yolg'on bo'lardi */}
      <span className="task__meta">{task.is_extra ? "qo'shimcha" : `${task.points} ball`}</span>

      {/* Tugmalar `readonly` ga bog'liq emas: `readonly` faqat ✅ bosishni
          taqiqlaydi (ertangi kunni bugundan bajarib bo'lmaydi), lekin
          vaqtni tahrirlash va o'chirish o'shanda ham kerak. */}
      {onEditTime && (
        <button
          className="btn btn--small btn--ghost"
          onClick={(event) => {
            event.stopPropagation();
            onEditTime(task);
          }}
          aria-label="Vaqtni o'zgartirish"
        >
          ⏱
        </button>
      )}

      {onDelete && (
        <button
          className="btn btn--small btn--ghost"
          onClick={(event) => {
            event.stopPropagation();
            onDelete(task);
          }}
          aria-label="O'chirish"
        >
          ✕
        </button>
      )}
    </div>
  );
}

/** Vazifa qatori ostida ochiladigan vaqt tahriri. */
export function TimeEditor({
  task,
  onSave,
  onCancel,
}: {
  task: Task;
  onSave: (start: string, end: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [start, setStart] = useState(task.start_time ?? "");
  const [end, setEnd] = useState(task.end_time ?? "");
  const [busy, setBusy] = useState(false);

  async function save(nextStart: string, nextEnd: string) {
    setBusy(true);
    try {
      await onSave(nextStart, nextEnd);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="row row--times">
      <input
        type="time"
        value={start}
        aria-label="Boshlanish vaqti"
        onChange={(event) => setStart(event.target.value)}
      />
      <span className="muted">–</span>
      <input
        type="time"
        value={end}
        aria-label="Tugash vaqti"
        onChange={(event) => setEnd(event.target.value)}
      />
      <button className="btn btn--small" disabled={busy} onClick={() => void save(start, end)}>
        Saqlash
      </button>
      <button
        className="btn btn--small btn--ghost"
        disabled={busy}
        onClick={() => void save("", "")}
        title="Vaqtni olib tashlash"
      >
        ✕
      </button>
      <button className="btn btn--small btn--ghost" disabled={busy} onClick={onCancel}>
        Bekor
      </button>
    </div>
  );
}

/**
 * Vazifa kiritish qatori — «Ertaga» va «Bugun» ekranlarida bir xil.
 *
 * Vaqt maydonlari ATAYLAB yashirin turadi va ⏱ bilan ochiladi: kechqurun
 * reja kiritish eng nozik qadam, har qo'shimcha maydon reja kiritilmay
 * qolish ehtimolini oshiradi. Vaqt kerak bo'lganda bir bosish yetadi.
 */
export function TaskComposer({
  placeholder,
  onAdd,
  disabled = false,
}: {
  placeholder: string;
  onAdd: (title: string, start: string, end: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [withTime, setWithTime] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const text = title.trim();
    if (!text || busy || disabled) return;
    setBusy(true);
    try {
      await onAdd(text, withTime ? start : "", withTime ? end : "");
      setTitle("");
      setStart("");
      setEnd("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="composer">
      <div className="row">
        <input
          type="text"
          value={title}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(event) => setTitle(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void submit();
          }}
        />
        <button
          className={`btn btn--small${withTime ? "" : " btn--ghost"}`}
          onClick={() => setWithTime((v) => !v)}
          aria-label="Vaqt belgilash"
          title="Vaqt belgilash"
        >
          ⏱
        </button>
        <button
          className="btn"
          onClick={() => void submit()}
          disabled={busy || disabled || !title.trim()}
        >
          +
        </button>
      </div>

      {withTime && (
        <div className="row row--times">
          <input
            type="time"
            value={start}
            aria-label="Boshlanish vaqti"
            onChange={(event) => setStart(event.target.value)}
          />
          <span className="muted">–</span>
          <input
            type="time"
            value={end}
            aria-label="Tugash vaqti"
            onChange={(event) => setEnd(event.target.value)}
          />
        </div>
      )}
    </div>
  );
}

/** Grafik ostidagi izoh — 2 va undan ko'p qator bo'lsa majburiy. */
export function Legend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div className="legend">
      {items.map((item) => (
        <span className="legend__item" key={item.label}>
          <span className="legend__swatch" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}
