/**
 * API mijozi.
 *
 * Har so'rovga `X-Init-Data` sarlavhasi qo'shiladi — server imzoni bot
 * tokeni bilan tekshiradi. Token frontend'da hech qachon bo'lmaydi.
 *
 * Manzillar nisbiy (`/api/...`): dev'da Vite proxy, ishlab chiqarishda esa
 * FastAPI o'zi tarqatadi — ikkalasida ham bitta origin, CORS muammosi yo'q.
 */

import { tg } from "./telegram";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": tg?.initData ?? "",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `Xato ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // JSON bo'lmagan javob — standart matn qoladi
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

// ─── Turlar ────────────────────────────────────────────────────────────────

export type TaskStatus = "planned" | "done" | "missed" | "skipped";
export type Visibility = "public" | "stats_only" | "private";

export interface Task {
  id: number;
  title: string;
  hidden: boolean;
  status: TaskStatus;
  source: "habit" | "manual";
  habit_id: number | null;
  points: number;
  visibility: Visibility;
  miss_reason: string | null;
  miss_note: string | null;
  done_at: string | null;
}

export interface DayView {
  date: string;
  submitted: boolean;
  closed: boolean;
  tasks: Task[];
  planned_count: number;
  done_count: number;
  score: number;
  max_score: number;
  completion_pct: number;
  streak?: number;
  best_streak?: number;
}

export interface Habit {
  id: number;
  title: string;
  icon: string;
  schedule_kind: "daily" | "weekdays";
  weekdays_mask: number;
  points: number;
  visibility: Visibility;
  is_archived: boolean;
  sort_order: number;
}

export interface Me {
  /** Jamoa qisqacha — sozlamalardagi «Jamoa» bo'limi shundan quriladi */
  group: {
    name: string;
    partner_count: number;
    is_owner: boolean;
    /** Faqat sardorga keladi */
    invite_code: string | null;
    /** O'zimdan boshqa a'zolar — sozlamalarda chiqarish uchun */
    partners: { user_id: number; name: string }[];
  } | null;
  id: number;
  name: string;
  username: string | null;
  tz: string;
  today: string;
  plan_reminder_at: string;
  digest_at: string;
  allow_nag_about_me: boolean;
  notify_about_partner: boolean;
  show_ranking: boolean;
  streak_success_pct: number;
}

export interface PartnerCard {
  user_id: number;
  name: string;
  username: string | null;
  today: DayView;
  streak: number;
  best_streak: number;
  tomorrow_submitted: boolean;
}

export interface LeaderRow {
  user_id: number;
  name: string;
  score: number;
  done_count: number;
  streak: number;
  rank: number;
}

export interface TeamView {
  group: {
    id: number;
    name: string;
    /** Faqat sardorga keladi, boshqalarga `null`. */
    invite_code: string | null;
    member_count: number;
    max_members: number;
    owner_id: number;
    is_owner: boolean;
  };
  me: { user_id: number; name: string; today: DayView };
  partners: PartnerCard[];
  leaderboard: LeaderRow[];
  show_ranking: boolean;
}

export interface SeriesPoint {
  date: string;
  weekday: number;
  planned: number;
  done: number;
  pct: number;
  score: number;
  submitted: boolean;
}

export interface StatsView {
  days: number;
  streak: number;
  best_streak: number;
  series: SeriesPoint[];
  partners: { user_id: number; name: string; series: SeriesPoint[] }[];
  reasons: { reason: string; label: string; count: number }[];
  habit_matrix: {
    dates: string[];
    habits: { id: number; title: string; icon: string; cells: (string | null)[] }[];
  };
  week: { start: string; leaderboard: LeaderRow[] };
}

// ─── Endpointlar ───────────────────────────────────────────────────────────

export const api = {
  me: () => get<Me>("/me"),
  updateMe: (body: Partial<Me>) => patch<Me>("/me", body),

  day: (day: string) => get<DayView>(`/day/${day}`),
  addTask: (day: string, title: string, points = 1, visibility?: Visibility) =>
    post<DayView>(`/day/${day}/tasks`, { title, points, visibility }),
  submitDay: (day: string) => post<DayView>(`/day/${day}/submit`),
  setStatus: (taskId: number, status: TaskStatus, reason?: string) =>
    patch<DayView>(`/tasks/${taskId}`, { status, reason }),
  moveTask: (taskId: number, date: string) =>
    post<DayView>(`/tasks/${taskId}/move`, { date }),
  deleteTask: (taskId: number) => del<{ ok: boolean }>(`/tasks/${taskId}`),

  habits: () => get<Habit[]>("/habits"),
  createHabit: (body: Partial<Habit>) => post<Habit>("/habits", body),
  updateHabit: (id: number, body: Partial<Habit>) => put<Habit>(`/habits/${id}`, body),
  archiveHabit: (id: number) => del<{ ok: boolean }>(`/habits/${id}`),

  team: () => get<TeamView>("/team"),
  join: (code: string) => post<{ ok: boolean }>("/team/join", { code }),
  renameTeam: (name: string) => patch<{ ok: boolean; name: string }>("/team", { name }),
  resetCode: () => post<{ ok: boolean; invite_code: string }>("/team/code"),
  removeMember: (userId: number) => del<{ ok: boolean }>(`/team/members/${userId}`),
  leaveTeam: () => post<{ ok: boolean }>("/team/leave"),
  nudge: (toUserId: number, comment = "") =>
    post<{ ok: boolean }>("/team/nudge", { to_user_id: toUserId, comment }),
  react: (targetUserId: number, emoji: string) =>
    post<{ ok: boolean }>("/team/react", { target_user_id: targetUserId, emoji }),

  stats: (days = 30) => get<StatsView>(`/stats?days=${days}`),
};
