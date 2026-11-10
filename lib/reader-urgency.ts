/**
 * 読者に「自分ごと」として関わる発表かの判定（2026-11-11 読者目線レビュー 6位・11位）。
 * 本体は lib/cover-path.ts（赤い「速報」の判定 isFastNews と同じ、依存のない小さなファイル。テストが単体で読むため）
 */
export { MEANINGLESS_ACTION_SOURCE, NO_READER_ACTION_SOURCE, READER_URGENT_SOURCE, meaninglessAction, noReaderAction, readerActions, urgentForReader } from "./cover-path";
