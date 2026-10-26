import ArticlesView, { articlesMetadata } from "./view";

export const metadata = articlesMetadata(1);

export default function ArticlesIndexPage() {
  return <ArticlesView page={1} />;
}
