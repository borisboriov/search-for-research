import type { SupervisorCard } from "./types";

// Формальный шаблон первого письма научруку — по структуре БФТ 2.2 паспорта
// (интересы → мотивация → ожидания). Текст черновой, на проверке у Светы
// (TODO_BORIS.md); квадратные скобки заполняет студент.
export function buildLetter(card: SupervisorCard): string {
  const topWork = card.top_works[0];
  const workLine = topWork
    ? `Прочитал(а) вашу работу «${topWork.title}»${topWork.year ? ` (${topWork.year})` : ""} — она близка к тому, чем я хочу заниматься.`
    : "Ваши публикации близки к тому, чем я хочу заниматься.";
  return `Здравствуйте, ${card.name}!

Я студент(ка) [курс, факультет, вуз]. Мне интересна тема [опишите интересы своими словами]. ${workLine}

Хочу обсудить возможность выполнить научную работу под вашим руководством. Буду благодарен(на) за ответ — готов(а) рассказать о себе подробнее и прислать резюме.

С уважением,
[Имя Фамилия]`;
}

// Адрес для «Это вы?» задаётся окружением; пока его нет, mailto открывает
// письмо без получателя — адрес появится вместе с доменом (TODO_BORIS.md).
export function claimProfileMailto(authorId: string): string {
  const to = process.env.NEXT_PUBLIC_CLAIM_EMAIL ?? "";
  const subject = encodeURIComponent(`Профиль НР ${authorId}: редактирование или скрытие`);
  return `mailto:${to}?subject=${subject}`;
}
