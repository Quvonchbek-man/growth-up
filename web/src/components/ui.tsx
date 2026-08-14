/** Kichik takrorlanuvchi bo'laklar. */

import type { ReactNode } from "react";

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

export function TaskRow({
  task,
  onToggle,
  onDelete,
  readonly = false,
}: {
  task: Task;
  onToggle?: (task: Task) => void;
  onDelete?: (task: Task) => void;
  readonly?: boolean;
}) {
  const done = task.status === "done";
  const missed = task.status === "missed";
  const mark = VISIBILITY_MARK[task.visibility];

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
        {task.title} {mark && <span title="Maxfiylik">{mark}</span>}
      </span>

      <span className="task__meta">{task.points} ball</span>

      {onDelete && !readonly && (
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
