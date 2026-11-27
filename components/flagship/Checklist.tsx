"use client";

import { useId, useState, type ReactNode } from "react";
import type { ChecklistItem } from "@/lib/flagship";
import { birthDeadline } from "@/lib/flagship-date";

/**
 * うちのやることリスト（期限つき）。チェックはこの画面の中だけ（保存・送信しない）。
 * 出生日（予定日）を入れると、認定請求の期限の日付を出す（こども家庭庁「出生の日の翌日から15日以内」）
 */
export default function Checklist({ items, sourceLinks }: { items: ChecklistItem[]; sourceLinks: Record<string, ReactNode> }) {
  const id = useId();
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [birth, setBirth] = useState("");
  const deadline = birth ? birthDeadline(birth) : null;
  const count = items.filter((item) => done[item.id]).length;
  return (
    <div className="fs-check-wrap">
      <div className="fs-progress" aria-live="polite">
        <span>
          {items.length}つのうち<b>{count}</b>つ確かめました
        </span>
        <span className="fs-progress-bar" aria-hidden="true">
          <i style={{ width: `${(count / Math.max(1, items.length)) * 100}%` }} />
        </span>
      </div>
      <ol className="fs-todo">
        {items.map((item) => (
          <li key={item.id} data-done={done[item.id] ? "" : undefined}>
            <label className="fs-todo-row">
              <input type="checkbox" checked={Boolean(done[item.id])} onChange={(e) => setDone((d) => ({ ...d, [item.id]: e.target.checked }))} />
              <span className="fs-todo-main">
                <b>{item.title}</b>
                <span className="fs-deadline">{item.deadline}</span>
              </span>
            </label>
            <p className="fs-todo-detail">{item.detail}</p>
            {item.birthDeadline ? (
              <div className="fs-todo-date">
                <label htmlFor={`${id}-birth`} className="fs-label">出生日（予定日）を入れると、期限の日付が出ます</label>
                <div className="fs-todo-date-row">
                  <input id={`${id}-birth`} type="date" value={birth} onChange={(e) => setBirth(e.target.value)} className="fs-input" />
                  <p className="fs-deadline-out" aria-live="polite">
                    {deadline ? (
                      <>
                        期限 <time dateTime={deadline.iso}>{deadline.label}</time>
                      </>
                    ) : (
                      "　"
                    )}
                  </p>
                </div>
                <p className="fs-hint">窓口が休みの日の扱いは、お住まいの市区町村で確かめてください。</p>
              </div>
            ) : null}
            <p className="fs-src">出典：{item.sources.map((s, i) => (<span key={s}>{i > 0 ? "、" : ""}{sourceLinks[s]}</span>))}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
