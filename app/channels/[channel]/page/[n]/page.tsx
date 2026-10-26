import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { parsePage } from "@/lib/paginate";
import ChannelView, { channelMetadata } from "../../view";

type Props = { params: Promise<{ channel: string; n: string }> };

// 2ページ目以降はアクセス時に生成してキャッシュする
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { channel, n } = await params;
  const page = parsePage(n);
  return page ? channelMetadata(channel, page) : {};
}

export default async function ChannelPagedPage({ params }: Props) {
  const { channel, n } = await params;
  const page = parsePage(n);
  if (!page) notFound();
  return <ChannelView channel={channel} page={page} />;
}
