# Дедупликация каталога (SFR-5) — выборка на ручную проверку

Готовит агент, читает человек. Ниже три раздела: что склеено автоматически, кого решено **не** склеивать, и профили с подозрением на чужую склейку OpenAlex.

Склеек: **48**; групп тёзок без сигнала: **276**; профилей с флагом `suspect_merge`: **412**.

## Склеено автоматически — первые 60

«Канонический» — тот, у кого больше работ; на него перенесены работы, темы и счётчики остальных.

| Канонический | Имена | Вуз | Дубли | Сигнал |
|---|---|---|---|---|
| `A5003445476` | Andrei G. Yakovlev; A. G. Yakovlev | Московский государственный университет | `A5114254527` | abbrev+institution+topics |
| `A5006869709` | Alexander A. Yaroslavov; A. A. Yaroslavov | Московский государственный университет | `A5111531327` | abbrev+institution+topics |
| `A5010299342` | Андрей Андреевич Шкаликов; А. А. Шкаликов | Московский государственный университет | `A5076625726` | abbrev+institution+topics |
| `A5014434996` | N. Chubarova; Natalia Chubarova | Московский государственный университет | `A5113036029` | abbrev+institution+topics |
| `A5016531787` | N. Yu. Tabachkova | Высшая школа экономики; Национальный исследовательский технологический университет МИСиС | `A5059699485` | orcid |
| `A5017119124` | Vsevolod V. Koryanov; V. V. Koryanov | Московский государственный технический университет имени Н. Э. Баумана | `A5007427934` | abbrev+institution+topics |
| `A5017246180` | A. А. Lanin; A. V. Lanin | Московский государственный университет | `A5033702332` | orcid |
| `A5024991865` | Grigory V. Zyryanov; G. V. Zyryanov | Уральский федеральный университет | `A5110847406`, `A5020486264` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5025975946` | M.S. Nechaev; Mikhail S. Nechaev | Московский государственный университет | `A5111202994` | abbrev+institution+topics |
| `A5028750791` | Svetlana G. Jorstad; S. G. Jorstad | Санкт-Петербургский государственный университет | `A5114375175` | abbrev+institution+topics |
| `A5033126777` | N. I. Chistyakova; Nataliya I. Chistyakova | Московский государственный университет | `A5108217699` | abbrev+institution+topics |
| `A5034087412` | Galina Vershubskaya; Galina Vershubsky | Московский государственный университет | `A5107991670` | orcid |
| `A5035715715` | Alexander Snigirev; A. Snigirev | Московский государственный университет | `A5105694793` | abbrev+institution+topics |
| `A5038417473` | Tatiana S. Oretskaya; T. S. Oretskaya | Московский государственный университет | `A5113617445` | abbrev+institution+topics |
| `A5051488444` | A. Yu. Kraeva; M. A. Kozhin | Национальный исследовательский ядерный университет МИФИ; Московский государственный университет | `A5052846692` | orcid |
| `A5051616216` | Igor S. Golyak; Il. S. Golyak | Московский государственный технический университет имени Н. Э. Баумана | `A5109502076` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5055996094` | Sergei Sharakin; S. Sharakin | Московский государственный университет | `A5038736353` | abbrev+institution+topics |
| `A5062267829` | A. V. Pestov; Alexandr V. Pestov | Уральский федеральный университет | `A5109499265` | abbrev+institution+topics |
| `A5065752368` | Evgeny A. Viktorov; E. A. Viktorov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | `A5071720585` | abbrev+institution+topics |
| `A5072035061` | L. I. Isaenko; Lyudmila I. Isaenko | Новосибирский государственный университет | `A5110810683` | abbrev+institution+topics |
| `A5077932250` | E. P. Kharitonova; Elena P. Kharitonova | Московский государственный университет | `A5111995092` | abbrev+institution+topics |
| `A5080073119` | A. B. Rubin; Andrey B. Rubin | Московский государственный университет | `A5109416325`, `A5088071447` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5083666599` | T. Aushev | Московский физико-технический институт | `A5107138481` | orcid |
| `A5092863478` | Nikolay A. Usachev; N. A. Usachev | Национальный исследовательский ядерный университет МИФИ | `A5055386468` | abbrev+institution+topics |
| `A5100367029` | Qiang Wang | Санкт-Петербургский государственный университет | `A5101786689` | orcid |
| `A5101454429` | Akihisa Inoue; A. Inoue | Национальный исследовательский технологический университет МИСиС | `A5101454427` | abbrev+institution+topics |
| `A5102818854` | A. V. Kulikov; Andrey V. Kulikov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | `A5102536047` | abbrev+institution+topics |
| `A5103013951` | Т. В. Андреева; Tatyana V. Andreeva | Московский государственный университет | `A5112612684` | orcid |
| `A5104155912` | G. Chelkov; G. A. Chelkov | Московский физико-технический институт; Московский государственный университет | `A5107824305` | orcid |
| `A5106945230` | А. А. Силаев | Московский государственный университет | `A5082621562` | orcid |
| `A5108096153` | A. Chepurnov; Alexander Chepurnov | Московский государственный университет | `A5109542233` | abbrev+institution+topics |
| `A5108393699` | A. P. Zhevlakov; V. Zherebchevskii | Санкт-Петербургский государственный университет | `A5085929652` | orcid |
| `A5108455821` | V. G. Yakunin; Valery G. Yakunin | Московский государственный университет | `A5108819750` | abbrev+institution+topics |
| `A5108463072` | S. Lobanov; Sergei Lobanov | Новосибирский государственный университет | `A5108765594` | abbrev+institution+topics |
| `A5108626258` | A.V. Alexandrova; Alina V. Alexandrova | Московский государственный университет | `A5103882772` | abbrev+institution+topics |
| `A5110110770` | Sergey A. Siletsky; S. A. Siletsky | Московский государственный университет | `A5111067128` | abbrev+institution+topics |
| `A5110156933` | S. M. Klimentov; Sergei M. Klimentov | Национальный исследовательский ядерный университет МИФИ | `A5103461360` | abbrev+institution+topics |
| `A5110296283` | N. N. Eremin; Nikolay N. Eremin | Московский государственный университет | `A5110471238` | abbrev+institution+topics |
| `A5110340004` | V. S. Aksenov; Viktor S. Aksenov | Национальный исследовательский ядерный университет МИФИ | `A5110743887` | abbrev+institution+topics |
| `A5110629778` | G. V. Sidorenko; Georgy V. Sidorenko | Национальный исследовательский ядерный университет МИФИ | `A5111203075` | abbrev+institution+topics |
| `A5110730302` | Andrey V. Shlyakhtin; A. V. Shlyakhtin | Московский государственный университет | `A5110813439` | abbrev+institution+topics |
| `A5110969712` | Evgeniy P. Lukashev; E. P. Lukashev | Московский государственный университет | `A5110152096` | abbrev+institution+topics |
| `A5111713776` | E. V. Podivilov; Evgeny V. Podivilov | Новосибирский государственный университет | `A5112685205` | abbrev+institution+topics |
| `A5112269203` | Valery Lukinskiy; Vladislav Lukinskiy | Высшая школа экономики | `A5073953503` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5112334685` | A. A. Chistyakov; Alexander A. Chistyakov | Национальный исследовательский ядерный университет МИФИ | `A5111954803` | abbrev+institution+topics |
| `A5112367657` | A. G. Kharlamov | Новосибирский государственный университет | `A5107868597` | orcid |
| `A5112502915` | E. N. Ulomsky; Evgeny N. Ulomsky | Уральский федеральный университет | `A5113218225` | abbrev+institution+topics |
| `A5112724907` | V. V. Vedyushkina; Viktoriya Viktorovna Vedyushkina | Московский государственный университет | `A5113014044` | abbrev+institution+topics |

## Не склеено: тёзки — первые 60

Одинаковое имя и вуз, но ни ORCID, ни общей работы. Склеить их автоматически — риск объединить двух разных людей; оставить как есть — риск дубля в выдаче. Выбран второй.

| Автор-ы | Имена | Вуз |
|---|---|---|
| `A5000033999`, `A5111837214` | Ludmila A. Baratova; Lyudmila A. Baratova | Московский государственный университет |
| `A5000809208`, `A5081848065` | Igor I. Potemkin | Московский государственный университет |
| `A5000910106`, `A5081155952` | Vadim Makarov | Национальный исследовательский технологический университет МИСиС |
| `A5001080347`, `A5102711687` | С. П. Кшевецкий | Санкт-Петербургский государственный университет |
| `A5001155008`, `A5018973674` | Andrey Chernyavskiy; Anton Chernyavskiy | Высшая школа экономики |
| `A5001535183`, `A5032593380`, `A5108009841`, `A5108128007` | N. Yu. Muchnoi | Новосибирский государственный университет |
| `A5001701647`, `A5040177241` | Alexandra Chesnokova; Anna Chesnokova | Новосибирский государственный университет |
| `A5001767693`, `A5069283769` | Viktor Polyakov; Vyacheslav Polyakov | Санкт-Петербургский государственный университет |
| `A5002327671`, `A5030490436` | Ilya A. Ryzhikov; I. A. Ryzhikov | Московский государственный технический университет имени Н. Э. Баумана |
| `A5002375089`, `A5061184176` | Yang Liu | Санкт-Петербургский государственный университет |
| `A5002494657`, `A5113870632` | Vasiliy O. Yapaskurt; V. O. Yapaskurt | Московский государственный университет |
| `A5002724483`, `A5085551896` | I. K. Surin | Новосибирский государственный университет |
| `A5003336391`, `A5113554030` | Anton A. Klyachko; Alexander A. Klyachko | Московский государственный университет |
| `A5003445476`, `A5080587433` | Andrei G. Yakovlev; A. G. Yakovlev | Московский государственный университет |
| `A5003474158`, `A5057325838` | Alexander Viktorovich Shklyaev; A. V. Shklyaev | Московский государственный университет |
| `A5003550637`, `A5014636332`, `A5104155912`, `A5109243687` | G. Chelkov | Московский физико-технический институт |
| `A5003561300`, `A5044150976` | Ying Sun | Московский авиационный институт |
| `A5004117118`, `A5077031104` | A. L. Buchachenko | Московский государственный университет |
| `A5004127966`, `A5103425096` | А. Е. Романов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5004429748`, `A5070271811` | Dmitry D. Sokoloff; D. D. Sokoloff | Московский государственный университет |
| `A5004505938`, `A5020808383` | Sergey Malkov | Московский государственный университет |
| `A5004508993`, `A5018265667` | Е. А. Левашов | Национальный исследовательский технологический университет МИСиС |
| `A5004619519`, `A5069174347` | A. V. Ivanov; Alexey V. Ivanov | Санкт-Петербургский государственный университет |
| `A5005727447`, `A5102758471` | Н.С. Касимов | Московский государственный университет |
| `A5005873845`, `A5115590111` | Antón Smirnov; Andrei Smirnov | Московский государственный университет |
| `A5006116376`, `A5007355563`, `A5018178280` | A. Yu. Popov | Московский государственный университет |
| `A5006387822`, `A5108113054` | Н. И. Каргин | Национальный исследовательский ядерный университет МИФИ |
| `A5006474392`, `A5031864902` | Aleksei P. Zhabko; Alexey P. Zhabko | Санкт-Петербургский государственный университет |
| `A5006480044`, `A5112461519` | A. M. Bobkov | Московский физико-технический институт |
| `A5006484035`, `A5028515210` | В. Г. Кытин | Московский государственный университет |
| `A5006736805`, `A5101921020` | Vladimir Popov; V. Popov | Московский государственный университет |
| `A5007263024`, `A5107892049`, `A5110765467` | F. Y. Khalili | Московский государственный университет |
| `A5007617087`, `A5076391492` | Alexander Pavlov | Высшая школа экономики |
| `A5008061061`, `A5091709269` | Vladislav G. Rodin | Национальный исследовательский ядерный университет МИФИ |
| `A5008142602`, `A5047972823` | D. V. Yakovlev; D V Yakovlev | Московский государственный университет |
| `A5008431175`, `A5111912496` | Yury A. Teterin; Yu. A. Teterin | Московский государственный университет |
| `A5008525201`, `A5016619004` | V.S. Fadin; V. S. Fadin | Новосибирский государственный университет |
| `A5009083880`, `A5100600309` | Artem V. Sergeev; Alexander V. Sergeev | Московский государственный университет |
| `A5009310022`, `A5102763984` | Aleksey Vishnyakov | Московский государственный университет |
| `A5009556638`, `A5052615328` | I. S. Troitskiy | Санкт-Петербургский государственный университет |
| `A5010549818`, `A5108315643` | Evgeny V. Sokolov; E. V. Sokolov | Московский государственный технический университет имени Н. Э. Баумана |
| `A5010619481`, `A5066082533` | Л. Г. Свешникова | Московский государственный университет |
| `A5011006843`, `A5012284704` | А. А. Белов | Московский государственный университет |
| `A5011573216`, `A5055134916` | В. А. Богатырев | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5012145115`, `A5103523575` | V. Samsonov | Московский государственный университет |
| `A5012152190`, `A5029069529` | В. В. Фадеев | Московский государственный университет |
| `A5012474766`, `A5056181125` | I. Kh. Sabitov | Московский государственный университет |
| `A5012856011`, `A5089285373` | Alexey V. Ustinov; A. V. Ustinov | Высшая школа экономики |
| `A5013101814`, `A5109592785` | V. V. Spiridonov; Vasiliy V. Spiridonov | Московский государственный университет |
| `A5013369571`, `A5021199389`, `A5059345176`, `A5064500094`, `A5101860102`, `A5103081160`, `A5104259484` | Abhinav Kumar; Avinash Kumar | Уральский федеральный университет |
| `A5013973148`, `A5084412511` | Sergey Marchenko; Steven Marchenko | Новосибирский государственный университет |
| `A5014682558`, `A5030983607` | В. В. Назаров | Московский государственный университет |
| `A5014699037`, `A5043886388` | A. V. Knotko; A.V. Knotko | Московский государственный университет |
| `A5015250052`, `A5028981909`, `A5048673082`, `A5109966519` | A.D. Dolgov; A. D. Dolgov | Новосибирский государственный университет |
| `A5015275358`, `A5050891811`, `A5102506413` | В. И. Захаров | Московский государственный университет |
| `A5015404546`, `A5032998427` | Mikhail V. Shestakov; M. V. Shestakov | Московский физико-технический институт |
| `A5015478913`, `A5042636648`, `A5109930073` | A. E. Zhukov | Высшая школа экономики |
| `A5015948564`, `A5065727560` | A. F. Iyudin | Московский государственный университет |
| `A5016235661`, `A5101628802` | Andrey A. Petrov; AL. A. PETROV | Санкт-Петербургский государственный университет |
| `A5016243280`, `A5080093142` | A. B. Kukushkin | Национальный исследовательский ядерный университет МИФИ |

## Подозрение на чужую склейку — первые 60 из 412

Работы профиля распадаются на две тематические группы без общей подобласти. Расклейка не делается: делить работы между людьми, которых мы не знаем, нечем. На фронте флаг пока не показывается.

| Автор | Имя | Вуз | Работ | Группы | Темы |
|---|---|---|---|---|---|
| `A5000304332` | A. G. Antipov | Санкт-Петербургский государственный университет | 25 | 17+8 | Non-Destructive Testing Techniques; Quantum optics and atomic interactions; Welding Techniques and Residual Stresses; Magnetic Properties and Applications |
| `A5000432586` | Иджад Хакович Сабитов | Московский государственный университет | 25 | 17+7 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Structural Analysis and Optimization |
| `A5000572171` | Alla Sidorova | Московский государственный университет | 18 | 13+5 | Protein Structure and Dynamics; Enzyme Structure and Function; Evolution and Genetic Dynamics; Advanced Neural Network Applications |
| `A5001854808` | А. А. Романов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 11+9 | Respiratory Support and Mechanisms; Cardiac, Anesthesia and Surgical Outcomes; Airway Management and Intubation Techniques; Geotechnical and Geomechanical Engineering |
| `A5001890520` | Oksana A. Korzhavina | Московский государственный университет | 11 | 8+3 | Coral and Marine Ecosystems Studies; Marine Biology and Ecology Research; Trypanosoma species research and implications; Parasite Biology and Host Interactions |
| `A5002397716` | Ilia Semenkov | Высшая школа экономики | 22 | 12+10 | Functional Brain Connectivity Studies; EEG and Brain-Computer Interfaces; Neurobiology of Language and Bilingualism; Advanced Vision and Imaging |
| `A5002852128` | Konstantin Yu. Kulichikhin | Санкт-Петербургский государственный университет | 18 | 10+8 | Plant Stress Responses and Tolerance; Plant responses to water stress; Alzheimer's disease research and treatments; Prion Diseases and Protein Misfolding |
| `A5003081622` | Sergey Romanov | Московский государственный университет | 25 | 13+7 | Radioactive contamination and transfer; Geochemistry and Geologic Mapping; Mining and Gasification Technologies; Geological Studies and Exploration |
| `A5003326369` | I. A. Anan’eva | Московский государственный университет | 16 | 10+5 | Analytical Chemistry and Chromatography; Microfluidic and Capillary Electrophoresis Applications; Chemical Synthesis and Analysis; Chemical Reactions and Isotopes |
| `A5003859451` | D. Karpenkov | Национальный исследовательский технологический университет МИСиС | 25 | 15+10 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Magnetic Properties of Alloys |
| `A5004388867` | S. V. Fedorov | Высшая школа экономики | 25 | 13+11 | Marine and coastal ecosystems; Atmospheric and Environmental Gas Dynamics; Engineering Technology and Methodologies; Water Quality Monitoring and Analysis |
| `A5004535584` | Aleksei Y. Kondratev | Высшая школа экономики | 24 | 16+6 | Game Theory and Voting Systems; Auction Theory and Applications; Electoral Systems and Political Participation; Game Theory and Applications |
| `A5004606349` | Eva B. Voronkova | Санкт-Петербургский государственный университет | 25 | 16+9 | Composite Structure Analysis and Optimization; Corneal surgery and disorders; Glaucoma and retinal disorders; Structural Analysis and Optimization |
| `A5004774159` | З.Г. Кокаева | Московский государственный университет | 25 | 13+9 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Migraine and Headache Studies |
| `A5005012128` | A. Vorobyev | Московский физико-технический институт | 25 | 18+7 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Photonic and Optical Devices |
| `A5005126269` | Ilya Smirnov | Московский государственный университет | 25 | 11+11 | Oceanographic and Atmospheric Processes; Climate variability and models; Differential Equations and Boundary Problems; Advanced Mathematical Modeling in Engineering |
| `A5005222164` | E. I. Komotskiy | Уральский федеральный университет | 11 | 5+3 | Economic and Technological Systems Analysis; Complex Network Analysis Techniques; Neural Networks and Applications; Impact of Technology on Adolescents |
| `A5005444451` | A. P. Karamyshev | Московский физико-технический институт | 23 | 15+6 | Metallurgy and Material Forming; Metal Alloys Wear and Properties; Diverse Industrial Engineering Technologies; Metal Forming Simulation Techniques |
| `A5005664992` | Е. В. Богданов | Санкт-Петербургский государственный университет | 25 | 14+8 | Semiconductor Quantum Structures and Devices; Digital Transformation in Law; Advanced Semiconductor Detectors and Materials; Semiconductor materials and interfaces |
| `A5006414488` | А. В. Подольский | Московский государственный университет | 25 | 11+10 | Advanced Mathematical Modeling in Engineering; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5006428988` | M. V. Glagolev | Московский государственный университет | 16 | 10+5 | Fusion materials and technologies; Methane Hydrates and Related Phenomena; Nuclear Materials and Properties; Atmospheric and Environmental Gas Dynamics |
| `A5006715496` | I. A. Gorbunova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 17+8 | Chemical synthesis and pharmacological studies; Synthesis of heterocyclic compounds; Synthesis and biological activity; Synthesis and Reactions of Organic Compounds |
| `A5007151249` | Mingyuan Wang | Уральский федеральный университет | 25 | 12+7 | Integrated Energy Systems Optimization; Building Energy and Comfort Optimization; Smart Grid Energy Management; Neutrino Physics Research |
| `A5007163583` | N. N. Dobrovolsky | Московский государственный университет | 16 | 6+5 | Material Properties and Applications; Image and Signal Denoising Methods; Mathematical Approximation and Integration; Cognitive Science and Mapping |
| `A5007381886` | Igor Baklanov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 10+7 | Sociopolitical Dynamics in Russia; RNA modifications and cancer; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies |
| `A5007707633` | A. V. Gubanov | Московский физико-технический институт | 25 | 16+9 | Methane Hydrates and Related Phenomena; Complex Network Analysis Techniques; Combustion and Detonation Processes; Innovations in Concrete and Construction Materials |
| `A5007875096` | Vladimir A. Bodunov | Санкт-Петербургский государственный университет | 15 | 7+7 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Synthesis and Catalytic Reactions; Catalytic C–H Functionalization Methods |
| `A5008463931` | Pavel Y. Stepanov | Московский государственный университет | 25 | 17+8 | Medical Imaging Techniques and Applications; Geotechnical and Geomechanical Engineering; Characterization and Applications of Magnetic Nanoparticles; Radiomics and Machine Learning in Medical Imaging |
| `A5008839108` | Т. П. Лукашенко | Московский государственный университет | 25 | 17+7 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Approximation Theory and Sequence Spaces |
| `A5008840687` | Alexey A. Gorbunov | Новосибирский государственный университет | 25 | 13+8 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Chemical synthesis and pharmacological studies; Synthesis and Biological Evaluation |
| `A5008959053` | O. A. Khlebnikova | Московский государственный университет | 22 | 13+9 | Geological Studies and Exploration; Synthesis and properties of polymers; Marine and environmental studies; Polymer Nanocomposite Synthesis and Irradiation |
| `A5009670893` | Л. И. Родионова | Московский государственный университет | 25 | 17+8 | Zeolite Catalysis and Synthesis; Catalysis and Oxidation Reactions; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies |
| `A5010156849` | Victoriya A. Balycheva | Московский государственный университет | 17 | 8+6 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Organometallic Complex Synthesis and Catalysis; Radical Photochemical Reactions |
| `A5010174582` | L. I. Men’shikov | Московский физико-технический институт | 25 | 14+9 | Atomic and Molecular Physics; Advanced Chemical Physics Studies; Muon and positron interactions and applications; Genetics, Aging, and Longevity in Model Organisms |
| `A5010483789` | V. I. Subbotin | Московский государственный университет | 25 | 15+10 | Heat Transfer and Boiling Studies; Advanced ceramic materials synthesis; Nuclear reactor physics and engineering; Heat transfer and supercritical fluids |
| `A5010522861` | О. В. Тарасова | Новосибирский государственный университет | 25 | 13+8 | Forest Insect Ecology and Management; Arctic and Russian Policy Studies; Fire effects on ecosystems; Animal Ecology and Behavior Studies |
| `A5010783705` | V. A. Kotel'Nikov | Санкт-Петербургский государственный университет | 25 | 11+9 | Planetary Science and Exploration; Astro and Planetary Science; Space exploration and regulation; Space Science and Extraterrestrial Life |
| `A5011298864` | Maria Smirnova | Санкт-Петербургский государственный университет | 25 | 14+9 | Digital Marketing and Social Media; Business Strategy and Innovation; Customer Service Quality and Loyalty; Innovation and Knowledge Management |
| `A5011818851` | Sergey V. Smirnov | Высшая школа экономики | 25 | 15+9 | Economic and Technological Developments in Russia; Monetary Policy and Economic Impact; Russia and Soviet political economy; Chromosomal and Genetic Variations |
| `A5012046177` | S. N. Lysenkov | Московский государственный университет | 25 | 14+9 | Plant and animal studies; Frailty in Older Adults; Plant Parasitism and Resistance; Insect and Pesticide Research |
| `A5012146146` | L B Chen | Московский государственный университет | 14 | 8+4 | RNA and protein synthesis mechanisms; Immunotherapy and Immune Responses; Cell Adhesion Molecules Research; Crime and Detective Fiction Studies |
| `A5012440349` | Е. А. Карпухина | Московский государственный университет | 25 | 14+8 | Analytical chemistry methods development; Clay minerals and soil interactions; Adsorption, diffusion, and thermodynamic properties of materials; Advanced Polymer Synthesis and Characterization |
| `A5012605961` | Igor Arenkov | Санкт-Петербургский государственный университет | 25 | 12+12 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Digital Marketing and Social Media |
| `A5013206562` | А. S. Alekseev | Высшая школа экономики | 25 | 13+11 | Geological Studies and Exploration; Paleontology and Stratigraphy of Fossils; Hydrocarbon exploration and reservoir analysis; Geological and Geochemical Analysis |
| `A5013480255` | L. A. Pozdnyakov | Московский государственный университет | 25 | 13+10 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Soil Carbon and Nitrogen Dynamics |
| `A5013727554` | Yu. V. Chernyak | Московский государственный университет | 12 | 9+3 | Ionosphere and magnetosphere dynamics; Earthquake Detection and Analysis; Geomagnetism and Paleomagnetism Studies; GNSS positioning and interference |
| `A5014213858` | Elizaveta A. Razumova | Московский государственный университет | 15 | 8+6 | Microbial Natural Products and Biosynthesis; RNA and protein synthesis mechanisms; Marine Sponges and Natural Products; Bacterial Genetics and Biotechnology |
| `A5014579054` | M. A. Gerasimov | Московский государственный университет | 20 | 10+8 | Space Exploration and Technology; Phytochemicals and Antioxidant Activities; Planetary Science and Exploration; Space exploration and regulation |
| `A5014763226` | V. V. Nikulin | Национальный исследовательский ядерный университет МИФИ | 25 | 14+8 | Black Holes and Theoretical Physics; Cosmology and Gravitation Theories; Synthesis and biological activity; Synthesis and Characterization of Heterocyclic Compounds |
| `A5015236020` | А. В. Мишин | Новосибирский государственный университет | 25 | 15+10 | Advanced Fiber Laser Technologies; Laser-Matter Interactions and Applications; Composite Material Mechanics; Advanced Mathematical Modeling in Engineering |
| `A5015611534` | Xuan Qiu | Санкт-Петербургский государственный университет | 25 | 14+9 | Advanced battery technologies research; Advanced Battery Materials and Technologies; Supercapacitor Materials and Fabrication; Advancements in Battery Materials |
| `A5015638659` | A.V. Kazansky | Санкт-Петербургский государственный университет | 25 | 13+8 | Oceanographic and Atmospheric Processes; Cytokine Signaling Pathways and Interactions; Meteorological Phenomena and Simulations; Animal Genetics and Reproduction |
| `A5015859306` | Kasim F. Magomedov | Московский государственный университет | 25 | 17+7 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Organometallic Complex Synthesis and Catalysis; Carbon dioxide utilization in catalysis |
| `A5016262778` | Н. П. Ерофеев | Санкт-Петербургский государственный университет | 25 | 12+8 | Thermoregulation and physiological responses; Chaos control and synchronization; Peripheral Artery Disease Management; Diabetic Foot Ulcer Assessment and Management |
| `A5016266822` | Т. Б. Голубева | Московский государственный университет | 25 | 17+7 | Marine animal studies overview; Bat Biology and Ecology Studies; Animal Vocal Communication and Behavior; Photoreceptor and optogenetics research |
| `A5016289155` | I. M. Chernenko | Уральский федеральный университет | 25 | 17+8 | Transition Metal Oxide Nanomaterials; Gas Sensing Nanomaterials and Sensors; Glass properties and applications; Catalysis and Oxidation Reactions |
| `A5016887914` | Malikakhon Kurbonova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 12 | 7+4 | Anaerobic Digestion and Biogas Production; Biofuel production and bioconversion; Methane Hydrates and Related Phenomena; Bee Products Chemical Analysis |
| `A5016903897` | L. A. Beklaryan | Московский физико-технический институт | 25 | 12+9 | Differential Equations and Numerical Methods; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5016992559` | Anna Likhacheva | Новосибирский государственный университет | 25 | 15+8 | Advanced Radiotherapy Techniques; Advances in Oncology and Radiotherapy; High-pressure geophysics and materials; Geological and Geochemical Analysis |
| `A5017101024` | С. Е. Табалин | Московский государственный технический университет имени Н. Э. Баумана | 25 | 18+7 | Spectroscopy and Laser Applications; Calibration and Measurement Techniques; Atmospheric Ozone and Climate; Pulsars and Gravitational Waves Research |
