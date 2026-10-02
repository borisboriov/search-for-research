# Русские подписи тем: проверка top-100 (#161)

Подготовлено 02.10.2026 в UI-сессии #155–161. По решению Бориса от 02.10.2026 приёмка top-100 состоит из агентской терминологической проверки с источниками и продуктового одобрения Борисом. Он одобрил этот способ и четыре исправления ниже. Это не научная экспертиза и не человеческая вычитка всех терминов; общие поля снимка `translation_status: agent_draft` и `human_review: none` остаются честными для всего словаря.

## Источник и воспроизводимость

Фактически прочитан текущий локальный каталог `data/exports/profiles_sfr5c.jsonl`: **9 002 профиля, 2 695 уникальных исходных названий тем, 45 061 вхождение тема–профиль**. SHA-256 исходного файла: `352a6377505c68c01f1e9980a513526835ec7a1e6a11ebdd0f7e7a32be1d73c3`. Это результат подсчёта, не историческое число из issue.

Частота ниже — число профилей, содержащих точную исходную строку темы; повтор одной темы внутри профиля учитывается один раз. Сортировка: частота по убыванию, при равенстве — исходное название по возрастанию. Агрегированный [снимок частот](pilot-ui-topic-catalogue.json) не содержит имён, идентификаторов и иных данных профилей. Он позволяет CI проверять полное покрытие; при наличии исходного локального каталога тест дополнительно сверяет частоты и SHA-256.

[Словарь отображения](../../apps/web/lib/topic-translations.json) содержит явный агентский перевод **всех** текущих тем. Переводы написаны по полным названиям научных направлений, без внешнего сервиса, API перевода или пословной подстановки. При последующей приёмке два отдельных агента прочитали 100 наиболее частых пар и выборочно проверили неоднозначные термины по описаниям OpenAlex и русскоязычным академическим источникам. Общие формулировки OpenAlex иногда неоднозначны; отсутствие пометки не означает подтверждения человеком.

Перевод меняет только подпись интерфейса: в ссылках нового поиска остаётся исходное название. Неизвестная точная строка показывается без перевода; регистр ключей сохраняется. Исходный каталог, `profile_text`, индекс и названия публикаций не меняются. Термины и название нового поиска проверяются в выдаче, профиле, его описании и метаданных.

## Метод, результат и границы приёмки

Проверены все 100 пар ниже: один агент — строки 1–50, другой — 51–100.
Использованы категории точности смысла, полноты и терминологии из
[MQM](https://new.themqm.org/mqm-pillars/typology/) без формального балльного
оценивания или заявления о сертификации. Название сопоставлялось с описанием,
ключевыми словами и дисциплиной темы OpenAlex; спорные русские термины — с
употреблением в академических источниках. Все 100 пар прочитаны, но отдельный
внешний источник подбирался выборочно, а не для каждой строки.

| № | Принятое исправление | Основание |
|---|---|---|
| 24 | «Современные волоконные лазеры» → «Современные технологии волоконных лазеров» | Восстановлено значение Technologies: [OpenAlex T10988](https://api.openalex.org/topics/T10988); [употребление РАН](https://www.ras.ru/news/shownews.aspx?id=a5721dc7-2600-4a40-a99e-b8a6a5825001). |
| 34 | «Ядерные материалы и их свойства» → «Материалы для ядерных установок и их свойства» | Уточнение широкого названия: описание охватывает топливо и оболочки, свойства при облучении; [OpenAlex T11242](https://api.openalex.org/topics/T11242), [материалы МИФИ](https://inphe.mephi.ru/node/18985). |
| 84 | «Взаимодействия ионов с поверхностью и их анализ» → «Взаимодействие ионов с поверхностью и анализ поверхности» | Analysis относится также к поверхности: [OpenAlex T12166](https://api.openalex.org/topics/T12166). |
| 100 | «Газовая динамика атмосферы и окружающей среды» → «Динамика газов в атмосфере и окружающей среде» | По описанию речь о выбросах и газовом составе, а не только о газодинамике: [OpenAlex T11588](https://api.openalex.org/topics/T11588); [Институт оптики атмосферы СО РАН](https://ao.iao.ru/ru/content/vol.38-2025/iss.07/4). |

Остальные 96 подписей top-100 оставлены. В частности, «культурные исследования»
согласуются с [программой ВШЭ](https://www.hse.ru/ma/cstudies/admission/),
«транспортные свойства» — с [курсом МГУ](https://condmatt.phys.msu.ru/special-courses/17/256/),
«планетология» — с [курсом ГАИШ МГУ](https://www.sai.msu.ru/ao/speccourses/courses/planety_vo_Vselennoi_busarev.pdf).
У Industrial Engineering and Technologies сохранено широкое название:
[описание T13045](https://api.openalex.org/topics/T13045) не даёт оснований
сужать его до организации производства. Это примеры предметной сверки,
а не перечень источников для каждой из 100 строк.

Борис принял результат для текущего PoC, включая перечисленные четыре правки.
Остальные **2 595** тем такую проверку не проходили. На весь словарь нельзя
распространять ни терминологическую проверку top-100, ни статус «проверено
человеком». Исходные замечания в последнем столбце сохранены как вопросы
первичного перевода; итоги проверки и принятые уточнения приведены выше.

## 100 наиболее частых тем

Все строки ниже: **агентская проверка выполнена; продуктовая приёмка Борисом — да; человеческая терминологическая вычитка — нет**.

| № | Исходная тема / поисковый запрос | Профилей | Русская подпись | На что обратить внимание |
|---|---|---:|---|---|
| 1 | Legal and Regulatory Analysis | 532 | Правовой и нормативный анализ | Спорно: regulatory — «нормативный» или «регуляторный»; проверить широту термина. |
| 2 | Particle physics theoretical and experimental studies | 440 | Теоретические и экспериментальные исследования физики частиц | — |
| 3 | Crystallization and Solubility Studies | 438 | Кристаллизация и растворимость | — |
| 4 | X-ray Diffraction in Crystallography | 433 | Рентгеновская дифракция в кристаллографии | — |
| 5 | Linguistic, Cultural, and Literary Studies | 396 | Лингвистические, культурные и литературные исследования | Широкая исходная тема; проверить, подходит ли «культурные исследования». |
| 6 | Quantum Chromodynamics and Particle Interactions | 359 | Квантовая хромодинамика и взаимодействия частиц | — |
| 7 | High-Energy Particle Collisions Research | 323 | Столкновения частиц высоких энергий | — |
| 8 | Military Technology and Strategies | 310 | Военные технологии и стратегии | — |
| 9 | Material Properties and Applications | 287 | Свойства и применение материалов | — |
| 10 | Dark Matter and Cosmic Phenomena | 255 | Тёмная материя и космические явления | — |
| 11 | Photonic and Optical Devices | 247 | Фотонные и оптические устройства | — |
| 12 | Particle Detector Development and Performance | 239 | Разработка и характеристики детекторов частиц | — |
| 13 | Physics of Superconductivity and Magnetism | 217 | Физика сверхпроводимости и магнетизма | — |
| 14 | Magnetic and transport properties of perovskites and related materials | 198 | Магнитные и транспортные свойства перовскитов и связанных материалов | Спорно: «транспортные» в физическом смысле переноса; проверить понятность студенту. |
| 15 | Economic and Technological Developments in Russia | 193 | Экономическое и технологическое развитие России | — |
| 16 | Geological Studies and Exploration | 190 | Геологические исследования и разведка | Спорно: exploration — геологоразведка или исследование; исходная тема широкая. |
| 17 | Quantum and electron transport phenomena | 186 | Квантовый и электронный транспорт | Спорно: quantum transport / electron transport объединены; проверить научную формулировку. |
| 18 | Semiconductor Quantum Structures and Devices | 182 | Полупроводниковые квантовые структуры и устройства | — |
| 19 | Metal and Thin Film Mechanics | 166 | Механика металлов и тонких плёнок | — |
| 20 | Engineering Technology and Methodologies | 164 | Инженерные технологии и методологии | Широкая исходная тема; проверить редактуру «инженерные технологии». |
| 21 | Advanced materials and composites | 163 | Современные материалы и композиты | Спорно: advanced переведено как «современные», возможен вариант «перспективные». |
| 22 | Neutrino Physics Research | 160 | Физика нейтрино | — |
| 23 | Advanced Chemical Physics Studies | 159 | Современные исследования химической физики | Спорно: advanced — «современные» или «углублённые» исследования. |
| 24 | Advanced Fiber Laser Technologies | 155 | Современные технологии волоконных лазеров | Уточнено по T10988: сохранено значение «технологии». |
| 25 | Luminescence Properties of Advanced Materials | 154 | Люминесцентные свойства современных материалов | Спорно: advanced materials — «современные» или «перспективные» материалы. |
| 26 | Astrophysics and Cosmic Phenomena | 153 | Астрофизика и космические явления | — |
| 27 | Magnetic properties of thin films | 150 | Магнитные свойства тонких плёнок | — |
| 28 | Semiconductor materials and devices | 150 | Полупроводниковые материалы и приборы | — |
| 29 | Diamond and Carbon-based Materials Research | 147 | Алмазные и углеродные материалы | — |
| 30 | Graphene research and applications | 147 | Исследования и применение графена | — |
| 31 | High-pressure geophysics and materials | 146 | Геофизика и материалы при высоких давлениях | Проверить объединение геофизики и материалов при высоких давлениях. |
| 32 | Industrial Engineering and Technologies | 145 | Промышленная инженерия и технологии | Спорно: industrial engineering может означать организацию производства, а не только инженерию. |
| 33 | Nuclear Physics and Applications | 143 | Ядерная физика и её применение | — |
| 34 | Nuclear Materials and Properties | 138 | Материалы для ядерных установок и их свойства | Уточнено по T11242: топливо и конструкционные материалы. |
| 35 | Catalytic Processes in Materials Science | 136 | Каталитические процессы в материаловедении | — |
| 36 | Geological and Geochemical Analysis | 135 | Геологический и геохимический анализ | — |
| 37 | Plasma Diagnostics and Applications | 134 | Диагностика и применение плазмы | — |
| 38 | Astro and Planetary Science | 133 | Астрономия и планетология | Спорно: широкое Astro передано как «астрономия»; возможны «космические науки». |
| 39 | Cold Atom Physics and Bose-Einstein Condensates | 131 | Физика холодных атомов и конденсаты Бозе — Эйнштейна | — |
| 40 | Photonic Crystals and Applications | 131 | Фотонные кристаллы и их применение | — |
| 41 | Atomic and Molecular Physics | 129 | Атомная и молекулярная физика | — |
| 42 | Gold and Silver Nanoparticles Synthesis and Applications | 127 | Синтез и применение наночастиц золота и серебра | — |
| 43 | Laser-Matter Interactions and Applications | 127 | Взаимодействие лазерного излучения с веществом и его применение | — |
| 44 | Advanced Condensed Matter Physics | 124 | Современная физика конденсированного состояния | Спорно: advanced — «современная» или «углублённая» физика. |
| 45 | Laser Design and Applications | 122 | Разработка и применение лазеров | — |
| 46 | Laser-Plasma Interactions and Diagnostics | 122 | Лазерно-плазменные взаимодействия и диагностика | — |
| 47 | Methane Hydrates and Related Phenomena | 121 | Гидраты метана и связанные явления | — |
| 48 | Quantum Information and Cryptography | 121 | Квантовая информация и криптография | — |
| 49 | Ionosphere and magnetosphere dynamics | 120 | Динамика ионосферы и магнитосферы | — |
| 50 | Chalcogenide Semiconductor Thin Films | 116 | Тонкие плёнки халькогенидных полупроводников | — |
| 51 | Plasmonic and Surface Plasmon Research | 116 | Плазмоника и исследования поверхностных плазмонов | — |
| 52 | Economic and Technological Systems Analysis | 115 | Анализ экономических и технологических систем | — |
| 53 | Quantum Dots Synthesis And Properties | 114 | Синтез и свойства квантовых точек | — |
| 54 | Spectroscopy and Laser Applications | 114 | Спектроскопия и применения лазеров | — |
| 55 | Carbon Nanotubes in Composites | 112 | Углеродные нанотрубки в композитах | — |
| 56 | Engineering and Environmental Studies | 112 | Инженерные и экологические исследования | Спорно: environmental studies — «экологические исследования» или «исследования окружающей среды». |
| 57 | Magnetic confinement fusion research | 112 | Термоядерный синтез с магнитным удержанием | — |
| 58 | Atomic and Subatomic Physics Research | 111 | Атомная и субатомная физика | — |
| 59 | Photosynthetic Processes and Mechanisms | 110 | Фотосинтетические процессы и механизмы | — |
| 60 | RNA and protein synthesis mechanisms | 110 | Механизмы синтеза РНК и белков | — |
| 61 | Intermetallics and Advanced Alloy Properties | 109 | Интерметаллиды и свойства современных сплавов | Спорно: advanced alloy — «современный» или «перспективный» сплав. |
| 62 | Nuclear reactor physics and engineering | 109 | Физика и проектирование ядерных реакторов | — |
| 63 | Advanced biosensing and bioanalysis techniques | 108 | Современные методы биосенсорики и биоанализа | Спорно: biosensing передано как «биосенсорика»; возможен вариант «биосенсорное обнаружение». |
| 64 | Photoreceptor and optogenetics research | 108 | Исследования фоторецепторов и оптогенетики | — |
| 65 | Sociopolitical Dynamics in Russia | 108 | Социально-политическая динамика России | — |
| 66 | Spectroscopy and Quantum Chemical Studies | 108 | Спектроскопия и квантово-химические исследования | — |
| 67 | Glass properties and applications | 107 | Свойства и применение стекла | — |
| 68 | Fluid Dynamics and Turbulent Flows | 106 | Гидрогазодинамика и турбулентные течения | — |
| 69 | Particle accelerators and beam dynamics | 106 | Ускорители частиц и динамика пучков | — |
| 70 | Radiation Detection and Scintillator Technologies | 105 | Регистрация излучения и сцинтилляционные технологии | — |
| 71 | Laser-induced spectroscopy and plasma | 104 | Лазерно-индуцированная спектроскопия и плазма | — |
| 72 | Solar and Space Plasma Dynamics | 104 | Динамика солнечной и космической плазмы | — |
| 73 | Marine and environmental studies | 102 | Морские и экологические исследования | — |
| 74 | Advanced Data Processing Techniques | 101 | Современные методы обработки данных | Спорно: advanced — «современные» или «углублённые» методы. |
| 75 | Catalysis and Oxidation Reactions | 101 | Катализ и реакции окисления | — |
| 76 | Gamma-ray bursts and supernovae | 101 | Гамма-всплески и сверхновые | — |
| 77 | Nuclear physics research studies | 101 | Исследования ядерной физики | — |
| 78 | Rare-earth and actinide compounds | 101 | Соединения редкоземельных элементов и актиноидов | — |
| 79 | Geochemistry and Geologic Mapping | 100 | Геохимия и геологическое картирование | — |
| 80 | Magnetic Properties of Alloys | 100 | Магнитные свойства сплавов | — |
| 81 | Educational Innovations and Challenges | 98 | Инновации и проблемы образования | — |
| 82 | Fusion materials and technologies | 97 | Материалы и технологии термоядерного синтеза | Спорно: fusion предполагается термоядерным; проверить в предметном контексте. |
| 83 | Solid-state spectroscopy and crystallography | 96 | Спектроскопия твёрдого тела и кристаллография | — |
| 84 | Ion-surface interactions and analysis | 95 | Взаимодействие ионов с поверхностью и анализ поверхности | Уточнено по T12166: анализ поверхности. |
| 85 | Nonlinear Waves and Solitons | 95 | Нелинейные волны и солитоны | — |
| 86 | Crystal Structures and Properties | 94 | Кристаллические структуры и свойства | — |
| 87 | Black Holes and Theoretical Physics | 93 | Чёрные дыры и теоретическая физика | — |
| 88 | Photorefractive and Nonlinear Optics | 93 | Фоторефрактивная и нелинейная оптика | — |
| 89 | Cosmology and Gravitation Theories | 91 | Космология и теории гравитации | — |
| 90 | Quantum optics and atomic interactions | 91 | Квантовая оптика и взаимодействия атомов | — |
| 91 | Algebraic structures and combinatorial models | 90 | Алгебраические структуры и комбинаторные модели | — |
| 92 | Gas Sensing Nanomaterials and Sensors | 90 | Газочувствительные наноматериалы и сенсоры | — |
| 93 | Microstructure and mechanical properties | 89 | Микроструктура и механические свойства | — |
| 94 | Psychology of Development and Education | 89 | Психология развития и образования | — |
| 95 | Regional Socio-Economic Development Trends | 89 | Тенденции регионального социально-экономического развития | — |
| 96 | Crystallography and molecular interactions | 86 | Кристаллография и межмолекулярные взаимодействия | — |
| 97 | Geomagnetism and Paleomagnetism Studies | 86 | Геомагнетизм и палеомагнетизм | — |
| 98 | Synthesis and Characterization of Heterocyclic Compounds | 86 | Синтез и характеристика гетероциклических соединений | — |
| 99 | Advanced ceramic materials synthesis | 85 | Синтез современных керамических материалов | — |
| 100 | Atmospheric and Environmental Gas Dynamics | 85 | Динамика газов в атмосфере и окружающей среде | Уточнено по T11588: динамика газов и выбросы в окружающую среду. |
