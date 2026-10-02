import type { SupervisorCard, TopWork } from "./types";

// Формальный шаблон первого письма научруку — по структуре БФТ 2.2 паспорта
// (интересы → мотивация → ожидания). Текст черновой, на проверке у Светы
// (TODO_BORIS.md); квадратные скобки заполняет студент.
export function buildLetter(card: SupervisorCard, selectedWork: TopWork | null = null): string {
  // Работу передаёт только явный выбор студента; без него нет утверждения о чтении.
  const work = selectedWork && card.top_works.find(
    (item) => item.title === selectedWork.title && item.year === selectedWork.year,
  );
  const workLine = work
    ? ` Прочитал(а) вашу работу «${work.title}»${work.year !== null ? ` (${work.year})` : ""} — она близка к тому, чем я хочу заниматься.`
    : "";
  return `Здравствуйте, [Имя Отчество]!

Я студент(ка) [курс, факультет, вуз]. Мне интересна тема [опишите интересы своими словами].${workLine}

Хочу решать задачу: [какую задачу хочу решать / тема ВКР].

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
