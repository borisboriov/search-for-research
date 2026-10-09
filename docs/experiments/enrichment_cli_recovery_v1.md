# Bounded-v3: восстановление завершённого v2 collector

V2 получил законченный assistant, done=true, exit0, pending=[] и полный receipt.
Host check_schema не поддерживал dictionary additionalProperties evidence_pool
и упал KeyError:properties. Это техническая ошибка postflight, не повод для
третьего collector inference. Исправленный общий checker проверяет typed
additionalProperties, required и запрет лишних полей; критерии не ослабляются.

Новый v3root содержит побайтные копии sample/batches/runs/pilot-events/policies
v2, SHA-индекс и неизменные imported manifest/STOP. Предыдущие v1/v2 roots и STOP
не меняются. У копированных Batch сохраняется readonly frozen_root v2: tickets,
выборка, правила, резервации, их исходы и исходный collector receipt не переименованы.
Первый collector parse/validate/bind выполняется над последним сохранённым
assistant, без новых источников/model calls. В result отмечается recovery.
После нормализации — первый независимый nativeSol/high по прежней полной рубрике.
Остальные11 профилей используют тот же ограниченный CLI collector, правило и
исходную заранее закреплённую выборку. Это продолжение, не новая свежая выборка.

Host method=v3, модельная инструкция остаётся bounded-v2. Новый полный code hash
фиксируется до preflight/recovery/Sol. Предыдущие raw/request/usage/tickets
проверяются по SHA до recovery; изменения дают STOP. Повтор collector запрещён.
Для квоты и дедлайна действуют исправления v2. Human_reviewed0.
