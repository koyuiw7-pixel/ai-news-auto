"use client";

import * as React from "react";

type ViewTransitionComponent = React.ComponentType<{
  name?: string;
  children?: React.ReactNode;
}>;

/*
 * 記事カード → 記事ページで、サムネイルと見出しを滑らかにつなぐ。
 * React の ViewTransition は実験機能のため、存在しない環境では何もせずに描画する。
 * 同じ name はページ内で1つだけにすること（重複すると遷移が無効になる）。
 */
const ReactWithTransition = React as unknown as {
  ViewTransition?: ViewTransitionComponent;
  unstable_ViewTransition?: ViewTransitionComponent;
};
const ViewTransition =
  ReactWithTransition.ViewTransition ?? ReactWithTransition.unstable_ViewTransition;

export default function Morph({
  name,
  enabled = true,
  children,
}: {
  name: string;
  enabled?: boolean;
  children: React.ReactNode;
}) {
  if (!enabled || !ViewTransition) return <>{children}</>;
  return <ViewTransition name={name}>{children}</ViewTransition>;
}
