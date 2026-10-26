import NewsView, { newsMetadata } from "./view";

export const metadata = newsMetadata(1);

export default function NewsPage() {
  return <NewsView page={1} />;
}
