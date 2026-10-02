import translations from "./topic-translations.json";

/** Display-only draft translations; original topic names remain search queries. */
export function topicLabel(topic: string): string {
  return Object.hasOwn(translations, topic)
    ? (translations as Record<string, string>)[topic]
    : topic;
}
