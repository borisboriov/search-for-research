# Дедупликация каталога — выборка на ручную проверку

Готовит агент, читает человек. Разделы: что склеено автоматически; что уже решено человеком (файл решений) и инвариант по нему; что требует его решения сейчас; кого решено **не** склеивать; профили с подозрением на чужую склейку OpenAlex.

Склеек: **24**; решено человеком: **4**; требуют решения человека: **1**; похоже, один человек, но сигнала не хватило: **11**; групп тёзок без сигнала: **163**; профилей с флагом `suspect_merge`: **267**.

## Склеено автоматически — все 24

«Канонический» — тот, у кого больше работ; на него перенесены работы, темы и счётчики остальных.

| Канонический | Имена | Вуз | Дубли | Сигнал |
|---|---|---|---|---|
| `A5010299342` | Андрей Андреевич Шкаликов; А. А. Шкаликов | Московский государственный университет | `A5076625726` | abbrev+institution+topics |
| `A5014434996` | N. Chubarova; Natalia Chubarova | Московский государственный университет | `A5113036029` | abbrev+institution+topics |
| `A5016531787` | N. Yu. Tabachkova | Высшая школа экономики; Национальный исследовательский технологический университет МИСиС | `A5059699485` | orcid |
| `A5024991865` | Grigory V. Zyryanov; G. V. Zyryanov | Уральский федеральный университет | `A5110847406`, `A5020486264` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5028750791` | Svetlana G. Jorstad; S. G. Jorstad | Санкт-Петербургский государственный университет | `A5114375175` | human (#93) |
| `A5035715715` | Alexander Snigirev; A. Snigirev | Московский государственный университет | `A5105694793` | abbrev+institution+topics |
| `A5051616216` | Igor S. Golyak; Il. S. Golyak | Московский государственный технический университет имени Н. Э. Баумана | `A5109502076` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5055996094` | Sergei Sharakin; S. Sharakin | Московский государственный университет | `A5038736353` | abbrev+institution+topics |
| `A5062267829` | A. V. Pestov; Alexandr V. Pestov | Уральский федеральный университет | `A5109499265` | abbrev+institution+topics |
| `A5065752368` | Evgeny A. Viktorov; E. A. Viktorov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | `A5071720585` | abbrev+institution+topics |
| `A5072035061` | L. I. Isaenko; Lyudmila I. Isaenko | Новосибирский государственный университет | `A5110810683` | abbrev+institution+topics |
| `A5080073119` | A. B. Rubin; Andrey B. Rubin | Московский государственный университет | `A5109416325`, `A5088071447` | склеено ранее (признак не восстановить — работы уже перенесены) |
| `A5083666599` | T. Aushev | Московский физико-технический институт | `A5107138481` | orcid |
| `A5100367029` | Qiang Wang | Санкт-Петербургский государственный университет | `A5101786689` | orcid |
| `A5102818854` | A. V. Kulikov; Andrey V. Kulikov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | `A5102536047` | abbrev+institution+topics |
| `A5104155912` | G. Chelkov; G. A. Chelkov | Московский физико-технический институт; Московский государственный университет | `A5107824305` | orcid |
| `A5108463072` | S. Lobanov; Sergei Lobanov | Новосибирский государственный университет | `A5108765594` | abbrev+institution+topics |
| `A5110156933` | S. M. Klimentov; Sergei M. Klimentov | Национальный исследовательский ядерный университет МИФИ | `A5103461360` | abbrev+institution+topics |
| `A5110340004` | V. S. Aksenov; Viktor S. Aksenov | Национальный исследовательский ядерный университет МИФИ | `A5110743887` | abbrev+institution+topics |
| `A5110629778` | G. V. Sidorenko; Georgy V. Sidorenko | Национальный исследовательский ядерный университет МИФИ | `A5111203075` | abbrev+institution+topics |
| `A5111713776` | E. V. Podivilov; Evgeny V. Podivilov | Новосибирский государственный университет | `A5112685205` | abbrev+institution+topics |
| `A5112334685` | A. A. Chistyakov; Alexander A. Chistyakov | Национальный исследовательский ядерный университет МИФИ | `A5111954803` | abbrev+institution+topics |
| `A5112367657` | A. G. Kharlamov | Новосибирский государственный университет | `A5107868597` | orcid |
| `A5112502915` | E. N. Ulomsky; Evgeny N. Ulomsky | Уральский федеральный университет | `A5113218225` | abbrev+institution+topics |

## Решено человеком — 4

Вердикты из `packages/sfr-match/eval/dedup_decisions.jsonl`. `different` — пара не склеивается ни по какому сигналу, в том числе транзитивно через третий профиль, и не появляется ни в одном списке ниже: решение уже принято. `same` — склеивается поверх блокеров (разные ORCID, разные имена). Новый вердикт — строкой в тот же файл.

| Пара | Вердикт | Имена | Вуз | Кто, когда | Источник | Что сделано | Примечание |
|---|---|---|---|---|---|---|---|
| `A5028750791`, `A5114375175` | **same** | Svetlana G. Jorstad; S. G. Jorstad | Санкт-Петербургский государственный университет | Борис, 2026-09-26 | #93 | уже склеено в БД | Svetlana G. Jorstad — один человек с двумя ORCID (СПбГУ) |
| `A5112269203`, `A5073953503` | **different** | Valery Lukinskiy; Vladislav Lukinskiy | Высшая школа экономики | Борис, 2026-09-26 | #108 | запрет действует | Лукинские Valery / Vladislav — отец и сын, соавторы, разные ORCID (ВШЭ) |
| `A5017119124`, `A5007427934` | **different** | Vsevolod V. Koryanov; V. V. Koryanov | Московский государственный технический университет имени Н. Э. Баумана | Борис, 2026-09-26 | #93 | запрет действует | Корянов Vsevolod / Victor (МГТУ), разные ORCID |
| `A5101454429`, `A5101454427` | **different** | Akihisa Inoue; A. Inoue | Национальный исследовательский технологический университет МИСиС | Борис, 2026-09-26 | #93 | запрет действует | Иноуэ Akihisa / Atsuo (МИСИС), разные ORCID |

### Инвариант «запрещено, но склеено» — 0

Пары с вердиктом `different`, которые в этой БД **уже склеены** (`merged_into_id`). На правильной базе список пуст; непустой означает, что БД собрана до решения человека (так в `data/sfr5b.db` с Лукинскими) — расклейка `sfr etl unmerge`.

Пусто — ни одна запрещённая пара не склеена.

## Требуют решения человека — все 1

Сигнал склейки есть (ORCID, общая работа или инициалы + темы), но его блокирует конфликт: один ORCID при разных фамилиях (ошибка OpenAlex), два разных ORCID или два разных развёрнутых имени. Автоматически не склеиваем; вердикт — комментарием в issue, склейка руками через `sfr etl dedup` после правки данных или расклейка `sfr etl unmerge`.

| Авторы | Имена | Вуз | Причина |
|---|---|---|---|
| `A5092863478`, `A5055386468` | Nikolay A. Usachev; N. A. Usachev | Национальный исследовательский ядерный университет МИФИ | abbrev+institution+topics, но разные ORCID |

## Похоже, один человек, но сигнала не хватило — все 11

Полное имя ↔ инициалы, один вуз, общих тем меньше порога склейки. Не склеиваем автоматически; список для человека (#109).

| Авторы | Имена | Вуз | Что совпало |
|---|---|---|---|
| `A5002327671`, `A5030490436` | Ilya A. Ryzhikov; I. A. Ryzhikov | Московский государственный технический университет имени Н. Э. Баумана | полное имя ↔ инициалы, один вуз, общих тем 2 |
| `A5002494657`, `A5113870632` | Vasiliy O. Yapaskurt; V. O. Yapaskurt | Московский государственный университет | полное имя ↔ инициалы, один вуз, общих тем 1 |
| `A5010549818`, `A5108315643` | Evgeny V. Sokolov; E. V. Sokolov | Московский государственный технический университет имени Н. Э. Баумана | полное имя ↔ инициалы, один вуз, общих тем 2 |
| `A5020280128`, `A5102891564` | Jianmin Wu; J. Wu | Московский государственный университет | полное имя ↔ инициалы, один вуз, общих тем 2 |
| `A5032998427`, `A5015404546` | M. V. Shestakov; Mikhail V. Shestakov | Московский физико-технический институт | полное имя ↔ инициалы, один вуз, общих тем 2 |
| `A5068802749`, `A5108729983` | В. С. Бескин; Василий С. Бескин | Московский физико-технический институт | полное имя ↔ инициалы, один вуз, общих тем 1 |
| `A5070271811`, `A5004429748` | D. D. Sokoloff; Dmitry D. Sokoloff | Московский государственный университет | полное имя ↔ инициалы, один вуз, общих тем 2 |
| `A5074881299`, `A5111571742` | V. V. Ryazanov; Valerii V. Ryazanov | Московский физико-технический институт | полное имя ↔ инициалы, один вуз, общих тем 2 |
| `A5087826312`, `A5113646070` | S. V. Popruzhenko; Sergei V. Popruzhenko | Национальный исследовательский ядерный университет МИФИ | полное имя ↔ инициалы, один вуз, общих тем 1 |
| `A5101671641`, `A5101671642` | Ismail Hossain; I. Hossain | Уральский федеральный университет | полное имя ↔ инициалы, один вуз, общих тем 1 |
| `A5110728086`, `A5110187638` | N. V. Lukashev; Nikolay V. Lukashev | Московский государственный университет | полное имя ↔ инициалы, один вуз, общих тем 2 |

## Не склеено: тёзки — все 163

Одинаковое имя и вуз, но ни ORCID, ни общей работы. Склеить их автоматически — риск объединить двух разных людей; оставить как есть — риск дубля в выдаче. Выбран второй.

| Автор-ы | Имена | Вуз |
|---|---|---|
| `A5000033999`, `A5111837214` | Ludmila A. Baratova; Lyudmila A. Baratova | Московский государственный университет |
| `A5000910106`, `A5081155952` | Vadim Makarov | Национальный исследовательский технологический университет МИСиС |
| `A5001080347`, `A5102711687` | С. П. Кшевецкий | Санкт-Петербургский государственный университет |
| `A5001155008`, `A5018973674` | Andrey Chernyavskiy; Anton Chernyavskiy | Высшая школа экономики |
| `A5001535183`, `A5032593380`, `A5108009841`, `A5108128007` | N. Yu. Muchnoi | Новосибирский государственный университет |
| `A5001701647`, `A5040177241` | Alexandra Chesnokova; Anna Chesnokova | Новосибирский государственный университет |
| `A5001767693`, `A5069283769` | Viktor Polyakov; Vyacheslav Polyakov | Санкт-Петербургский государственный университет |
| `A5002724483`, `A5085551896` | I. K. Surin | Новосибирский государственный университет |
| `A5003336391`, `A5113554030` | Anton A. Klyachko; Alexander A. Klyachko | Московский государственный университет |
| `A5003550637`, `A5014636332`, `A5104155912`, `A5109243687` | G. Chelkov | Московский физико-технический институт |
| `A5003561300`, `A5044150976` | Ying Sun | Московский авиационный институт |
| `A5004117118`, `A5077031104` | A. L. Buchachenko | Московский государственный университет |
| `A5004127966`, `A5103425096` | А. Е. Романов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5004508993`, `A5018265667` | Е. А. Левашов | Национальный исследовательский технологический университет МИСиС |
| `A5006387822`, `A5108113054` | Н. И. Каргин | Национальный исследовательский ядерный университет МИФИ |
| `A5006480044`, `A5112461519` | A. M. Bobkov | Московский физико-технический институт |
| `A5006736805`, `A5101921020` | Vladimir Popov; V. Popov | Московский государственный университет |
| `A5007263024`, `A5107892049` | F. Y. Khalili | Московский государственный университет |
| `A5007617087`, `A5076391492` | Alexander Pavlov | Высшая школа экономики |
| `A5008061061`, `A5091709269` | Vladislav G. Rodin | Национальный исследовательский ядерный университет МИФИ |
| `A5008525201`, `A5016619004` | V.S. Fadin; V. S. Fadin | Новосибирский государственный университет |
| `A5009310022`, `A5102763984` | Aleksey Vishnyakov | Московский государственный университет |
| `A5011573216`, `A5055134916` | В. А. Богатырев | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5012152190`, `A5029069529` | В. В. Фадеев | Московский государственный университет |
| `A5012856011`, `A5089285373` | Alexey V. Ustinov; A. V. Ustinov | Высшая школа экономики |
| `A5013369571`, `A5021199389`, `A5059345176`, `A5064500094`, `A5101860102`, `A5103081160`, `A5104259484` | Abhinav Kumar; Avinash Kumar | Уральский федеральный университет |
| `A5013973148`, `A5084412511` | Sergey Marchenko; Steven Marchenko | Новосибирский государственный университет |
| `A5015250052`, `A5028981909`, `A5048673082`, `A5109966519` | A.D. Dolgov; A. D. Dolgov | Новосибирский государственный университет |
| `A5015275358`, `A5050891811` | В. И. Захаров | Московский государственный университет |
| `A5015478913`, `A5042636648`, `A5109930073` | A. E. Zhukov | Высшая школа экономики |
| `A5016235661`, `A5101628802` | Andrey A. Petrov; AL. A. PETROV | Санкт-Петербургский государственный университет |
| `A5016243280`, `A5080093142` | A. B. Kukushkin | Национальный исследовательский ядерный университет МИФИ |
| `A5016479284`, `A5057621684` | A. Y. Polyakov; Alexander Yu. Polyakov | Национальный исследовательский технологический университет МИСиС |
| `A5019420372`, `A5107865413` | S. P. Vyatchanin | Московский государственный университет |
| `A5019834066`, `A5042650363`, `A5085080728` | Z. D. Kvon | Новосибирский государственный университет |
| `A5020854221`, `A5101759965` | A Popov; Alexey Popov | Санкт-Петербургский государственный университет |
| `A5020992544`, `A5108016000` | A. A. Talyshev | Новосибирский государственный университет |
| `A5021338684`, `A5088439768` | А. М. Никишин | Московский государственный университет |
| `A5022864448`, `A5065545442` | Denis Nasonov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5023538332`, `A5065227028` | Filipp Milovich | Национальный исследовательский технологический университет МИСиС |
| `A5023542344`, `A5051633061` | А. В. Зайцев | Новосибирский государственный университет |
| `A5024264128`, `A5102844258` | Mikhail Sokolov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5024293401`, `A5077797377`, `A5107882518` | P. Kravtsov | Национальный исследовательский ядерный университет МИФИ |
| `A5024835773`, `A5070749472` | Alexander Kovalev | Новосибирский государственный университет |
| `A5025655729`, `A5043502396` | Dmitry Yudin | Московский физико-технический институт |
| `A5025903764`, `A5107892335` | S. M. Polozov | Национальный исследовательский ядерный университет МИФИ |
| `A5026461510`, `A5109012516` | I. I. Yashin | Национальный исследовательский ядерный университет МИФИ |
| `A5026872631`, `A5111379429` | G. V. Shlyapnikov | Московский физико-технический институт |
| `A5027250769`, `A5102877110` | Vladimir Gurvich | Высшая школа экономики |
| `A5027535433`, `A5100720596` | F. Ratnikov | Высшая школа экономики |
| `A5028714719`, `A5107841926` | V. A. Kuzmin | Московский государственный университет |
| `A5029231453`, `A5070101030` | Vladislav Belov; Vasily Belov | Московский государственный университет |
| `A5029456810`, `A5078117318` | Anna Orlova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5029690932`, `A5087182897` | А. А. Остроушко | Уральский федеральный университет |
| `A5029991439`, `A5102874271` | Ruimin Ma | Санкт-Петербургский государственный университет |
| `A5030054541`, `A5103095641` | Alexey A. Dmitriev; A. A. Dmitriev | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5030458413`, `A5087847801` | В. П. Тарасов | Национальный исследовательский технологический университет МИСиС |
| `A5031459441`, `A5113580330` | Н. Н. Михайлов | Новосибирский государственный университет |
| `A5031883719`, `A5047112856` | Sergey V. Fedorov | Московский государственный университет |
| `A5032432142`, `A5105369358` | Sergei Kuksin | Высшая школа экономики |
| `A5032916454`, `A5101512470` | Anna Zakharova | Уральский федеральный университет |
| `A5032946262`, `A5103045560` | B. P. Gorshunov | Московский физико-технический институт |
| `A5032953140`, `A5103860336` | Alexander Kuznetsov | Высшая школа экономики |
| `A5033001413`, `A5064778458` | А. В. Миронов | Московский государственный университет |
| `A5034609382`, `A5078269930`, `A5105684797` | A. V. Brandin | Национальный исследовательский ядерный университет МИФИ |
| `A5034711870`, `A5089205971` | Alexey Kuznetsov | Санкт-Петербургский государственный университет |
| `A5034853571`, `A5107025957` | I. B. Nikolaev | Новосибирский государственный университет |
| `A5035548480`, `A5114006789` | M. A. Vasiliev; M.A. Vasiliev | Московский физико-технический институт |
| `A5036176203`, `A5109181758` | S.D. Kaloshkin | Национальный исследовательский технологический университет МИСиС |
| `A5036225416`, `A5053022246` | M. Yu. Plotnikov; M.Yu. Plotnikov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5036787324`, `A5065755742` | G.V. Fedotovich | Новосибирский государственный университет |
| `A5036860932`, `A5060363780` | E. K. Guseva; E K Guseva | Московский физико-технический институт |
| `A5037470790`, `A5081306441` | Tatiana Nikitina | Санкт-Петербургский государственный университет |
| `A5037559872`, `A5102942400` | Alexandr V. Vinogradov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5038064113`, `A5053269705` | E. S. Andrianov | Московский физико-технический институт |
| `A5038969283`, `A5079460480` | Sergey M. Vlasov; S. M. Vlasov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5039093092`, `A5103422981` | Е. А. Иванова | Высшая школа экономики |
| `A5039177559`, `A5067384980` | Ekaterina Ivanova | Высшая школа экономики |
| `A5040137879`, `A5101671641`, `A5101671642` | Ismail Hossain; I. Hossain | Уральский федеральный университет |
| `A5040781090`, `A5074238659` | Igor Makarov; Ilya Makarov | Высшая школа экономики |
| `A5041240191`, `A5109050521` | A. Garmash | Новосибирский государственный университет |
| `A5042320241`, `A5069241547` | Viacheslav Kravtsov; Vasily Kravtsov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5042929390`, `A5107937750`, `A5109059147`, `A5112425469` | M. N. Achasov | Новосибирский государственный университет |
| `A5044324082`, `A5102984978` | Egor V. Verbitskiy | Уральский федеральный университет |
| `A5046043197`, `A5053293606` | Andrey Bogdanov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5048225771`, `A5110348237` | С. В. Сазонов | Московский авиационный институт |
| `A5048721431`, `A5075392699` | Juanwen Zhang; Jingrui Zhang | Московский государственный университет |
| `A5048935741`, `A5111549769` | Alexander Nazin | Московский физико-технический институт |
| `A5049446261`, `A5100418969` | Zheng Li; Zhang Li | Московский государственный университет |
| `A5050234205`, `A5103438122` | А. А. Васин | Московский физико-технический институт |
| `A5052981534`, `A5059972777` | G. A. Bobkov | Московский физико-технический институт |
| `A5053958270`, `A5088670343` | Yu. E. Gorbachev; Yuriy E. Gorbachev | Новосибирский государственный университет |
| `A5054361884`, `A5107863071` | V. P. Druzhinin | Новосибирский государственный университет |
| `A5054714368`, `A5088025607` | A. Yu. Nikulin; Arthur Yu. Nikulin | Новосибирский государственный университет |
| `A5055604670`, `A5076457015` | А. М. Попов | Московский государственный университет |
| `A5056431163`, `A5109051959` | Yu. V. Stenkin; Yuri V. Stenkin | Московский физико-технический институт |
| `A5057883966`, `A5078906808` | Yury A. Zolotov; Yu. A. Zolotov | Московский государственный университет |
| `A5060532392`, `A5103087079` | V. L. Minaev | Высшая школа экономики |
| `A5061702558`, `A5103463150` | A. B. Fedotov | Московский государственный университет |
| `A5061868894`, `A5103095561` | А. В. Бабкин | Московский государственный университет |
| `A5062359608`, `A5139486172` | M. N. Skripalenko | Национальный исследовательский технологический университет МИСиС |
| `A5063155145`, `A5085228510` | Yulia S. Petrova; Yu. S. Petrova | Уральский федеральный университет |
| `A5063947024`, `A5082562633` | Елена Горбунова | Высшая школа экономики |
| `A5064014153`, `A5107824790`, `A5107830433`, `A5107944690` | A. Taranenko | Национальный исследовательский ядерный университет МИФИ |
| `A5065436172`, `A5070879850`, `A5105053363`, `A5107887765` | V. Samsonov | Национальный исследовательский ядерный университет МИФИ |
| `A5067596892`, `A5089233753`, `A5105466486`, `A5110222732` | S. I. Serednyakov | Новосибирский государственный университет |
| `A5068515774`, `A5105525267` | V. E. Blinov | Новосибирский государственный университет |
| `A5070079249`, `A5103433962` | Mariia Molodchik; Mariya Molodchik | Высшая школа экономики |
| `A5071051369`, `A5101571040`, `A5101884698` | В. В. Иванов | Московский физико-технический институт |
| `A5071361156`, `A5101886811`, `A5107905940` | Igor A. Bilenko; I. A. Bilenko | Московский государственный университет |
| `A5071413061`, `A5107772566` | A. N. Vasiliev | Национальный исследовательский ядерный университет МИФИ |
| `A5072170672`, `A5078599418` | Konstantin Zimenko | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5072219813`, `A5086022271` | Anna Kuzminova | Санкт-Петербургский государственный университет |
| `A5074409263`, `A5108085050` | Vjacheslav V. Zuev | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5074514813`, `A5113871466` | Valentine G. Nenajdenko; Valentin G. Nenajdenko | Московский государственный университет |
| `A5074558450`, `A5082955833` | Md Monirul Islam; Md. Monirul Islam | Уральский федеральный университет |
| `A5077190182`, `A5103192579` | Ivan N. Shatsky | Московский государственный университет |
| `A5077449726`, `A5112114077` | Shuanglin Chen; Sili Chen | Московский государственный университет |
| `A5079197179`, `A5101537797` | Sergey Leonov | Московский физико-технический институт |
| `A5079369225`, `A5112523666` | Г. Г. Бондаренко | Высшая школа экономики |
| `A5079604981`, `A5103830088` | Mikhail V. Volkov; M. V. Volkov | Уральский федеральный университет |
| `A5079662185`, `A5101402799` | Mohammad Reza Bahrami | Автономная некоммерческая организация высшего образования Университет Иннополис |
| `A5079728421`, `A5090172823` | Alexey V. Egorov; Andrei V. Egorov | Санкт-Петербургский государственный университет |
| `A5079853539`, `A5105273914` | N. Nikitin; N Nikitin | Московский физико-технический институт |
| `A5080649530`, `A5101604481` | Alexander Ponomarenko; Alexey Ponomarenko | Высшая школа экономики |
| `A5081118743`, `A5108684386` | N.V. Kudrevatykh; N. V. Kudrevatykh | Уральский федеральный университет |
| `A5081290114`, `A5108036173` | Denis Nazarov | Санкт-Петербургский государственный университет |
| `A5082448405`, `A5112595143` | A. B. Yaroslavtsev | Высшая школа экономики |
| `A5082678277`, `A5103501465` | А. Р. Хохлов | Московский государственный университет |
| `A5083006127`, `A5087627275` | Leonid Kogan | Высшая школа экономики |
| `A5084784712`, `A5101978823` | Mikhail Ivanov | Московский государственный технический университет имени Н. Э. Баумана |
| `A5084819139`, `A5108092830` | A. Kalinin | Высшая школа экономики |
| `A5085706021`, `A5108412021` | T. V. Murzina | Московский государственный университет |
| `A5086282074`, `A5107931070` | L. Kochenda | Национальный исследовательский ядерный университет МИФИ |
| `A5086601715`, `A5108129686` | V. Aulchenko | Новосибирский государственный университет |
| `A5087542455`, `A5105788894` | Ajith Abraham | Автономная некоммерческая организация высшего образования Университет Иннополис |
| `A5088511906`, `A5090358918` | E. V. Chulkov | Высшая школа экономики |
| `A5088840800`, `A5111857901` | Н. В. Никоноров | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5088927471`, `A5108113112` | Alexander Studenikin | Московский государственный университет |
| `A5090010304`, `A5111233313` | İmran Ali; Iman Ali | Высшая школа экономики |
| `A5090374647`, `A5103712290` | М. П. Федорук | Новосибирский государственный университет |
| `A5090797638`, `A5108489624` | Yu. A. Ustynyuk; Yuri A. Ustynyuk | Московский государственный университет |
| `A5091144798`, `A5091568619` | N. Morozov; Nikita Morozov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5091275818`, `A5102754973` | Muhammad Aslam | Уральский федеральный университет |
| `A5100392599`, `A5100613162` | Wenjuan Wang | Санкт-Петербургский государственный университет |
| `A5100394566`, `A5100752423` | Jing Liu; Jiarui Liu | Санкт-Петербургский государственный университет |
| `A5100666835`, `A5100681630` | Shan Gao | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5100669202`, `A5103261216` | Waqas Ahmed | Высшая школа экономики |
| `A5100694706`, `A5101761090` | Xiangjun Liao; Xinyu Liao | Московский государственный университет |
| `A5100699646`, `A5106277732` | А. В. Иванов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5101424151`, `A5108113194` | Sergei V. Trukhanov; Sergey V. Trukhanov | Национальный исследовательский технологический университет МИСиС |
| `A5101946706`, `A5108078829` | Vladimir Mironov | Национальный исследовательский технологический университет МИСиС |
| `A5102899689`, `A5108061463` | Ahmad Hammoud | Московский государственный технический университет имени Н. Э. Баумана |
| `A5102986864`, `A5103264642` | Anton Tcypkin | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики |
| `A5102994577`, `A5112209348` | Anna Gladkova | Высшая школа экономики |
| `A5103692606`, `A5112979002` | С. В. Алексеенко | Новосибирский государственный университет |
| `A5107393035`, `A5108070794` | I. Machulin | Национальный исследовательский ядерный университет МИФИ |
| `A5107807658`, `A5115596989` | Liu W; Wei Liu | Санкт-Петербургский государственный университет |
| `A5107845551`, `A5114043098` | L. Shekhtman | Новосибирский государственный университет |
| `A5107890601`, `A5112367657` | A. G. Kharlamov | Новосибирский государственный университет |
| `A5108537085`, `A5113628428` | M. Perfilov | Московский государственный университет |
| `A5109420860`, `A5109728544` | Jing Ma | Новосибирский государственный университет |
| `A5111760858`, `A5111856013` | Yuriy Makhlin; Yu. Makhlin | Высшая школа экономики |

## Подозрение на чужую склейку — все 267

Работы профиля распадаются на две тематические группы без общей подобласти. Расклейка не делается: делить работы между людьми, которых мы не знаем, нечем. На фронте флаг пока не показывается.

### Топ-20 по размеру меньшей тематической группы — смотреть эти

| Автор | Имя | Вуз | Работ | Группы | Темы |
|---|---|---|---|---|---|
| `A5025268957` | Vladimir N. Mikhaylov | Санкт-Петербургский государственный университет | 25 | 13+12 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Catalytic Cross-Coupling Reactions; N-Heterocyclic Carbenes in Organic and Inorganic Chemistry |
| `A5034427136` | Andrey Yu. Konyaev | Уральский федеральный университет | 25 | 13+12 | Nonlinear Waves and Solitons; Algebraic structures and combinatorial models; Advanced Topics in Algebra; Electric Power Systems and Control |
| `A5059798297` | Vasiliy Fomenko | Уральский федеральный университет | 25 | 12+12 | Radiation Detection and Scintillator Technologies; Nuclear Physics and Applications; Spectroscopy and Quantum Chemical Studies; Semiconductor materials and devices |
| `A5069508961` | С. В. Малышев | Санкт-Петербургский государственный университет | 25 | 13+12 | Geological and Geochemical Analysis; Wheat and Barley Genetics and Pathology; Geological Studies and Exploration; Geochemistry and Geologic Mapping |
| `A5111524384` | V. A. Zubov | Санкт-Петербургский государственный университет | 25 | 12+12 | Optical and Acousto-Optic Technologies; Optical Polarization and Ellipsometry; Spectroscopy Techniques in Biomedical and Chemical Research; Atmospheric Ozone and Climate |
| `A5004388867` | S. V. Fedorov | Высшая школа экономики | 25 | 13+11 | Marine and coastal ecosystems; Atmospheric and Environmental Gas Dynamics; Engineering Technology and Methodologies; Water Quality Monitoring and Analysis |
| `A5013206562` | А. S. Alekseev | Высшая школа экономики | 25 | 13+11 | Geological Studies and Exploration; Paleontology and Stratigraphy of Fossils; Hydrocarbon exploration and reservoir analysis; Geological and Geochemical Analysis |
| `A5057931192` | S V Kireev | Национальный исследовательский ядерный университет МИФИ | 25 | 12+11 | Spectroscopy and Laser Applications; Laser Design and Applications; Atmospheric and Environmental Gas Dynamics; Advanced Chemical Sensor Technologies |
| `A5058183061` | Anton I. Kanev | Московский государственный технический университет имени Н. Э. Баумана | 25 | 12+11 | Remote Sensing and LiDAR Applications; Remote Sensing in Agriculture; Semantic Web and Ontologies; Advanced Computational Techniques and Applications |
| `A5063730286` | A. A. Fomichev | Московский физико-технический институт | 25 | 14+11 | Advanced Fiber Laser Technologies; Solid State Laser Technologies; Laser Design and Applications; Geophysics and Sensor Technology |
| `A5082380865` | К. В. Пугачев | Новосибирский государственный университет | 25 | 11+11 | Particle physics theoretical and experimental studies; Mosquito-borne diseases and control; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research |
| `A5082582724` | A. V. Golubkov | Высшая школа экономики | 25 | 13+11 | Rare-earth and actinide compounds; Solid-state spectroscopy and crystallography; Material Science and Thermodynamics; Magnetic Properties of Alloys |
| `A5101462418` | Hongzhi Yu | Уральский федеральный университет | 25 | 12+11 | Astrophysics and Star Formation Studies; Atmospheric Ozone and Climate; Stellar, planetary, and galactic studies; Astro and Planetary Science |
| `A5107980327` | А. Антонов | Московский государственный университет | 25 | 14+11 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Particle Detector Development and Performance |
| `A5108684386` | N. V. Kudrevatykh | Уральский федеральный университет | 25 | 13+11 | Chemical synthesis and pharmacological studies; Magnetic Properties of Alloys; Magnetic and transport properties of perovskites and related materials; Rare-earth and actinide compounds |
| `A5113833663` | А. В. Лобода | Московский государственный университет | 25 | 14+11 | Holomorphic and Operator Theory; Algebraic and Geometric Analysis; Analytic and geometric function theory; Geometric Analysis and Curvature Flows |
| `A5002397716` | Ilia Semenkov | Высшая школа экономики | 22 | 12+10 | Functional Brain Connectivity Studies; EEG and Brain-Computer Interfaces; Neurobiology of Language and Bilingualism; Advanced Vision and Imaging |
| `A5003859451` | D. Karpenkov | Национальный исследовательский технологический университет МИСиС | 25 | 15+10 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Magnetic Properties of Alloys |
| `A5010483789` | V. I. Subbotin | Московский государственный университет | 25 | 15+10 | Heat Transfer and Boiling Studies; Advanced ceramic materials synthesis; Nuclear reactor physics and engineering; Heat transfer and supercritical fluids |
| `A5013480255` | L. A. Pozdnyakov | Московский государственный университет | 25 | 13+10 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Soil Carbon and Nitrogen Dynamics |

### Полный список — все 267, по id

| Автор | Имя | Вуз | Работ | Группы | Темы |
|---|---|---|---|---|---|
| `A5000304332` | A. G. Antipov | Санкт-Петербургский государственный университет | 25 | 17+8 | Non-Destructive Testing Techniques; Quantum optics and atomic interactions; Welding Techniques and Residual Stresses; Magnetic Properties and Applications |
| `A5001854808` | А. А. Романов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 11+9 | Respiratory Support and Mechanisms; Cardiac, Anesthesia and Surgical Outcomes; Airway Management and Intubation Techniques; Geotechnical and Geomechanical Engineering |
| `A5002397716` | Ilia Semenkov | Высшая школа экономики | 22 | 12+10 | Functional Brain Connectivity Studies; EEG and Brain-Computer Interfaces; Neurobiology of Language and Bilingualism; Advanced Vision and Imaging |
| `A5002852128` | Konstantin Yu. Kulichikhin | Санкт-Петербургский государственный университет | 18 | 10+8 | Plant Stress Responses and Tolerance; Plant responses to water stress; Alzheimer's disease research and treatments; Prion Diseases and Protein Misfolding |
| `A5003859451` | D. Karpenkov | Национальный исследовательский технологический университет МИСиС | 25 | 15+10 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Magnetic Properties of Alloys |
| `A5004388867` | S. V. Fedorov | Высшая школа экономики | 25 | 13+11 | Marine and coastal ecosystems; Atmospheric and Environmental Gas Dynamics; Engineering Technology and Methodologies; Water Quality Monitoring and Analysis |
| `A5004535584` | Aleksei Y. Kondratev | Высшая школа экономики | 24 | 16+6 | Game Theory and Voting Systems; Auction Theory and Applications; Electoral Systems and Political Participation; Game Theory and Applications |
| `A5004774159` | З.Г. Кокаева | Московский государственный университет | 25 | 13+9 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Migraine and Headache Studies |
| `A5005012128` | A. Vorobyev | Московский физико-технический институт | 25 | 18+7 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Photonic and Optical Devices |
| `A5005222164` | E. I. Komotskiy | Уральский федеральный университет | 11 | 5+3 | Economic and Technological Systems Analysis; Complex Network Analysis Techniques; Neural Networks and Applications; Impact of Technology on Adolescents |
| `A5005444451` | A. P. Karamyshev | Московский физико-технический институт | 23 | 15+6 | Metallurgy and Material Forming; Metal Alloys Wear and Properties; Diverse Industrial Engineering Technologies; Metal Forming Simulation Techniques |
| `A5006715496` | I. A. Gorbunova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 17+8 | Chemical synthesis and pharmacological studies; Synthesis of heterocyclic compounds; Synthesis and biological activity; Synthesis and Reactions of Organic Compounds |
| `A5007151249` | Mingyuan Wang | Уральский федеральный университет | 25 | 12+7 | Integrated Energy Systems Optimization; Building Energy and Comfort Optimization; Smart Grid Energy Management; Neutrino Physics Research |
| `A5007381886` | Igor Baklanov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 10+7 | Sociopolitical Dynamics in Russia; RNA modifications and cancer; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies |
| `A5007707633` | A. V. Gubanov | Московский физико-технический институт | 25 | 16+9 | Methane Hydrates and Related Phenomena; Complex Network Analysis Techniques; Combustion and Detonation Processes; Innovations in Concrete and Construction Materials |
| `A5008840687` | Alexey A. Gorbunov | Новосибирский государственный университет | 25 | 13+8 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Chemical synthesis and pharmacological studies; Synthesis and Biological Evaluation |
| `A5010174582` | L. I. Men’shikov | Московский физико-технический институт | 25 | 14+9 | Atomic and Molecular Physics; Advanced Chemical Physics Studies; Muon and positron interactions and applications; Genetics, Aging, and Longevity in Model Organisms |
| `A5010483789` | V. I. Subbotin | Московский государственный университет | 25 | 15+10 | Heat Transfer and Boiling Studies; Advanced ceramic materials synthesis; Nuclear reactor physics and engineering; Heat transfer and supercritical fluids |
| `A5010522861` | О. В. Тарасова | Новосибирский государственный университет | 25 | 13+8 | Forest Insect Ecology and Management; Arctic and Russian Policy Studies; Fire effects on ecosystems; Animal Ecology and Behavior Studies |
| `A5011298864` | Maria Smirnova | Санкт-Петербургский государственный университет | 25 | 14+9 | Digital Marketing and Social Media; Business Strategy and Innovation; Customer Service Quality and Loyalty; Innovation and Knowledge Management |
| `A5011818851` | Sergey V. Smirnov | Высшая школа экономики | 25 | 15+9 | Economic and Technological Developments in Russia; Monetary Policy and Economic Impact; Russia and Soviet political economy; Chromosomal and Genetic Variations |
| `A5012146146` | L B Chen | Московский государственный университет | 14 | 8+4 | RNA and protein synthesis mechanisms; Immunotherapy and Immune Responses; Cell Adhesion Molecules Research; Crime and Detective Fiction Studies |
| `A5013206562` | А. S. Alekseev | Высшая школа экономики | 25 | 13+11 | Geological Studies and Exploration; Paleontology and Stratigraphy of Fossils; Hydrocarbon exploration and reservoir analysis; Geological and Geochemical Analysis |
| `A5013480255` | L. A. Pozdnyakov | Московский государственный университет | 25 | 13+10 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Soil Carbon and Nitrogen Dynamics |
| `A5014763226` | V. V. Nikulin | Национальный исследовательский ядерный университет МИФИ | 25 | 14+8 | Black Holes and Theoretical Physics; Cosmology and Gravitation Theories; Synthesis and biological activity; Synthesis and Characterization of Heterocyclic Compounds |
| `A5015236020` | А. В. Мишин | Новосибирский государственный университет | 25 | 15+10 | Advanced Fiber Laser Technologies; Laser-Matter Interactions and Applications; Composite Material Mechanics; Advanced Mathematical Modeling in Engineering |
| `A5015611534` | Xuan Qiu | Санкт-Петербургский государственный университет | 25 | 14+9 | Advanced battery technologies research; Advanced Battery Materials and Technologies; Supercapacitor Materials and Fabrication; Advancements in Battery Materials |
| `A5015638659` | A.V. Kazansky | Санкт-Петербургский государственный университет | 25 | 13+8 | Oceanographic and Atmospheric Processes; Cytokine Signaling Pathways and Interactions; Meteorological Phenomena and Simulations; Animal Genetics and Reproduction |
| `A5016262778` | Н. П. Ерофеев | Санкт-Петербургский государственный университет | 25 | 12+8 | Thermoregulation and physiological responses; Chaos control and synchronization; Peripheral Artery Disease Management; Diabetic Foot Ulcer Assessment and Management |
| `A5016289155` | I. M. Chernenko | Уральский федеральный университет | 25 | 17+8 | Transition Metal Oxide Nanomaterials; Gas Sensing Nanomaterials and Sensors; Glass properties and applications; Catalysis and Oxidation Reactions |
| `A5016887914` | Malikakhon Kurbonova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 12 | 7+4 | Anaerobic Digestion and Biogas Production; Biofuel production and bioconversion; Methane Hydrates and Related Phenomena; Bee Products Chemical Analysis |
| `A5016903897` | L. A. Beklaryan | Московский физико-технический институт | 25 | 12+9 | Differential Equations and Numerical Methods; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5016992559` | Anna Likhacheva | Новосибирский государственный университет | 25 | 15+8 | Advanced Radiotherapy Techniques; Advances in Oncology and Radiotherapy; High-pressure geophysics and materials; Geological and Geochemical Analysis |
| `A5017101024` | С. Е. Табалин | Московский государственный технический университет имени Н. Э. Баумана | 25 | 18+7 | Spectroscopy and Laser Applications; Calibration and Measurement Techniques; Atmospheric Ozone and Climate; Pulsars and Gravitational Waves Research |
| `A5017593597` | Maxim Shkurin | Московский авиационный институт | 11 | 8+3 | Material Properties and Applications; Spacecraft Dynamics and Control; Aerospace Engineering and Energy Systems; Heat Transfer and Mathematical Modeling |
| `A5017642500` | Muhammad Ahsan | Высшая школа экономики | 20 | 8+8 | Microgrid Control and Optimization; Innovative concrete reinforcement materials; Optimal Power Flow Distribution; Concrete and Cement Materials Research |
| `A5017961417` | Б. Семенов | Уральский федеральный университет | 25 | 13+9 | Planetary Science and Exploration; Astro and Planetary Science; Space Exploration and Technology; Distributed and Parallel Computing Systems |
| `A5018839817` | N. P. Alekseev | Санкт-Петербургский государственный университет | 25 | 17+8 | Breastfeeding Practices and Influences; Infant Nutrition and Health; Infant Health and Development; Neuroscience and Neuropharmacology Research |
| `A5018920230` | Nadezhda Smirnova | Высшая школа экономики | 25 | 17+7 | Game Theory and Applications; Economic theories and models; Game Theory and Voting Systems; Auction Theory and Applications |
| `A5019336215` | Svetlana M. Bauer | Санкт-Петербургский государственный университет | 25 | 15+8 | Corneal surgery and disorders; Glaucoma and retinal disorders; Composite Structure Analysis and Optimization; Ophthalmology and Visual Impairment Studies |
| `A5019849324` | Н. А. Кругликов | Уральский федеральный университет | 25 | 13+10 | Astro and Planetary Science; Planetary Science and Exploration; Intermetallics and Advanced Alloy Properties; Magnetic and Electromagnetic Effects |
| `A5020560197` | Rostislav Streletskii | Московский государственный университет | 25 | 16+7 | Microbial bioremediation and biosurfactants; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5020854221` | A Popov | Санкт-Петербургский государственный университет | 25 | 16+7 | Agriculture and Biological Studies; Soil Carbon and Nitrogen Dynamics; Soil and Environmental Studies; Chemical Thermodynamics and Molecular Structure |
| `A5020917675` | D. P. Shcherbinin | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 16+8 | Liquid Crystal Research Advancements; Gold and Silver Nanoparticles Synthesis and Applications; Quantum Dots Synthesis And Properties; Photonic Crystals and Applications |
| `A5021146123` | Maria Volkova | Московский государственный технический университет имени Н. Э. Баумана | 25 | 14+7 | Global Energy Security and Policy; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5022322416` | Artemii M. Zenkin | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 13 | 8+4 | Biosensors and Analytical Detection; Advanced Chemical Sensor Technologies; Advanced Biosensing Techniques and Applications; Advanced Data Processing Techniques |
| `A5022483491` | Иван А. Кочнев | Уральский федеральный университет | 25 | 18+7 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Fluorine in Organic Chemistry; Synthesis and Characterization of Pyrroles |
| `A5022493280` | T.A. Agasiev | Московский государственный технический университет имени Н. Э. Баумана | 10 | 6+3 | Metaheuristic Optimization Algorithms Research; Advanced Multi-Objective Optimization Algorithms; Advanced Optimization Algorithms Research; Optimal Experimental Design Methods |
| `A5022509400` | Andrey Vlasov | Высшая школа экономики | 25 | 9+7 | Transcranial Magnetic Stimulation Studies; Organometallic Complex Synthesis and Catalysis; Blockchain Technology Applications and Security; Asymmetric Hydrogenation and Catalysis |
| `A5022852796` | В. В. Матвеев | Санкт-Петербургский государственный университет | 25 | 16+8 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Ionic liquids properties and applications |
| `A5023037996` | V. V. Parkhomchuk | Новосибирский государственный университет | 25 | 14+7 | Nuclear Physics and Applications; Particle Accelerators and Free-Electron Lasers; Mass Spectrometry Techniques and Applications; Particle accelerators and beam dynamics |
| `A5023714423` | Галина Чернова | Санкт-Петербургский государственный университет | 25 | 18+7 | Coal Combustion and Slurry Processing; Educational Innovations and Challenges; Economic and Technological Developments in Russia; Thermochemical Biomass Conversion Processes |
| `A5023797459` | Vladimir Valentinovich Kozhevnikov | Московский авиационный институт | 25 | 14+10 | Legal and Policy Issues; Security, Politics, and Digital Transformation; Legal and Regulatory Analysis; Education, Law, and Society |
| `A5023799323` | Anton Mitrofanov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 14 | 9+4 | Speech Recognition and Synthesis; Music and Audio Processing; Speech and Audio Processing; Distributed and Parallel Computing Systems |
| `A5023970079` | Mikhail A. Kamenskii | Санкт-Петербургский государственный университет | 25 | 18+7 | Advancements in Battery Materials; Advanced Battery Materials and Technologies; Advanced Battery Technologies Research; Advanced battery technologies research |
| `A5024166981` | Anna Lantsberg | Московский государственный технический университет имени Н. Э. Баумана | 20 | 10+7 | Advanced Chemical Sensor Technologies; Gas Sensing Nanomaterials and Sensors; Analytical Chemistry and Sensors; Health Literacy and Information Accessibility |
| `A5024387874` | Pengyi Li | Санкт-Петербургский государственный университет | 25 | 12+8 | Respiratory Support and Mechanisms; Reinforcement Learning in Robotics; Model-Driven Software Engineering Techniques; Cancer, Stress, Anesthesia, and Immune Response |
| `A5024623698` | Б. Н. Миронов | Санкт-Петербургский государственный университет | 25 | 11+8 | Soviet and Russian History; Russia and Soviet political economy; Advanced Electron Microscopy Techniques and Applications; Laser-Matter Interactions and Applications |
| `A5025268957` | Vladimir N. Mikhaylov | Санкт-Петербургский государственный университет | 25 | 13+12 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Catalytic Cross-Coupling Reactions; N-Heterocyclic Carbenes in Organic and Inorganic Chemistry |
| `A5026149983` | Guzal Khayrullina | Высшая школа экономики | 25 | 17+8 | Obsessive-Compulsive Spectrum Disorders; Anxiety, Depression, Psychometrics, Treatment, Cognitive Processes; Neuroinflammation and Neurodegeneration Mechanisms; Immune Cell Function and Interaction |
| `A5026185204` | О. В. Крылов | Московский государственный университет | 25 | 15+10 | Catalysis and Oxidation Reactions; Catalytic Processes in Materials Science; Catalysis and Hydrodesulfurization Studies; Geological Studies and Exploration |
| `A5026392555` | А. В. Таганов | Новосибирский государственный университет | 25 | 13+8 | Dermatology and Skin Diseases; COVID-19 Clinical Research Studies; SARS-CoV-2 and COVID-19 Research; Skin Protection and Aging |
| `A5026722038` | Sergei A. Filin | Московский физико-технический институт | 25 | 12+7 | Economic and Technological Developments in Russia; Regional Economic Development and Innovation; Economic and Technological Systems Analysis; Economic Development and Digital Transformation |
| `A5027137604` | A. M. Zadorozhny | Новосибирский государственный университет | 25 | 11+8 | Atmospheric Ozone and Climate; Ionosphere and magnetosphere dynamics; Atmospheric and Environmental Gas Dynamics; Quantum Chromodynamics and Particle Interactions |
| `A5027431619` | S. Alexandrova | Московский авиационный институт | 25 | 15+7 | Semiconductor materials and devices; Silicon Nanostructures and Photoluminescence; Thin-Film Transistor Technologies; Silicon and Solar Cell Technologies |
| `A5027724136` | T. V. Lapina | Санкт-Петербургский государственный университет | 25 | 18+7 | Photosynthetic Processes and Mechanisms; Algal biology and biofuel production; Inorganic and Organometallic Chemistry; Organic and Molecular Conductors Research |
| `A5028947243` | Alexandra Klímová | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 11+9 | Scientific Computing and Data Management; Big Data and Business Intelligence; Green IT and Sustainability; IoT and Edge/Fog Computing |
| `A5029831200` | A. Yu. Kazantseva | Московский физико-технический институт | 20 | 15+5 | Adipose Tissue and Metabolism; Fibroblast Growth Factor Research; Epigenetics and DNA Methylation; Kruppel-like factors research |
| `A5029991439` | Ruimin Ma | Санкт-Петербургский государственный университет | 19 | 10+8 | Diverse Aspects of Tourism Research; Urban Transport and Accessibility; Supply Chain and Inventory Management; Environmental Impact and Sustainability |
| `A5030167121` | Е. А. Морозова | Национальный исследовательский ядерный университет МИФИ | 25 | 17+7 | earthquake and tectonic studies; High-pressure geophysics and materials; Laser Design and Applications; Geological and Geochemical Analysis |
| `A5031444671` | O. Grishin | Новосибирский государственный университет | 25 | 14+7 | Astrophysics and Cosmic Phenomena; Neutrino Physics Research; Dark Matter and Cosmic Phenomena; Photoacoustic and Ultrasonic Imaging |
| `A5031641614` | E. M. Gromov | Высшая школа экономики | 25 | 17+8 | Nonlinear Photonic Systems; Nonlinear Waves and Solitons; Advanced Fiber Laser Technologies; Particle physics theoretical and experimental studies |
| `A5032039676` | М. А. Баранов | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 13+8 | Cold Atom Physics and Bose-Einstein Condensates; Quantum, superfluid, helium dynamics; Physics of Superconductivity and Magnetism; Quantum Dots Synthesis And Properties |
| `A5032931428` | В. В. Лебедев | Высшая школа экономики | 25 | 12+7 | Advanced Harmonic Analysis Research; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5033775794` | Natalia A. Lozinskaya | Московский государственный университет | 25 | 16+7 | Corrosion Behavior and Inhibition; Concrete Corrosion and Durability; Synthesis and biological activity; Free Radicals and Antioxidants |
| `A5033921904` | Arina Pavlova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 14 | 9+4 | Gold and Silver Nanoparticles Synthesis and Applications; Solid State Laser Technologies; Laser Design and Applications; Quantum Dots Synthesis And Properties |
| `A5034427136` | Andrey Yu. Konyaev | Уральский федеральный университет | 25 | 13+12 | Nonlinear Waves and Solitons; Algebraic structures and combinatorial models; Advanced Topics in Algebra; Electric Power Systems and Control |
| `A5034462085` | Oleg I. Borisov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 18+7 | Adaptive Control of Nonlinear Systems; Stability and Control of Uncertain Systems; Aerospace Engineering and Control Systems; Stability and Controllability of Differential Equations |
| `A5034711870` | Alexey Kuznetsov | Санкт-Петербургский государственный университет | 25 | 9+8 | Stochastic processes and financial applications; Photochemistry and Electron Transfer Studies; Spectroscopy and Quantum Chemical Studies; Molecular Junctions and Nanostructures |
| `A5034916596` | Alexander V. Osipov | Уральский федеральный университет | 25 | 15+8 | Advanced Topology and Set Theory; Advanced Banach Space Theory; Fuzzy and Soft Set Theory; Rings, Modules, and Algebras |
| `A5037842489` | Н. В. Лакиза | Уральский федеральный университет | 22 | 16+6 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Magnetic and transport properties of perovskites and related materials |
| `A5037987776` | С. А. Бабин | Новосибирский государственный университет | 25 | 17+8 | Advanced Fiber Laser Technologies; Photonic Crystal and Fiber Optics; Advanced Fiber Optic Sensors; Laser Design and Applications |
| `A5038344492` | Roman Astrakhantsev | Высшая школа экономики | 16 | 7+4 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Digital Transformation in Law |
| `A5038627423` | Zhanna Pisarenko | Санкт-Петербургский государственный университет | 25 | 16+8 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Nanotechnology research and applications |
| `A5038667261` | Татьяна Караваева | Санкт-Петербургский государственный университет | 25 | 16+9 | SARS-CoV-2 and COVID-19 Research; SARS-CoV-2 detection and testing; Environmental Monitoring and Data Management; COVID-19 Clinical Research Studies |
| `A5038864483` | S. S. Nikolaenko | Московский физико-технический институт | 21 | 10+7 | Quantum chaos and dynamical systems; Nonlinear Waves and Solitons; Diverse Scientific Research in Ukraine; Nonlinear Photonic Systems |
| `A5039985668` | А. В. Гусев | Уральский федеральный университет | 25 | 14+8 | Pulsars and Gravitational Waves Research; Geophysics and Gravity Measurements; Geophysics and Sensor Technology; Radio Astronomy Observations and Technology |
| `A5040666019` | А. А. Старікова | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 13+7 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Geology and Paleoclimatology Research |
| `A5040778329` | Ruslan Sharipov | Новосибирский государственный университет | 25 | 17+8 | Air Quality and Health Impacts; Genomics and Chromatin Dynamics; Cancer, Lipids, and Metabolism; Gene expression and cancer classification |
| `A5041538987` | В. В. Молодцов | Новосибирский государственный университет | 25 | 10+7 | Engineering Technology and Methodologies; Orthoptera Research and Taxonomy; Ecology and Vegetation Dynamics Studies; Advanced machining processes and optimization |
| `A5041565955` | D. I. Zinchenko | Высшая школа экономики | 23 | 11+6 | Semiconductor Quantum Structures and Devices; Spectroscopy and Laser Applications; Terahertz technology and applications; Human Resources and Workforce |
| `A5041697774` | Anastasia Nikitina | Санкт-Петербургский государственный университет | 25 | 12+8 | Animal Nutrition and Health; Food Industry and Aquatic Biology; Agriculture and Biological Studies; Lymphoma Diagnosis and Treatment |
| `A5041828821` | А. В. Соколов | Новосибирский государственный университет | 25 | 17+7 | Quantum Mechanics and Non-Hermitian Physics; Nonlinear Waves and Solitons; Quantum chaos and dynamical systems; Algebraic and Geometric Analysis |
| `A5041909306` | Boris B. Velichkovsky | Московский государственный университет | 25 | 14+10 | Neural and Behavioral Psychology Studies; Visual perception and processing mechanisms; Virtual Reality Applications and Impacts; Cognitive Abilities and Testing |
| `A5044422840` | Elena Zinovieva | Уральский федеральный университет | 24 | 15+6 | Economic and Technological Systems Analysis; Software Testing and Debugging Techniques; Industrial Engineering and Technologies; Formal Methods in Verification |
| `A5045403413` | D. Vlasenko | Высшая школа экономики | 25 | 17+7 | Gamma-ray bursts and supernovae; Astrophysical Phenomena and Observations; Astronomical Observations and Instrumentation; Pulsars and Gravitational Waves Research |
| `A5045576159` | Pavel A. Andreev | Московский государственный университет | 25 | 17+7 | Cold Atom Physics and Bose-Einstein Condensates; Dust and Plasma Wave Phenomena; Ionosphere and magnetosphere dynamics; Quantum, superfluid, helium dynamics |
| `A5045798482` | Olga Nekrasova | Уральский федеральный университет | 25 | 15+7 | Climate change and permafrost; Botany and Plant Ecology Studies; Soil Carbon and Nitrogen Dynamics; Marine and environmental studies |
| `A5045965506` | Sergey V. Ivanov | Московский авиационный институт | 25 | 8+7 | Risk and Portfolio Optimization; Optimization and Mathematical Programming; Optimization and Variational Analysis; Scientific Computing and Data Management |
| `A5046041765` | E. G. Malkovich | Новосибирский государственный университет | 22 | 11+8 | Advanced Differential Geometry Research; Geometric Analysis and Curvature Flows; Black Holes and Theoretical Physics; Geometry and complex manifolds |
| `A5047420518` | A. Gouskov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 14+9 | Advanced machining processes and optimization; Solid-state spectroscopy and crystallography; Advanced Surface Polishing Techniques; Semiconductor Quantum Structures and Devices |
| `A5048402137` | A. V. Kolpakov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 9+7 | Crystallography and Radiation Phenomena; Optical Imaging and Spectroscopy Techniques; Infrared Thermography in Medicine; X-ray Diffraction in Crystallography |
| `A5048452037` | А. А. Повзнер | Уральский федеральный университет | 25 | 15+9 | Rare-earth and actinide compounds; Magnetic Properties of Alloys; Magnetic properties of thin films; Magnetic Properties and Applications |
| `A5049259288` | A. P. Molchanov | Московский авиационный институт | 25 | 18+7 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Cyclopropane Reaction Mechanisms; Fluorine in Organic Chemistry |
| `A5049545891` | V. A. Ilyin | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 15+9 | Distributed and Parallel Computing Systems; Advanced X-ray Imaging Techniques; Particle physics theoretical and experimental studies; Matrix Theory and Algorithms |
| `A5049657619` | Anna Ilina | Высшая школа экономики | 25 | 10+8 | Agriculture and Biological Studies; Animal Nutrition and Health; Food Industry and Aquatic Biology; Genetic diversity and population structure |
| `A5050025509` | A. V. Sumarokov | Московский физико-технический институт | 25 | 15+10 | Aerospace Engineering and Control Systems; Advanced Research in Science and Engineering; High-Energy Particle Collisions Research; Particle physics theoretical and experimental studies |
| `A5050223585` | Ekaterina Shevtsova | Московский государственный технический университет имени Н. Э. Баумана | 21 | 7+6 | Hymenoptera taxonomy and phylogeny; Insect-Plant Interactions and Control; Forest Insect Ecology and Management; Plant and animal studies |
| `A5052499647` | О. В. Руденко | Московский государственный университет | 24 | 11+6 | Ultrasonics and Acoustic Wave Propagation; Nonlinear Photonic Systems; Acoustic Wave Phenomena Research; Underwater Acoustics Research |
| `A5053512045` | A.A. Romanov | Национальный исследовательский технологический университет МИСиС | 25 | 14+8 | ZnO doping and properties; Ga2O3 and related materials; Advanced Photocatalysis Techniques; Oceanographic and Atmospheric Processes |
| `A5053808600` | Artem Pavlenko | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 23 | 15+7 | Cryptographic Implementations and Security; Coding theory and cryptography; Metaheuristic Optimization Algorithms Research; Formal Methods in Verification |
| `A5053959024` | Ivan Bakulin | Московский физико-технический институт | 16 | 8+5 | Fluid Dynamics and Heat Transfer; Surface Modification and Superhydrophobicity; Spectroscopy and Quantum Chemical Studies; Topic Modeling |
| `A5054031294` | Anna Epishkina | Национальный исследовательский ядерный университет МИФИ | 25 | 17+8 | Internet Traffic Analysis and Secure E-voting; Network Security and Intrusion Detection; Advanced Malware Detection Techniques; Cryptography and Data Security |
| `A5054284261` | Stanislav Smirnov | Санкт-Петербургский государственный университет | 25 | 16+7 | Stochastic processes and statistical mechanics; Theoretical and Computational Physics; Mathematical Dynamics and Fractals; Random Matrices and Applications |
| `A5054532174` | Н. В. Медведева | Московский государственный университет | 25 | 11+9 | Sociopolitical Dynamics in Russia; Legal and Policy Issues; Impulse Buying and Technology Impacts; Educational Innovations and Challenges |
| `A5054555373` | Yu. A. Danilov | Московский государственный университет | 25 | 13+8 | Semiconductor Quantum Structures and Devices; ZnO doping and properties; Magnetic properties of thin films; Quantum and electron transport phenomena |
| `A5054985657` | Anastasia Povolotckaia | Санкт-Петербургский государственный университет | 25 | 17+7 | Laser-Ablation Synthesis of Nanoparticles; Cultural Heritage Materials Analysis; Nonlinear Optical Materials Studies; Gold and Silver Nanoparticles Synthesis and Applications |
| `A5055709571` | A. Semenov | Санкт-Петербургский государственный университет | 25 | 15+7 | Particle physics theoretical and experimental studies; Dark Matter and Cosmic Phenomena; Algebraic structures and combinatorial models; Advanced Topics in Algebra |
| `A5055881938` | V. Rozov | Санкт-Петербургский государственный университет | 25 | 18+7 | Superconducting Materials and Applications; Magnetic confinement fusion research; Fusion materials and technologies; Historical and Linguistic Studies |
| `A5056107563` | Julia Agafonova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 13 | 7+6 | Cardiovascular Effects of Exercise; Sports injuries and prevention; Computational and Text Analysis Methods; Natural Language Processing Techniques |
| `A5056108259` | A. V. Leonidov | Московский физико-технический институт | 25 | 15+10 | High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Particle physics theoretical and experimental studies; Complex Systems and Time Series Analysis |
| `A5056801503` | M. A. Saif | Уральский федеральный университет | 12 | 7+3 | Radiation Shielding Materials Analysis; Complex Network Analysis Techniques; Blockchain Technology Applications and Security; Glass properties and applications |
| `A5057275468` | A. S. Zubov | Московский физико-технический институт | 25 | 17+7 | Nuclear physics research studies; Astronomical and nuclear sciences; Atomic and Molecular Physics; Advanced Chemical Physics Studies |
| `A5057455948` | N. S. Tropskaya | Московский авиационный институт | 25 | 12+10 | Diet and metabolism studies; Biochemical effects in animals; Gastrointestinal motility and disorders; Biochemical Analysis and Sensing Techniques |
| `A5057782263` | A. V. Babichev | Новосибирский государственный университет | 25 | 18+7 | Geological and Geochemical Analysis; High-pressure geophysics and materials; Geological Studies and Exploration; Carbon Nanotubes in Composites |
| `A5057931192` | S V Kireev | Национальный исследовательский ядерный университет МИФИ | 25 | 12+11 | Spectroscopy and Laser Applications; Laser Design and Applications; Atmospheric and Environmental Gas Dynamics; Advanced Chemical Sensor Technologies |
| `A5057992942` | А. Н. Тихонов | Московский государственный университет | 25 | 11+10 | Photosynthetic Processes and Mechanisms; Light effects on plants; Photoreceptor and optogenetics research; Spectroscopy and Quantum Chemical Studies |
| `A5058183061` | Anton I. Kanev | Московский государственный технический университет имени Н. Э. Баумана | 25 | 12+11 | Remote Sensing and LiDAR Applications; Remote Sensing in Agriculture; Semantic Web and Ontologies; Advanced Computational Techniques and Applications |
| `A5058530409` | D. Grigoriev | Санкт-Петербургский государственный университет | 25 | 15+7 | Paleontology and Evolutionary Biology; Evolution and Paleontology Studies; Polynomial and algebraic computation; Complex Systems and Time Series Analysis |
| `A5058535047` | Yuliya S. Zhuravleva | Новосибирский государственный университет | 13 | 7+6 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Redox biology and oxidative stress; Biochemical effects in animals |
| `A5058555774` | Anna V. Diachkova | Уральский федеральный университет | 25 | 14+9 | Educational Innovations and Challenges; Food Industry and Aquatic Biology; Security, Politics, and Digital Transformation; Microencapsulation and Drying Processes |
| `A5058628813` | Mikhail A. Kiselev | Московский государственный университет | 25 | 15+8 | Lipid Membrane Structure and Behavior; Surfactants and Colloidal Systems; Spectroscopy and Quantum Chemical Studies; Legal and Regulatory Analysis |
| `A5059798297` | Vasiliy Fomenko | Уральский федеральный университет | 25 | 12+12 | Radiation Detection and Scintillator Technologies; Nuclear Physics and Applications; Spectroscopy and Quantum Chemical Studies; Semiconductor materials and devices |
| `A5060007173` | А. И. Усов | Московский государственный технический университет имени Н. Э. Баумана | 25 | 11+7 | Ukrainian Legal and Forensic Studies; Law, AI, and Intellectual Property; Digital Transformation in Law; Education, Law, and Society |
| `A5060804170` | Yu. F. Filippov | Новосибирский государственный университет | 25 | 18+7 | Geological Studies and Exploration; Photonic and Optical Devices; Hydrocarbon exploration and reservoir analysis; Microwave and Dielectric Measurement Techniques |
| `A5061383864` | A. V. Chirkin | Московский государственный технический университет имени Н. Э. Баумана | 25 | 17+7 | Nuclear Materials and Properties; Chaos-based Image/Signal Encryption; Cybersecurity and Information Systems; Titanium Alloys Microstructure and Properties |
| `A5061451091` | S.A. Korchagin | Московский физико-технический институт | 25 | 9+8 | High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Particle physics theoretical and experimental studies; Nuclear physics research studies |
| `A5061826062` | Fedor S. Kliuev | Высшая школа экономики | 16 | 12+4 | Asymmetric Hydrogenation and Catalysis; Chemical Synthesis and Analysis; Chemical Synthesis and Reactions; Crystallization and Solubility Studies |
| `A5062050861` | V. S. Ponamarev | Санкт-Петербургский государственный университет | 25 | 16+7 | Liver Disease Diagnosis and Treatment; Drug-Induced Hepatotoxicity and Protection; Pharmacogenetics and Drug Metabolism; Animal Nutrition and Health |
| `A5062343909` | В. С. Паршин | Уральский федеральный университет | 25 | 16+8 | Metallurgy and Material Forming; Diverse Industrial Engineering Technologies; Thyroid Cancer Diagnosis and Treatment; Metal Alloys Wear and Properties |
| `A5062439853` | В. А. Садовничий | Московский государственный университет | 25 | 12+8 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Fusion and Plasma Physics Studies |
| `A5062482400` | Е. Н. Михайлова | Московский физико-технический институт | 22 | 10+9 | Marine and environmental studies; Aquatic and Environmental Studies; Oceanographic and Atmospheric Processes; Geological Studies and Exploration |
| `A5063496005` | П. А. Хаптаханова | Московский физико-технический институт | 12 | 5+5 | biodegradable polymer synthesis and properties; Boron Compounds in Chemistry; Boron and Carbon Nanomaterials Research; Bone Tissue Engineering Materials |
| `A5063535629` | Ilia Revin | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 16 | 7+5 | Evolutionary Algorithms and Applications; Machine Learning and Data Classification; Mining and Gasification Technologies; Geotechnical and Geomechanical Engineering |
| `A5063730286` | A. A. Fomichev | Московский физико-технический институт | 25 | 14+11 | Advanced Fiber Laser Technologies; Solid State Laser Technologies; Laser Design and Applications; Geophysics and Sensor Technology |
| `A5064456514` | С. С. Савченко | Уральский федеральный университет | 25 | 16+8 | Quantum Dots Synthesis And Properties; Semiconductor Quantum Structures and Devices; Chalcogenide Semiconductor Thin Films; Astrophysics and Cosmic Phenomena |
| `A5064583036` | Vasily Kornilov | Высшая школа экономики | 19 | 8+8 | Lipid Membrane Structure and Behavior; Complex Systems and Time Series Analysis; Complex Network Analysis Techniques; Ecosystem dynamics and resilience |
| `A5064611752` | Alexander Yu Derevyagin | Высшая школа экономики | 25 | 14+7 | Geology and Paleoclimatology Research; Geological Studies and Exploration; Methane Hydrates and Related Phenomena; Climate change and permafrost |
| `A5064763980` | Ilya Starodumov | Уральский федеральный университет | 25 | 9+7 | Solidification and crystal growth phenomena; Aluminum Alloy Microstructure Properties; Metallurgical Processes and Thermodynamics; Fluid Dynamics and Mixing |
| `A5064778458` | А. В. Миронов | Московский государственный университет | 25 | 14+9 | Electrospun Nanofibers in Biomedical Applications; Laser Design and Applications; Tissue Engineering and Regenerative Medicine; Crystallization and Solubility Studies |
| `A5065433622` | Veronika Yu. Yurova | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 17 | 12+5 | Advanced Photocatalysis Techniques; Electrocatalysts for Energy Conversion; Metalloenzymes and iron-sulfur proteins; Electrochemical Analysis and Applications |
| `A5065526550` | М. В. Богданова | Национальный исследовательский технологический университет МИСиС | 25 | 18+7 | Organophosphorus compounds synthesis; Additive Manufacturing Materials and Processes; Additive Manufacturing and 3D Printing Technologies; Sulfur-Based Synthesis Techniques |
| `A5065656882` | Anton Teslyuk | Московский физико-технический институт | 25 | 14+8 | Advanced X-ray Imaging Techniques; Advanced Electron Microscopy Techniques and Applications; Scientific Computing and Data Management; Genomics and Phylogenetic Studies |
| `A5065721419` | Н. А. Анисимова | Санкт-Петербургский государственный университет | 25 | 18+7 | Chemical Reaction Mechanisms; Synthesis and Reactions of Organic Compounds; Chemical Synthesis and Analysis; Fluorine in Organic Chemistry |
| `A5067853597` | Irina Kiseleva | Уральский федеральный университет | 25 | 13+10 | Cardiac electrophysiology and arrhythmias; Ion channel regulation and function; Neuroscience and Neural Engineering; Plant Stress Responses and Tolerance |
| `A5068549116` | Nataliya Tovma | Высшая школа экономики | 25 | 16+9 | Economic and Technological Developments in Russia; Economic Development and Digital Transformation; Regional Socio-Economic Development Trends; Digital Economy and Transformation |
| `A5069226546` | A. V. Serov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 14+9 | Particle Accelerators and Free-Electron Lasers; Crystallography and Radiation Phenomena; Advanced X-ray Imaging Techniques; Gyrotron and Vacuum Electronics Research |
| `A5069508961` | С. В. Малышев | Санкт-Петербургский государственный университет | 25 | 13+12 | Geological and Geochemical Analysis; Wheat and Barley Genetics and Pathology; Geological Studies and Exploration; Geochemistry and Geologic Mapping |
| `A5069613082` | I. М. Kvetnoy | Санкт-Петербургский государственный университет | 25 | 14+9 | Circadian rhythm and melatonin; Reproductive System and Pregnancy; Endometriosis Research and Treatment; Mitochondrial Function and Pathology |
| `A5070348662` | Alexandra Kuznetsova | Высшая школа экономики | 25 | 12+7 | Ocean Waves and Remote Sensing; Oceanographic and Atmospheric Processes; Tropical and Extratropical Cyclones Research; Coastal and Marine Dynamics |
| `A5070369664` | E G Shershneva | Уральский федеральный университет | 24 | 15+9 | Sustainability and Innovation in Business; Environmental Engineering and Cultural Studies; Banking stability, regulation, efficiency; Economic and Technological Systems Analysis |
| `A5070439476` | Александр Викторович Колесников | Высшая школа экономики | 25 | 11+10 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Geometric Analysis and Curvature Flows |
| `A5071402970` | Alexander Krasnikov | Высшая школа экономики | 25 | 15+7 | Statistical and numerical algorithms; Advanced Optimization Algorithms Research; Innovation and Knowledge Management; International Business and FDI |
| `A5071927214` | A. Efremov | Новосибирский государственный университет | 25 | 14+7 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Essential Oils and Antimicrobial Activity |
| `A5072791125` | А. Н. Тырсин | Уральский федеральный университет | 25 | 10+9 | Regional Socio-Economic Development Trends; Socioeconomic and Demographic Analysis; Economic and Technological Systems Analysis; Economic and Technological Developments in Russia |
| `A5073069796` | Mikhail Sarafanov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 18 | 11+7 | Arctic and Antarctic ice dynamics; Evolutionary Algorithms and Applications; Arctic and Russian Policy Studies; Hydrological Forecasting Using AI |
| `A5073075584` | V. I. Kaminsky | Национальный исследовательский ядерный университет МИФИ | 24 | 14+8 | Particle accelerators and beam dynamics; Gyrotron and Vacuum Electronics Research; Educational Innovations and Challenges; Particle Accelerators and Free-Electron Lasers |
| `A5073387855` | О. П. Колесникова | Московский физико-технический институт | 25 | 16+7 | T-cell and B-cell Immunology; Synthesis and biological activity; Synthesis and Characterization of Heterocyclic Compounds; Synthesis and Reactions of Organic Compounds |
| `A5074157239` | V. S. Travkin | Санкт-Петербургский государственный университет | 25 | 15+7 | Oceanographic and Atmospheric Processes; Heat and Mass Transfer in Porous Media; Nanofluid Flow and Heat Transfer; Geology and Paleoclimatology Research |
| `A5074884381` | Ivan Shilin | Высшая школа экономики | 18 | 8+8 | Biomedical Text Mining and Ontologies; Scientific Computing and Data Management; Topic Modeling; IoT and Edge/Fog Computing |
| `A5075032920` | С. И. Горбачев | Московский авиационный институт | 21 | 9+6 | Engineering and Environmental Studies; Laser Design and Applications; Industrial Engineering and Technologies; Material Properties and Applications |
| `A5075134804` | Марина А. Токарева | Уральский федеральный университет | 24 | 16+8 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Synthesis and biological activity; Catalytic C–H Functionalization Methods |
| `A5075392699` | Jingrui Zhang | Московский государственный университет | 25 | 13+10 | Optimal Power Flow Distribution; Electric Power System Optimization; Smart Grid Energy Management; Microgrid Control and Optimization |
| `A5075453637` | A. V. Kuznetsov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 14+10 | Nanofluid Flow and Heat Transfer; Heat and Mass Transfer in Porous Media; Lattice Boltzmann Simulation Studies; Fluid Dynamics and Turbulent Flows |
| `A5075601412` | Natalia Shmatko | Высшая школа экономики | 25 | 18+7 | Educational Innovations and Challenges; scientometrics and bibliometrics research; Higher Education Governance and Development; Doctoral Education Challenges and Solutions |
| `A5076887424` | А. V. Postnikov | Московский физико-технический институт | 25 | 15+10 | Geological and Geochemical Analysis; High-pressure geophysics and materials; Geological Studies and Exploration; Advanced MEMS and NEMS Technologies |
| `A5078008105` | Saira Saira | Уральский федеральный университет | 25 | 11+7 | Technology-Enhanced Education Studies; Nanoparticles: synthesis and applications; Online and Blended Learning; Online Learning and Analytics |
| `A5078430016` | Е. Г. Жижина | Высшая школа экономики | 25 | 15+9 | Polyoxometalates: Synthesis and Applications; Chemical Synthesis and Reactions; Oxidative Organic Chemistry Reactions; Advanced Mathematical Modeling in Engineering |
| `A5078748436` | С. В. Цветков | Новосибирский государственный университет | 25 | 12+10 | Advanced Fiber Optic Sensors; Photonic and Optical Devices; Photonic Crystal and Fiber Optics; Advanced Fiber Laser Technologies |
| `A5078974032` | Alexandra Georgieva | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 21 | 15+6 | Advanced Optical Imaging Technologies; Adaptive optics and wavefront sensing; Optical measurement and interference techniques; Immune Cell Function and Interaction |
| `A5079460480` | S. M. Vlasov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 13+10 | Advanced Power Generation Technologies; Quantum and electron transport phenomena; Magnetic properties of thin films; Physics of Superconductivity and Magnetism |
| `A5079485396` | M. A. Kondratenko | Московский физико-технический институт | 25 | 18+7 | Particle Accelerators and Free-Electron Lasers; Superconducting Materials and Applications; Particle accelerators and beam dynamics; Particle physics theoretical and experimental studies |
| `A5079745958` | V. Yu. Shishkin | Московский государственный университет | 25 | 15+8 | Molten salt chemistry and electrochemical processes; Extraction and Separation Processes; Metallurgical Processes and Thermodynamics; Astrophysics and Cosmic Phenomena |
| `A5080281532` | Priyanka Yadav | Высшая школа экономики | 25 | 10+9 | Thermochemical Biomass Conversion Processes; Fungal Biology and Applications; Pesticide and Herbicide Environmental Studies; Lignin and Wood Chemistry |
| `A5080910752` | О А Симонова | Высшая школа экономики | 25 | 16+9 | EEG and Brain-Computer Interfaces; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5081002862` | Vladislav L. Zhdanov | Высшая школа экономики | 22 | 12+9 | Economic and Technological Developments in Russia; Graphene research and applications; Space exploration and regulation; Advanced materials and composites |
| `A5081393289` | Susan Jyakhwo | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 11 | 4+3 | Phytochemicals and Antioxidant Activities; Nanoparticles: synthesis and applications; Nanoparticle-Based Drug Delivery; SARS-CoV-2 and COVID-19 Research |
| `A5081771083` | А. В. Гаврилов | Московский государственный университет | 25 | 9+7 | Solid State Laser Technologies; Photorefractive and Nonlinear Optics; Laser Design and Applications; Methane Hydrates and Related Phenomena |
| `A5081919482` | A. N. Semenov | Новосибирский государственный университет | 25 | 12+7 | Computational Fluid Dynamics and Aerodynamics; Fluid Dynamics and Turbulent Flows; Block Copolymer Self-Assembly; Geological and Geochemical Analysis |
| `A5082380865` | К. В. Пугачев | Новосибирский государственный университет | 25 | 11+11 | Particle physics theoretical and experimental studies; Mosquito-borne diseases and control; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research |
| `A5082582724` | A. V. Golubkov | Высшая школа экономики | 25 | 13+11 | Rare-earth and actinide compounds; Solid-state spectroscopy and crystallography; Material Science and Thermodynamics; Magnetic Properties of Alloys |
| `A5083082784` | Georgi Asatryan | Высшая школа экономики | 25 | 16+7 | Luminescence Properties of Advanced Materials; Politics and Conflicts in Afghanistan, Pakistan, and Middle East; Solid-state spectroscopy and crystallography; Quantum optics and atomic interactions |
| `A5083659213` | Konstantin Yur'evich Osipenko | Московский государственный университет | 25 | 17+8 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Differential Equations and Boundary Problems |
| `A5084030961` | Ilya Kolyadenko | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 15 | 9+5 | Enzyme-mediated dye degradation; Metal-Catalyzed Oxygenation Mechanisms; Photosynthetic Processes and Mechanisms; Psoriasis: Treatment and Pathogenesis |
| `A5084049631` | V. A. Sal’nikov | Высшая школа экономики | 25 | 15+9 | Economic and Technological Developments in Russia; Global trade and economics; Catalysis and Hydrodesulfurization Studies; Legal and Regulatory Analysis |
| `A5084153434` | Ekaterina Antonova | Московский государственный технический университет имени Н. Э. Баумана | 25 | 15+9 | Radiomics and Machine Learning in Medical Imaging; Minerals Flotation and Separation Techniques; Gene expression and cancer classification; Industrial Engineering and Technologies |
| `A5084455963` | В. Н. Самойлов | Московский государственный университет | 25 | 15+9 | Ion-surface interactions and analysis; Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; Force Microscopy Techniques and Applications |
| `A5084535122` | A. Y. Sergeev | Новосибирский государственный университет | 25 | 17+7 | Nail Diseases and Treatments; Plant Pathogens and Fungal Diseases; Migraine and Headache Studies; Fungal Infections and Studies |
| `A5084621179` | Victoria K. Besprozvannykh | Высшая школа экономики | 15 | 7+7 | Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Bone Tissue Engineering Materials; biodegradable polymer synthesis and properties |
| `A5084795942` | Maria A. Khvatova | Московский государственный технический университет имени Н. Э. Баумана | 15 | 9+5 | Arctic and Russian Policy Studies; Economic and Technological Developments in Russia; Legal and Regulatory Analysis; Engineering and Environmental Studies |
| `A5084963768` | Владислав Сергеевич Медведев | Высшая школа экономики | 24 | 17+7 | Mathematical Dynamics and Fractals; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies |
| `A5085161196` | N. A. Toropov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 17+7 | Gold and Silver Nanoparticles Synthesis and Applications; Plasmonic and Surface Plasmon Research; Photonic and Optical Devices; Glass properties and applications |
| `A5085224984` | Andrei Mikhailovich Dregulo | Высшая школа экономики | 25 | 13+9 | Municipal Solid Waste Management; Industrial Engineering and Technologies; Mining and Gasification Technologies; Engineering and Environmental Studies |
| `A5086058139` | Vladimir Vanovskiy | Московский физико-технический институт | 25 | 13+10 | Arctic and Antarctic ice dynamics; Reservoir Engineering and Simulation Methods; Meteorological Phenomena and Simulations; Hydraulic Fracturing and Reservoir Analysis |
| `A5086073143` | S. V. Semendyaev | Московский физико-технический институт | 17 | 10+7 | Luminescence Properties of Advanced Materials; Robotic Locomotion and Control; Dynamics and Control of Mechanical Systems; Radiation Detection and Scintillator Technologies |
| `A5086493587` | Leonid N. Yasnitsky | Высшая школа экономики | 25 | 17+7 | Economic and Technological Systems Analysis; Economic and Technological Developments in Russia; Diverse Industrial Engineering Technologies; Healthcare Systems and Public Health |
| `A5086803366` | О. В. Морозов | Московский физико-технический институт | 25 | 10+9 | Solar and Space Plasma Dynamics; Ionosphere and magnetosphere dynamics; Plasma Diagnostics and Applications; Astro and Planetary Science |
| `A5086944778` | Irina Petrovskaya | Московский государственный университет | 11 | 5+3 | Entrepreneurship Studies and Influences; Innovation and Knowledge Management; Job Satisfaction and Organizational Behavior; Corporate Social Responsibility Reporting |
| `A5086988405` | E. V. Shevchenko | Санкт-Петербургский государственный университет | 25 | 16+7 | Topological Materials and Phenomena; Advanced Condensed Matter Physics; Solid-state spectroscopy and crystallography; Physics of Superconductivity and Magnetism |
| `A5087087375` | Victor B. Rybakov | Московский государственный университет | 25 | 17+7 | X-ray Diffraction in Crystallography; Crystallization and Solubility Studies; Synthesis and Reactivity of Heterocycles; Crystal structures of chemical compounds |
| `A5087116457` | Mary Ann Wagner | Национальный исследовательский ядерный университет МИФИ | 25 | 13+10 | Simulation Techniques and Applications; Brucella: diagnosis, epidemiology, treatment; Amino Acid Enzymes and Metabolism; Bacteriophages and microbial interactions |
| `A5087350537` | Ruslan Lukin | Автономная некоммерческая организация высшего образования Университет Иннополис | 12 | 9+3 | Machine Learning in Materials Science; Computational Drug Discovery Methods; Catalytic Cross-Coupling Reactions; Organoboron and organosilicon chemistry |
| `A5087415130` | M. I. Guseva | Высшая школа экономики | 25 | 13+7 | Fusion materials and technologies; Ion-surface interactions and analysis; Nuclear Materials and Properties; Metal and Thin Film Mechanics |
| `A5087615399` | S. Pozdniakov | Московский государственный университет | 25 | 13+10 | Quantum Chromodynamics and Particle Interactions; Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Groundwater flow and contamination studies |
| `A5087796113` | В. В. Фомичев | Московский государственный университет | 25 | 12+10 | Solar and Space Plasma Dynamics; Ionosphere and magnetosphere dynamics; Geomagnetism and Paleomagnetism Studies; Earthquake Detection and Analysis |
| `A5087982577` | А. И. Рубинштейн | Московский государственный университет | 25 | 13+7 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Mathematical functions and polynomials |
| `A5088992641` | N. N. Osipov | Санкт-Петербургский государственный университет | 25 | 10+10 | Advanced Harmonic Analysis Research; Nonlinear Partial Differential Equations; Tuberculosis Research and Epidemiology; Advanced Mathematical Modeling in Engineering |
| `A5090278484` | Yu. V. Zuev | Московский авиационный институт | 25 | 14+7 | Particle Dynamics in Fluid Flows; Particle Accelerators and Free-Electron Lasers; Particle accelerators and beam dynamics; Fluid Dynamics and Heat Transfer |
| `A5100361432` | А. В. Смирнов | Московский государственный университет | 26 | 12+10 | Plasma Diagnostics and Applications; Enzyme function and inhibition; Protist diversity and phylogeny; Material Properties and Applications |
| `A5100613162` | Wenjuan Wang | Санкт-Петербургский государственный университет | 25 | 15+8 | Advanced Sensor and Control Systems; Mercury impact and mitigation studies; Climate change and permafrost; Heavy metals in environment |
| `A5100673989` | Eun-Kyoung Kim | Высшая школа экономики | 20 | 13+5 | Global Maternal and Child Health; Global Health Care Issues; Healthcare Systems and Reforms; Insect symbiosis and bacterial influences |
| `A5101462418` | Hongzhi Yu | Уральский федеральный университет | 25 | 12+11 | Astrophysics and Star Formation Studies; Atmospheric Ozone and Climate; Stellar, planetary, and galactic studies; Astro and Planetary Science |
| `A5101518929` | Jing Tang | Московский государственный университет | 25 | 14+7 | Corneal surgery and disorders; Ophthalmology and Visual Impairment Studies; Metabolomics and Mass Spectrometry Studies; Ocular Surface and Contact Lens |
| `A5101596267` | В. А. Соколов | Национальный исследовательский технологический университет МИСиС | 25 | 9+7 | Material Properties and Applications; Forest Management and Policy; Trauma and Emergency Care Studies; Healthcare Systems and Public Health |
| `A5101647000` | Alexander Semenov | Московский авиационный институт | 24 | 16+6 | Petri Nets in System Modeling; Service-Oriented Architecture and Web Services; Business Process Modeling and Analysis; Distributed and Parallel Computing Systems |
| `A5101654868` | V. A. Ivanov | Национальный исследовательский ядерный университет МИФИ | 25 | 15+7 | Astro and Planetary Science; Stellar, planetary, and galactic studies; Gut microbiota and health; Clostridium difficile and Clostridium perfringens research |
| `A5101822993` | Alexander A. Kharlamov | Московский физико-технический институт | 24 | 15+9 | Quality and Supply Management; Supply Chain Resilience and Risk Management; Big Data and Business Intelligence; Customer Service Quality and Loyalty |
| `A5101867217` | А. М. Savchenko | Высшая школа экономики | 25 | 14+9 | Nuclear Materials and Properties; Nuclear reactor physics and engineering; Physics of Superconductivity and Magnetism; Statistical Mechanics and Entropy |
| `A5101884698` | В. В. Иванов | Московский физико-технический институт | 25 | 14+8 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Geological Studies and Exploration |
| `A5101926125` | A. L. Smirnov | Санкт-Петербургский государственный университет | 25 | 16+9 | Algebraic Geometry and Number Theory; Diamond and Carbon-based Materials Research; Homotopy and Cohomology in Algebraic Topology; Ferroelectric and Piezoelectric Materials |
| `A5101946472` | С. В. Зайцев | Московский государственный университет | 25 | 16+8 | Pancreatic function and diabetes; Semiconductor Quantum Structures and Devices; Blood Coagulation and Thrombosis Mechanisms; Electron and X-Ray Spectroscopy Techniques |
| `A5101982860` | Nikolay A. Ivanov | Новосибирский государственный университет | 25 | 11+9 | Epigenetics and DNA Methylation; Neuroendocrine Tumor Research Advances; Lung Cancer Research Studies; Genomics and Chromatin Dynamics |
| `A5102003871` | Manoj Kumar | Уральский федеральный университет | 25 | 15+9 | Advanced machining processes and optimization; Advanced Machining and Optimization Techniques; Advanced Surface Polishing Techniques; Sustainable Supply Chain Management |
| `A5102014526` | Alexander Vasilyev | Национальный исследовательский ядерный университет МИФИ | 25 | 15+7 | Differential Equations and Boundary Problems; Differential Equations and Numerical Methods; advanced mathematical theories; Spectral Theory in Mathematical Physics |
| `A5102755946` | Surajit Das | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 14+8 | Structural Health Monitoring Techniques; Ultrasonics and Acoustic Wave Propagation; Structural Load-Bearing Analysis; Artificial Intelligence in Healthcare |
| `A5102936853` | O. V. Denisov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 15+8 | Advanced Data Processing Techniques; Material Properties and Applications; Spacecraft Design and Technology; Heat Transfer and Mathematical Modeling |
| `A5102954169` | Yunfei Han | Новосибирский государственный университет | 19 | 10+7 | Plant Molecular Biology Research; Advanced Neural Network Applications; Genetic Mapping and Diversity in Plants and Animals; Video Surveillance and Tracking Methods |
| `A5102959279` | S. A. LEBEDEV | Московский государственный технический университет имени Н. Э. Баумана | 25 | 13+8 | Inorganic and Organometallic Chemistry; Educational Innovations and Challenges; Scientific Research and Philosophical Inquiry; Catalytic Cross-Coupling Reactions |
| `A5103022770` | A. A. MAKSIMENKO | Высшая школа экономики | 25 | 14+9 | Organoselenium and organotellurium chemistry; Organic Chemistry Cycloaddition Reactions; Chemical Thermodynamics and Molecular Structure; Sociopolitical Dynamics in Russia |
| `A5103328861` | Alexander Afanasiev | Национальный исследовательский технологический университет МИСиС | 25 | 10+7 | Efficiency Analysis Using DEA; Distributed and Parallel Computing Systems; Cloud Computing and Resource Management; Scientific Computing and Data Management |
| `A5103393483` | A. Yu. Baranov | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 16+7 | Spacecraft and Cryogenic Technologies; Thermoregulation and physiological responses; Arctic and Russian Policy Studies; Infrared Thermography in Medicine |
| `A5103438122` | А. А. Васин | Московский физико-технический институт | 25 | 14+8 | Economic theories and models; Smart Grid Energy Management; Auction Theory and Applications; Electric Power System Optimization |
| `A5103560925` | Alexey Kotov | Высшая школа экономики | 21 | 14+7 | Child and Animal Learning Development; Obesity, Physical Activity, Diet; Categorization, perception, and language; Global Public Health Policies and Epidemiology |
| `A5103890935` | Наталья Николаевна Скворцова | Новосибирский государственный университет | 19 | 10+6 | Linguistic, Cultural, and Literary Studies; Legal and Regulatory Analysis; Military Technology and Strategies; Multiple Myeloma Research and Treatments |
| `A5104780466` | Григорий Евгеньевич Иванов | Московский физико-технический институт | 17 | 10+7 | Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies; Military Technology and Strategies; Optimization and Variational Analysis |
| `A5107839879` | Д. Деркач | Высшая школа экономики | 25 | 15+10 | Particle physics theoretical and experimental studies; Quantum Chromodynamics and Particle Interactions; High-Energy Particle Collisions Research; Neutrino Physics Research |
| `A5107980327` | А. Антонов | Московский государственный университет | 25 | 14+11 | Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions; Particle Detector Development and Performance |
| `A5108120314` | A. A. Lebedev | Национальный исследовательский ядерный университет МИФИ | 25 | 13+9 | Silicon Carbide Semiconductor Technologies; Particle physics theoretical and experimental studies; High-Energy Particle Collisions Research; Quantum Chromodynamics and Particle Interactions |
| `A5108684386` | N. V. Kudrevatykh | Уральский федеральный университет | 25 | 13+11 | Chemical synthesis and pharmacological studies; Magnetic Properties of Alloys; Magnetic and transport properties of perovskites and related materials; Rare-earth and actinide compounds |
| `A5108762142` | С. В. Курочкин | Высшая школа экономики | 25 | 7+7 | Stochastic processes and financial applications; Probability and Risk Models; Differential Equations and Numerical Methods; Insurance, Mortality, Demography, Risk Management |
| `A5108860838` | Anna Mylnikova | Высшая школа экономики | 18 | 12+6 | Ionosphere and magnetosphere dynamics; Earthquake Detection and Analysis; GNSS positioning and interference; Natural Language Processing Techniques |
| `A5109391752` | M. N. Zakharov | Московский государственный технический университет имени Н. Э. Баумана | 25 | 18+7 | Engineering Technology and Methodologies; Material Properties and Applications; Gear and Bearing Dynamics Analysis; Industrial Engineering and Technologies |
| `A5109801013` | Vira Koshkina | Московский физико-технический институт | 15 | 4+4 | Climate variability and models; Meteorological Phenomena and Simulations; Cancer Risks and Factors; Human Health and Disease |
| `A5109838845` | Mahmoud Naderi | Автономная некоммерческая организация высшего образования Университет Иннополис | 17 | 8+6 | Innovative concrete reinforcement materials; Concrete and Cement Materials Research; Structural Behavior of Reinforced Concrete; Quantum Computing Algorithms and Architecture |
| `A5109913769` | M. Zhao | Новосибирский государственный университет | 12 | 7+3 | Animal Behavior and Reproduction; Immune Response and Inflammation; Tuberculosis Research and Epidemiology; Amphibian and Reptile Biology |
| `A5109976652` | Svetlana I. Kuzmina | Московский государственный технический университет имени Н. Э. Баумана | 25 | 16+7 | Climate change and permafrost; Arctic and Antarctic ice dynamics; Climate variability and models; Computational Fluid Dynamics and Aerodynamics |
| `A5110440207` | Alexander Ostroushko | Уральский федеральный университет | 20 | 12+6 | Polyoxometalates: Synthesis and Applications; Nanocluster Synthesis and Applications; Legal and Regulatory Analysis; Linguistic, Cultural, and Literary Studies |
| `A5111243299` | T. Hein | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 17 | 10+6 | Ionosphere and magnetosphere dynamics; Magnetic confinement fusion research; Plant tissue culture and regeneration; Laser-Plasma Interactions and Diagnostics |
| `A5111333002` | Maria Obraztsova | Автономная некоммерческая организация высшего образования Университет Иннополис | 12 | 6+3 | Venous Thromboembolism Diagnosis and Management; Acute Myocardial Infarction Research; Pulmonary Hypertension Research and Treatments; Educational Innovations and Challenges |
| `A5111524384` | V. A. Zubov | Санкт-Петербургский государственный университет | 25 | 12+12 | Optical and Acousto-Optic Technologies; Optical Polarization and Ellipsometry; Spectroscopy Techniques in Biomedical and Chemical Research; Atmospheric Ozone and Climate |
| `A5111604731` | Alexander Kotov | Уральский федеральный университет | 25 | 17+7 | Semiconductor materials and devices; Advancements in Semiconductor Devices and Circuit Design; Advanced Memory and Neural Computing; Software Engineering Research |
| `A5112194709` | В. В. Станкевич | Национальный исследовательский технологический университет МИСиС | 25 | 11+7 | Laser-Matter Interactions and Applications; Nonlinear Optical Materials Studies; Advanced Fiber Laser Technologies; Synthesis and Characterization of Pyrroles |
| `A5112318731` | Guofeng Sun | Уральский федеральный университет | 25 | 12+8 | Structural Load-Bearing Analysis; Chemical Synthesis and Reactions; Organoboron and organosilicon chemistry; Crystallization and Solubility Studies |
| `A5113833663` | А. В. Лобода | Московский государственный университет | 25 | 14+11 | Holomorphic and Operator Theory; Algebraic and Geometric Analysis; Analytic and geometric function theory; Geometric Analysis and Curvature Flows |
| `A5113863334` | E. A. Savchenkova | Национальный исследовательский ядерный университет МИФИ | 17 | 9+8 | Mesenchymal stem cell research; Photonic and Optical Devices; Virus-based gene therapy research; Digital Holography and Microscopy |
| `A5113889637` | Marina A. Medvedeva | Уральский федеральный университет | 25 | 11+10 | Numerical methods for differential equations; Matrix Theory and Algorithms; Economic and Technological Systems Analysis; Scientific Innovation and Industrial Efficiency |
| `A5113915823` | Jiacheng Lou | Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики | 25 | 11+9 | Heat Transfer and Boiling Studies; Heat transfer and supercritical fluids; Glioma Diagnosis and Treatment; Cancer-related molecular mechanisms research |
