import type { Metadata } from "next";
import { getAllChannels } from "@/lib/articles";
import ChannelView, { channelMetadata } from "./view";

type Props = { params: Promise<{ channel: string }> };

// 記事の多いチャンネルだけビルド時に静的化し、残りは初回アクセス時に生成（ISR）。無いチャンネルは 404
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return getAllChannels()
    .slice(0, 50)
    .map((channel) => ({ channel: channel.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { channel } = await params;
  return channelMetadata(channel, 1);
}

export default async function ChannelPage({ params }: Props) {
  const { channel } = await params;
  return <ChannelView channel={channel} page={1} />;
}
