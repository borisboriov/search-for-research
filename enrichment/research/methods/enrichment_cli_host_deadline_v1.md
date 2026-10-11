# Прерываемый host deadline, исправление после bounded-v4

Полное независимое ревью ночного диапазона выявило Medium блокер: синхронная
policy проверяла DNS/robots/body/crawl-delay внутри host, а HTTPX timeout20
ограничивал паузу между chunks, не полное время операции. Внешний collector
не мог проверить595с/HARD_STOP до возврата policy. Permission timeout30с в
Pi не отменяет host запрос. Источник контракта:
[HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/).

Исправление изолирует policy в отдельном spawn процессе. Родитель ждёт малый
результат через pipe до единого monotonic deadline: минимум25с, остатка
source phase360с и HARD_STOP−5с. Время запуска входит в этот бюджет. При
превышении или сбое дочернего процесса host прекращает collector; обычный
robots ValueError остаётся отказом источника. Cleanup: terminate, bounded
join0.25с, при необходимости kill и bounded join0.25с. CLI также останавливается.
После остановки дренируются только полученные результаты; поздние reserve
отклоняются без новой DNS/policy/reader операции.

Timeout сохраняет finished/receipt с host_policy_error, done=false,
usage_complete=false и host_partial_unknown. Пустой result/not_checked не
считается завершённой моделью; dependent Sol запрещён прежним stage gate.
Незавершённая robots reservation сохраняется в журнале Batch и бюджете,
автоматического запроса/повтора/признания доступа нет.

Проверка только офлайн: реально зависший child, игнорирующий SIGTERM, убит
по deadline; истёкший deadline не запускает child/DNS; local CLI fixture
остановлена, partial/unknown сохранён, поздняя reservation не вызвала policy.
Новых GLM/source calls для этого исправления в ночь нет.

Двенадцать основных профилей и сравнение GPT измерены **до исправления**,
на frozen bounded-v4 core hashes. Их raw/STOP/manifest/метрики сохранены;
не заявляется новый живой прогон исправленного host. Старые roots после
изменения core отвергают resume по SHA. Перед будущим source запуском нужны
новое поручение после ночной остановки, новый freeze/code hashes и preflight;
старые результаты нельзя переименовать как измерение исправленной версии.
