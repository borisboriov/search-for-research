# Дедупликация каталога (SFR-5) — выборка на ручную проверку

Готовит агент, читает человек. Ниже три раздела: что склеено автоматически, кого решено **не** склеивать, и профили с подозрением на чужую склейку OpenAlex.

Склеек: **16**; групп тёзок без сигнала: **84**; профилей с флагом `suspect_merge`: **15**.

## Склеено автоматически — первые 16

«Канонический» — тот, у кого больше работ; на него перенесены работы, темы и счётчики остальных.

| Канонический | Имена | Вуз | Дубли | Сигнал |
|---|---|---|---|---|
| `A5010299342` | Андрей Андреевич Шкаликов; А. А. Шкаликов | Московский государственный университет | `A5076625726` | склеено ранее |
| `A5016531787` | N. Yu. Tabachkova | Высшая школа экономики; Национальный исследовательский технологический университет МИСиС | `A5059699485` | склеено ранее |
| `A5017119124` | Vsevolod V. Koryanov; V. V. Koryanov | Московский государственный технический университет имени Н. Э. Баумана | `A5007427934` | склеено ранее |
| `A5028750791` | Svetlana G. Jorstad; S. G. Jorstad | Санкт-Петербургский государственный университет | `A5114375175` | склеено ранее |
| `A5035715715` | Alexander Snigirev; A. Snigirev | Московский государственный университет | `A5105694793` | склеено ранее |
| `A5062267829` | A. V. Pestov; Alexandr V. Pestov | Уральский федеральный университет | `A5109499265` | склеено ранее |
| `A5065752368` | Evgeny A. Viktorov; E. A. Viktorov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | `A5071720585` | склеено ранее |
| `A5083666599` | T. Aushev | Московский физико-технический институт | `A5107138481` | склеено ранее |
| `A5100367029` | Qiang Wang | Санкт-Петербургский государственный университет | `A5101786689` | склеено ранее |
| `A5101454429` | Akihisa Inoue; A. Inoue | Национальный исследовательский технологический университет МИСиС | `A5101454427` | склеено ранее |
| `A5104155912` | G. Chelkov; G. A. Chelkov | Московский физико-технический институт; Московский государственный университет | `A5107824305` | склеено ранее |
| `A5108463072` | S. Lobanov; Sergei Lobanov | Новосибирский государственный университет | `A5108765594` | склеено ранее |
| `A5110156933` | S. M. Klimentov; Sergei M. Klimentov | Национальный исследовательский ядерный университет МИФИ | `A5103461360` | склеено ранее |
| `A5111713776` | E. V. Podivilov; Evgeny V. Podivilov | Новосибирский государственный университет | `A5112685205` | склеено ранее |
| `A5112334685` | A. A. Chistyakov; Alexander A. Chistyakov | Национальный исследовательский ядерный университет МИФИ | `A5111954803` | склеено ранее |
| `A5112367657` | A. G. Kharlamov | Новосибирский государственный университет | `A5107868597` | склеено ранее |

## Не склеено: тёзки — первые 16

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
| `A5008525201`, `A5016619004` | V.S. Fadin; V. S. Fadin | Новосибирский государственный университет |
| `A5010549818`, `A5108315643` | Evgeny V. Sokolov; E. V. Sokolov | Московский государственный технический университет имени Н. Э. Баумана |
| `A5011573216`, `A5055134916` | В. А. Богатырев | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5012856011`, `A5089285373` | Alexey V. Ustinov; A. V. Ustinov | Высшая школа экономики |
| `A5015250052`, `A5028981909`, `A5048673082`, `A5109966519` | A.D. Dolgov; A. D. Dolgov | Новосибирский государственный университет |
| `A5015404546`, `A5032998427` | Mikhail V. Shestakov; M. V. Shestakov | Московский физико-технический институт |

## Подозрение на чужую склейку — первые 16

Работы профиля распадаются на две тематические группы без общей подобласти. Расклейка не делается: делить работы между людьми, которых мы не знаем, нечем. На фронте флаг пока не показывается.

| Автор | Имя | Вуз | Работ | Группы | Темы |
|---|---|---|---|---|---|
| `A5003859451` | D. Karpenkov | Национальный исследовательский технологический университет МИСиС | 25 | 15+10 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Magnetic Properties of Alloys |
| `A5010174582` | L. I. Men’shikov | Московский физико-технический институт | 25 | 14+9 | Atomic and Molecular Physics; Advanced Chemical Physics Studies; Muon and positron interactions and applications; Genetics, Aging, and Longevity in Model Organisms |
| `A5016903897` | L. A. Beklaryan | Московский физико-технический институт | 25 | 12+9 | Differential Equations and Numerical Methods; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5026722038` | Sergei A. Filin | Московский физико-технический институт | 25 | 12+7 | Economic and Technological Developments in Russia; Regional Economic Development and Innovation; Economic and Technological Systems Analysis; Economic Development and Digital Transformation |
| `A5052499647` | О. В. Руденко | Московский государственный университет | 24 | 11+6 | Ultrasonics and Acoustic Wave Propagation; Nonlinear Photonic Systems; Acoustic Wave Phenomena Research; Underwater Acoustics Research |
| `A5056108259` | A. V. Leonidov | Московский физико-технический институт | 25 | 15+10 | High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Particle physics theoretical and experimental studies; Complex Systems and Time Series Analysis |
| `A5057992942` | А. Н. Тихонов | Московский государственный университет | 25 | 11+10 | Photosynthetic Processes and Mechanisms; Light effects on plants; Photoreceptor and optogenetics research; Spectroscopy and Quantum Chemical Studies |
| `A5063730286` | A. A. Fomichev | Московский физико-технический институт | 25 | 14+11 | Advanced Fiber Laser Technologies; Solid State Laser Technologies; Laser Design and Applications; Geophysics and Sensor Technology |
| `A5078430016` | Е. Г. Жижина | Высшая школа экономики | 25 | 15+9 | Polyoxometalates: Synthesis and Applications; Chemical Synthesis and Reactions; Oxidative Organic Chemistry Reactions; Advanced Mathematical Modeling in Engineering |
| `A5079485396` | M. A. Kondratenko | Московский физико-технический институт | 25 | 18+7 | Particle Accelerators and Free-Electron Lasers; Superconducting Materials and Applications; Particle accelerators and beam dynamics; Particle physics theoretical and experimental studies |
| `A5081771083` | А. В. Гаврилов | Московский государственный университет | 25 | 9+7 | Solid State Laser Technologies; Photorefractive and Nonlinear Optics; Laser Design and Applications; Methane Hydrates and Related Phenomena |
| `A5087087375` | Victor B. Rybakov | Московский государственный университет | 25 | 17+7 | X-ray Diffraction in Crystallography; Crystallization and Solubility Studies; Synthesis and Reactivity of Heterocycles; Crystal structures of chemical compounds |
| `A5100361432` | А. В. Смирнов | Московский государственный университет | 26 | 12+10 | Plasma Diagnostics and Applications; Enzyme function and inhibition; Protist diversity and phylogeny; Material Properties and Applications |
| `A5101884698` | В. В. Иванов | Московский физико-технический институт | 25 | 14+8 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Geological Studies and Exploration |
| `A5107980327` | А. Антонов | Московский государственный университет | 25 | 14+11 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Particle Detector Development and Performance |
