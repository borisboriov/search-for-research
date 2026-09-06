# Дедупликация каталога (SFR-5) — выборка на ручную проверку

Готовит агент, читает человек. Ниже три раздела: что склеено автоматически, кого решено **не** склеивать, и профили с подозрением на чужую склейку OpenAlex.

Склеек: **18**; групп тёзок без сигнала: **82**; профилей с флагом `suspect_merge`: **143**.

## Склеено автоматически — первые 10

«Канонический» — тот, у кого больше работ; на него перенесены работы, темы и счётчики остальных.

| Канонический | Имена | Вуз | Дубли | Сигнал |
|---|---|---|---|---|
| `A5010299342` | Андрей Андреевич Шкаликов; А. А. Шкаликов | Московский государственный университет | `A5076625726` | abbrev+institution+topics |
| `A5016531787` | N. Yu. Tabachkova | Высшая школа экономики; Национальный исследовательский технологический университет МИСиС | `A5059699485` | orcid |
| `A5017119124` | Vsevolod V. Koryanov; V. V. Koryanov | Московский государственный технический университет имени Н. Э. Баумана | `A5007427934` | abbrev+institution+topics |
| `A5028750791` | Svetlana G. Jorstad; S. G. Jorstad | Санкт-Петербургский государственный университет | `A5114375175` | abbrev+institution+topics |
| `A5035715715` | Alexander Snigirev; A. Snigirev | Московский государственный университет | `A5105694793` | abbrev+institution+topics |
| `A5062267829` | A. V. Pestov; Alexandr V. Pestov | Уральский федеральный университет | `A5109499265` | abbrev+institution+topics |
| `A5065752368` | Evgeny A. Viktorov; E. A. Viktorov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | `A5071720585` | abbrev+institution+topics |
| `A5083666599` | T. Aushev | Московский физико-технический институт | `A5107138481` | orcid |
| `A5100367029` | Qiang Wang | Санкт-Петербургский государственный университет | `A5101786689` | orcid |
| `A5101454429` | Akihisa Inoue; A. Inoue | Национальный исследовательский технологический университет МИСиС | `A5101454427` | abbrev+institution+topics |

## Не склеено: тёзки — первые 10

Одинаковое имя и вуз, но ни ORCID, ни общей работы. Склеить их автоматически — риск объединить двух разных людей; оставить как есть — риск дубля в выдаче. Выбран второй.

| Автор-ы | Имена | Вуз |
|---|---|---|
| `A5000910106`, `A5081155952` | Vadim Makarov | Национальный исследовательский технологический университет МИСиС |
| `A5001767693`, `A5069283769` | Viktor Polyakov; Vyacheslav Polyakov | Санкт-Петербургский государственный университет |
| `A5002327671`, `A5030490436` | Ilya A. Ryzhikov; I. A. Ryzhikov | Московский государственный технический университет имени Н. Э. Баумана |
| `A5003550637`, `A5104155912`, `A5109243687` | G. Chelkov | Московский физико-технический институт |
| `A5003561300`, `A5044150976` | Ying Sun | Московский авиационный институт |
| `A5004117118`, `A5077031104` | A. L. Buchachenko | Московский государственный университет |
| `A5004127966`, `A5103425096` | А. Е. Романов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5004429748`, `A5070271811` | Dmitry D. Sokoloff; D. D. Sokoloff | Московский государственный университет |
| `A5004508993`, `A5018265667` | Е. А. Левашов | Национальный исследовательский технологический университет МИСиС |
| `A5006387822`, `A5108113054` | Н. И. Каргин | Национальный исследовательский ядерный университет МИФИ |

## Подозрение на чужую склейку — первые 10 из 143

Работы профиля распадаются на две тематические группы без общей подобласти. Расклейка не делается: делить работы между людьми, которых мы не знаем, нечем. На фронте флаг пока не показывается.

| Автор | Имя | Вуз | Работ | Группы | Темы |
|---|---|---|---|---|---|
| `A5003859451` | D. Karpenkov | Национальный исследовательский технологический университет МИСиС | 25 | 15+10 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Magnetic Properties of Alloys |
| `A5005012128` | A. Vorobyev | Московский физико-технический институт | 25 | 18+7 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Photonic and Optical Devices |
| `A5006715496` | I. A. Gorbunova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 17+8 | Chemical synthesis and pharmacological studies; Synthesis of heterocyclic compounds; Synthesis and biological activity; Synthesis and Reactions of Organic Compounds |
| `A5007151249` | Mingyuan Wang | Уральский федеральный университет | 25 | 12+7 | Integrated Energy Systems Optimization; Building Energy and Comfort Optimization; Smart Grid Energy Management; Neutrino Physics Research |
| `A5007381886` | Igor Baklanov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 10+7 | Sociopolitical Dynamics in Russia; RNA modifications and cancer; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies |
| `A5010174582` | L. I. Men’shikov | Московский физико-технический институт | 25 | 14+9 | Atomic and Molecular Physics; Advanced Chemical Physics Studies; Muon and positron interactions and applications; Genetics, Aging, and Longevity in Model Organisms |
| `A5010522861` | О. В. Тарасова | Новосибирский государственный университет | 25 | 13+8 | Forest Insect Ecology and Management; Arctic and Russian Policy Studies; Fire effects on ecosystems; Animal Ecology and Behavior Studies |
| `A5011298864` | Maria Smirnova | Санкт-Петербургский государственный университет | 25 | 14+9 | Digital Marketing and Social Media; Business Strategy and Innovation; Customer Service Quality and Loyalty; Innovation and Knowledge Management |
| `A5011818851` | Sergey V. Smirnov | Высшая школа экономики | 25 | 15+9 | Economic and Technological Developments in Russia; Monetary Policy and Economic Impact; Russia and Soviet political economy; Chromosomal and Genetic Variations |
| `A5012146146` | L B Chen | Московский государственный университет | 14 | 8+4 | RNA and protein synthesis mechanisms; Immunotherapy and Immune Responses; Cell Adhesion Molecules Research; Crime and Detective Fiction Studies |
