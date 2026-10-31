# Только синтетический пример входов НИР B/C

Вымышленные люди, идентификаторы и адреса на зарезервированном `.invalid`.
`selection.json`, четыре UTF-8 снимка, `previous-use.json` и `exclusions.json`
показывают заполненный формат. Это не новая выборка SFR, не пилот и не разметка.
Заявление полноты исключений относится только к этому искусственному набору.
Команда требует --development-only и маркирует результат как разработочный,
не подтверждая независимость реального отбора.

Для офлайн-проверки скопировать шаблон протокола
`enrichment/research/methods/nir_email_bc_protocol_v1.json` в приватную папку,
заполнить фактические версии вместо `TEMPLATE` (никакого запуска модели), затем:

```bash
uv run --frozen python -m sfr_enrichment.nir freeze --development-only --root /private/tmp/nir-synthetic-demo --selection enrichment/tests/fixtures/nir-email-bc-v1/selection.json --exclusions enrichment/tests/fixtures/nir-email-bc-v1/exclusions.json --protocol /private/tmp/nir-protocol-demo.json
uv run --frozen python -m sfr_enrichment.nir export --root /private/tmp/nir-synthetic-demo --annotator adelina
uv run --frozen python -m sfr_enrichment.nir export --root /private/tmp/nir-synthetic-demo --annotator sasha
```

Повторный запуск использует новый путь: артефакты не перезаписываются. Эти
команды не создают ответы людей или B/C. Для реального отбора подготовить
другие приватные файлы и полный реестр прежних использований по методике.
