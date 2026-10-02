import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import catalogue from "../../../../docs/reports/pilot-ui-topic-catalogue.json";
import translations from "@/lib/topic-translations.json";
import { topicLabel } from "@/lib/topics";

const frequencies: Record<string, number> = catalogue.frequencies;

describe("topicLabel", () => {
  it("переводит научное направление для отображения", () => {
    expect(topicLabel("Topic Modeling")).toBe("Тематическое моделирование");
    expect(topicLabel("Cold Atom Physics and Bose-Einstein Condensates")).toBe(
      "Физика холодных атомов и конденсаты Бозе — Эйнштейна",
    );
  });

  it.each(["Unknown new topic", "topic modeling", "", "constructor", "toString", "__proto__"])(
    "сохраняет неизвестную точную строку %j, включая свойства прототипа",
    (topic) => expect(topicLabel(topic)).toBe(topic),
  );

  it("покрывает все точные названия измеренного каталога без лишних ключей", () => {
    expect(Object.keys(translations).sort()).toEqual(Object.keys(frequencies).sort());
    for (const topic of Object.keys(frequencies)) {
      const label = topicLabel(topic);
      expect(label.trim(), topic).toBe(label);
      expect(label, topic).toMatch(/[А-Яа-яЁё]/);
      expect(label, topic).not.toBe(topic);
    }
  });

  it("снимок имеет согласованные итоги и честный статус переводов", () => {
    expect(Object.keys(frequencies)).toHaveLength(catalogue.unique_topic_count);
    expect(Object.values(frequencies).reduce((sum, value) => sum + value, 0)).toBe(
      catalogue.topic_profile_mentions,
    );
    expect(Object.values(frequencies).every((n) => n > 0 && n <= catalogue.profile_count)).toBe(true);
    expect(catalogue.translation_status).toBe("agent_draft");
    expect(catalogue.human_review).toBe("none");
  });
});

const sourcePath = path.resolve(process.cwd(), "../..", catalogue.source);

it.skipIf(!existsSync(sourcePath))(
  "сверяет весь доступный локальный каталог, частоты и SHA-256 со снимком",
  () => {
    const bytes = readFileSync(sourcePath);
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(catalogue.source_sha256);
    const profiles = bytes.toString("utf8").split(/\r?\n/).filter(Boolean).map(
      (line) => JSON.parse(line) as { topics: string[] },
    );
    expect(profiles).toHaveLength(catalogue.profile_count);
    const actual: Record<string, number> = {};
    for (const profile of profiles) {
      for (const topic of new Set(profile.topics)) {
        actual[topic] = (actual[topic] ?? 0) + 1;
      }
    }
    expect(actual).toEqual(frequencies);
    expect(Object.keys(translations).sort()).toEqual(Object.keys(actual).sort());
  },
  30_000,
);
