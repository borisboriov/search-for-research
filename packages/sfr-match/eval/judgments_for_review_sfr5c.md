# Судейские оценки SFR-5c — выборка для ручной проверки

> **Важно (правка 26.09 после ревью).** Пометки ⚠ в этом файле — по пересуду
> **v1**, который шёл по рубрике с посторонним правилом «сомневаешься между 1 и 2
> — ставь 1». Итоговая разметка итерации — **v2** (та же рубрика, но без этого
> правила): там расхождений с накопленной разметкой 40, а не 51, и часть пар
> разошлась в другую сторону. Сводка по классам — `docs/sfr5c_rejudge_classes.json`
> и §6 `docs/SFR5c_REPORT.md`; построчно v2 —
> `packages/sfr-match/eval/judgments_rejudge_sfr5c_v2.jsonl`. Перегенерация этого
> файла с колонками «было → v1 → v2» — #114.

Два раздела. **Первый — «Решающие пары»** (обязательный, §6.3 спеки): пары, из-за которых метрики трёх каталогов расходятся, с оценками накопленной разметки и пересуда (v1) — смотреть их первыми, начиная с помеченных ⚠. **Второй — случайная выборка** из новой партии оценок этой итерации.

Порог из спеки: **≥4 расхождений из 20** в случайной выборке → партию надо пересуживать. В решающих парах расхождение двух судей — не повод пересуживать, а повод решить, какое чтение рубрики верное: вердикт человека здесь и есть истина.

---

## Часть 1. Решающие пары трёх точек

Запросов, у которых Success@1, Success@5 или топ-1 разошлись хотя бы между двумя из трёх каталогов: **16**. Для каждого — топ-5 всех трёх точек с оценками и названиями работ. Оценка ставится **по работам**, а не по темам OpenAlex (#107).

Колонки точек: **5 538** · **потолок 9 010** · **12 119**.

Оценки печатаются как **было → пересуд v1** (135 пар пересужены отдельным прогоном судьи по той же рубрике; расхождений 51). Судья не независим от разметки конструктивно — слеп пул, а не он (§6 отчёта). Расходящиеся помечены ⚠ — смотреть их первыми.

## `q01` — Хочу заниматься машинным обучением для анализа текстов, интересна тема депрессии в соцсетях. Есть кто-то, кто этим занимается?

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.583 | `A5070267730` (2 = 2), `A5007086495` (1 = 1), `A5031192722` (1 = 1), `A5038667261` (0 = 0), `A5052465844` (1 = 1) |
| потолок 9 010 | 1 | 1 | 0.603 | `A5012212950` (2 = 2), `A5070267730` (2 = 2), `A5100352794` (1 → 2 ⚠), `A5029380392` (2 = 2), `A5022906506` (1 = 1) |
| 12 119 | 1 | 1 | 0.603 | `A5012212950` (2 = 2), `A5070267730` (2 = 2), `A5100352794` (1 → 2 ⚠), `A5089112259` (1 = 1), `A5029380392` (2 = 2) |

- `A5070267730` **Ivan Smirnov** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Dynamics of the meningeal CD4+ T-cell repertoire are defined by the cervical lymph nodes and facilitate cognitive task performance in mice» (2013); «Feature Engineering for Depression Detection in Social Media» (2018); «Predicting Depression with Text, Image, and Profile Data from Social Media» (2022); «Semantic Role Labeling with Pretrained Language Models for Known and Unknown Predicates» (2019); «Depression Detection from Social Media Profiles» (2020); «RLBenchNet: The Right Network for the Right Reinforcement Learning Task» (2025); «Анализ информационной безопасности на техническую спецификацию Network 2030 Architecture Framework для 6G сетей» (2025)
- `A5007086495` **Robiul Islam** — Автономная некоммерческая организация высшего образования Университет Иннополис; оценка **1 = 1**
  - работы: «Detecting Depression Using K-Nearest Neighbors (KNN) Classification Technique» (2018); «Explainable Machine Learning Methods for Classification of Brain States during Visual Perception» (2022); «On-air English Capital Alphabet (ECA) recognition using depth information» (2021); «Optimum Blade Design of Pinwheel Type Horizontal Axis Wind Turbine for Low Wind Speed Areas» (2021); «Alphabet Recognition in Air Writing Using Depth Information» (2016)
- `A5031192722` **Denis Dresvyanskiy** — Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики; оценка **1 = 1**
  - работы: «In search of a robust facial expressions recognition model: A large-scale visual cross-corpus study» (2022); «Predicting Depression and Emotions in the Cross-roads of Cultures, Para-linguistics, and Non-linguistics» (2019); «End-to-End Modeling and Transfer Learning for Audiovisual Emotion Recognition in-the-Wild» (2022); «Ensembling End-to-End Deep Models for Computational Paralinguistics Tasks: ComParE 2020 Mask and Breathing Sub-Challenges» (2020)
- `A5038667261` **Татьяна Караваева** — Санкт-Петербургский государственный университет; оценка **0 = 0**
  - работы: «Psychological mechanisms and psychosomatic relationships in various dermatoses» (2018); «Basic approaches to the diagnosis and therapy of post-traumatic stress disorder» (2022); «Psychotherapy: Textbook» (2022); «The social-demographic characteristics and pandemic COVID-19 individual experience and their impact on vaccination attitude study aimed to determine the psychosocial interventions targets» (2021); «Socio-psychological risk factors for the development of posttraumatic stress disorder in patients with rectum cancer, who undergone colostomia» (2018)
- `A5052465844` **Elena Ryumina** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Audio-Visual Speech and Gesture Recognition by Sensors of Mobile Devices» (2023); «In search of a robust facial expressions recognition model: A large-scale visual cross-corpus study» (2022); «Audio–visual speech recognition based on regulated transformer and spatio–temporal fusion strategy for driver assistive systems» (2024); «End-to-End Modeling and Transfer Learning for Audiovisual Emotion Recognition in-the-Wild» (2022); «Multi-corpus emotion recognition method based on cross-modal gated attention fusion» (2025)
- `A5012212950` **Dheeraj Kodati** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Negative emotions detection on online mental-health related patients texts using the deep learning with MHA-BCNN model» (2021); «Identifying suicidal emotions on social media through transformer-based deep learning» (2022); «Negative emotion detection on social media during the peak time of COVID-19 through deep learning with an auto-regressive transformer» (2023); «Advancing mental health detection in texts via multi-task learning with soft-parameter sharing transformers» (2024); «Emotion mining for early suicidal threat detection on both social media and suicide notes using context dynamic masking-based transformer with deep learning» (2024); «POLAR: A Benchmark for Multilingual, Multicultural, and Multi-Event Online Polarization» (2026)
- `A5100352794` **Xinyu Wang** — Московский государственный университет; оценка **1 → 2 ⚠**
  - работы: «A Depression Detection Model Based on Sentiment Analysis in Micro-blog Social Network» (2013); «Interpretable feature-temporal transformer for short-term wind power forecasting with multivariate time series» (2024); «A random forest classifier based on pixel comparison features for urban LiDAR data» (2018); «Building a Bridge: A Method for Image-Text Sarcasm Detection Without Pretraining on Image-Text Data» (2020); «An Improved Model for Depression Detection in Micro-Blog Social Network» (2013)
- `A5029380392` **Dmitry Devyatkin** — Санкт-Петербургский государственный университет; оценка **2 = 2**
  - работы: «Feature Engineering for Depression Detection in Social Media» (2018); «Exploring linguistic features for extremist texts detection (on the material of Russian-speaking illegal texts)» (2017); «Random Kernel Forests» (2022); «Technologies for Complex Intelligent Clinical Data Analysis» (2016)
- `A5022906506` **Oxana Mikhaylova** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Depression representations on the most popular Russian-language YouTube channels» (2023); «Radical Self-Representation in a Hostile Setting: Discursive Strategies of the Russian Lesbian Feminist Movement» (2021); «Self-representations of the experience of anorexia on YouTube: The joint influence of the explanatory model and the web platform» (2022)
- `A5089112259` **German Klimenko** — Московский государственный университет; оценка **1 = 1**
  - работы: «Identifying Reproductive Behavior Arguments in Social Media Content Users’ Opinions through Natural Language Processing Techniques» (2023); «Advancing Semantic Classification: A Comprehensive Examination of Machine Learning Techniques in Analyzing Russian-Language Patient Reviews» (2024); «The Measurement of Demographic Temperature Using the Sentiment Analysis of Data from the Social Network VKontakte» (2021)

## `q03` — Интересна физика элементарных частиц, хочу поучаствовать в экспериментах на коллайдере

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.434 | `A5100670875` (2 → 1 ⚠), `A5039966405` (2 → 1 ⚠), `A5114377115` (2 → 1 ⚠), `A5107963115` (2 → 1 ⚠), `A5102786081` (2 → 1 ⚠) |
| потолок 9 010 | 1 | 1 | 0.443 | `A5067830021` (2 = 2), `A5100670875` (2 → 1 ⚠), `A5039966405` (2 → 1 ⚠), `A5002724483` (2 = 2), `A5114377115` (2 → 1 ⚠) |
| 12 119 | 1 | 1 | 0.443 | `A5067830021` (2 = 2), `A5100670875` (2 → 1 ⚠), `A5039966405` (2 → 1 ⚠), `A5002724483` (2 = 2), `A5114377115` (2 → 1 ⚠) |

- `A5100670875` **A. Belyaev** — Московский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Observation of a new boson at a mass of 125 GeV with the CMS experiment at the LHC» (2012); «CalcHEP 3.4 for collider physics within and beyond the Standard Model» (2013); «Two asymptotic corrections for the p-Poisson distance» (2026); «Minimal Scale-Invariant Dark Matter» (2026); «Addendum: Search for resonant and nonresonant production of pairs of dijet resonances in proton-proton collisions at $$ \sqrt{s}=13 $$ TeV» (2026); «Gravitational waves from dark gauge sectors» (2026)
- `A5039966405` **A. Bolozdynya** — Национальный исследовательский ядерный университет МИФИ; оценка **2 → 1 ⚠**
  - работы: «First Results from the LUX Dark Matter Experiment at the Sanford Underground Research Facility» (2014); «Observation of coherent elastic neutrino-nucleus scattering» (2017); «First Results from the XENON10 Dark Matter Experiment at the Gran Sasso National Laboratory» (2008); «Search for Light Dark Matter in XENON10 Data» (2011); «The Large Underground Xenon (LUX) experiment» (2012)
- `A5114377115` **K. Beloborodov** — Новосибирский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Search for high-mass dilepton resonances using 139 fb−1 of pp collision data collected at s=13 TeV with the ATLAS detector» (2019); «Search for a resonance decaying into a scalar particle and a Higgs boson in the final state with two bottom quarks and two photons with 199 fb−1 of data collected at s=13 and 13.6 TeV with the ATLAS…» (2026); «Impact of QED backgrounds on light-by-light scattering measurements at $$e^+e^-$$ and $$e^-e^-$$ colliders» (2026)
- `A5107963115` **А. Виноградов** — Санкт-Петербургский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Ion-Beam Modulation of Nitrogen Defect Sites in Carbon Nanotubes for Controlled ORR Selectivity in Alkaline Media» (2026); «Time resolution of the ALICE time-of-flight detector with the first Run 3 pp collisions at $$\mathbf{\sqrt{\textit{s}} = 13.6}$$ TeV» (2026); «Formation of dense partonic matter in relativistic nucleus–nucleus collisions at RHIC: Experimental evaluation by the PHENIX Collaboration» (2005); «The ALICE experiment at the CERN LHC» (2008)
- `A5102786081` **P. Teterin** — Национальный исследовательский ядерный университет МИФИ; оценка **2 → 1 ⚠**
  - работы: «A facility to Search for Hidden Particles (SHiP) at the CERN SPS» (2015); «The ATLAS experiment at the CERN Large Hadron Collider: a description of the detector configuration for Run 3» (2024); «Reactive pulsed laser deposition of Cu2ZnSnS4 thin films in H2S» (2012); «Effect of annealing on structural and optical properties of Cu2ZnSnS4 thin films grown by pulsed laser deposition» (2015); «Technical Design Report of the Spin Physics Detector at NICA» (2024)
- `A5067830021` **Vladimir Bocharnikov** — Высшая школа экономики; оценка **2 = 2**
  - работы: «International Large Detector: Interim Design Report» (2020); «The BM@N spectrometer at the NICA accelerator complex» (2024); «Analysis of testbeam data of the highly granular RPC-steel CALICE digital hadron calorimeter and validation of Geant4 Monte Carlo models» (2019); «Data-Efficient Unsupervised Recalibration of Calorimeter Sensor Arrays Using Wasserstein Adversarial Learning» (2026); «Production of Λ hyperons in 4.0A GeV and 4.5A GeV carbon-nucleus interactions at the Nuclotron» (2026)
- `A5002724483` **I. K. Surin** — Новосибирский государственный университет; оценка **2 = 2**
  - работы: «Study of the process e+e−→nn¯ at the VEPP-2000 e+e− collider with the SND detector» (2014); «Measurement of the e+e−→ηπ+π− cross section in the center-of-mass energy range 1.22–2.00 GeV with the SND detector at the VEPP-2000 collider» (2015); «Study of the process e+e−→ηγ in the center-of-mass energy range 1.07–2.00 GeV» (2014)

## `q04` — Хочу в тему сверхпроводимости, но боюсь, что это слишком сложно для меня

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.512 | `A5026267619` (2 → 1 ⚠), `A5044414277` (1 = 1), `A5038973865` (2 → 1 ⚠), `A5087372080` (2 = 2), `A5105975394` (2 = 2) |
| потолок 9 010 | 1 | 1 | 0.517 | `A5041062340` (2 → 1 ⚠), `A5019927506` (2 = 2), `A5064599758` (2 = 2), `A5026267619` (2 → 1 ⚠), `A5029059211` (1 → 0 ⚠) |
| 12 119 | 1 | 1 | 0.517 | `A5041062340` (2 → 1 ⚠), `A5019927506` (2 = 2), `A5064599758` (2 = 2), `A5026267619` (2 → 1 ⚠), `A5087284937` (2 = 2) |

- `A5026267619` **О. С. Волкова** — Московский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Milestones of low-D quantum magnetism» (2018); «Frustrated Cuprate Route from Antiferromagnetic to Ferromagnetic Spin- 1 2 Heisenberg Chains: Li 2 ZrCuO 4 as a Missing Link near the Quantum Critical Point» (2007); «Single crystal growth and characterization of tetragonal FeSe1−x superconductors» (2013)
- `A5044414277` **Andrey Vlasenko** — Московский авиационный институт; оценка **1 = 1**
  - работы: «Simulation of chemical transport model estimates by means of a neural network using meteorological data» (2021); «Structure and properties of melt-textured YBa2Cu3O7 , high pressure–high temperature treated and oxygenated under evaluated oxygen pressure» (2004); «Nanostructural Superconducting Materials for Fault Current Limiters and Cryogenic Electrical Machines» (2010); «High-pressure synthesis of MgB2 with and without tantalum additions» (2002)
- `A5038973865` **A. Yu. Kuntsevich** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «Structural distortion behind the nematic superconductivity in Sr x Bi2Se3» (2018); «Strongly correlated two-dimensional plasma explored from entropy measurements» (2015); «Spin-Droplet State of an Interacting 2D Electron System» (2012); «Electron-electron interaction correction and magnetoresistance in tilted fields in Si-based two-dimensional systems» (2013)
- `A5087372080` **E. F. Talantsev** — Уральский федеральный университет; оценка **2 = 2**
  - работы: «Universal self-field critical current for thin-film superconductors» (2015); «Magnetic flux trapping in hydrogen-rich high-temperature superconductors» (2023); «Thermodynamic Parameters of Single‐ or Multi‐Band Superconductors Derived from Self‐Field Critical Currents» (2017)
- `A5105975394` **A. A. Golubov** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Superconductivity in M g B 2 : Clean or Dirty?» (2002); «Josephson supercurrent through a topological insulator surface state» (2012); «Multiband model for tunneling in MgB2 junctions» (2002); «Theory of the Proximity Effect in Junctions with Unconventional Superconductors» (2007); «Effect of magnetic and nonmagnetic impurities on highly anisotropic superconductivity» (1997)
- `A5041062340` **Boris G. Lvov** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «Competitive 0 and π states in S/F/S trilayers: Multimode approach» (2019); «Automation of parameter extraction procedure for Si JFET SPICE model in the −200…+110°C temperature range» (2018); «Radiation-Induced Fault Simulation of SOI/SOS CMOS LSI’s Using Universal Rad-SPICE MOSFET Model» (2017); «Exploring disorder correlations in superconducting systems: spectroscopic insights and matrix element effects» (2024)
- `A5019927506` **Alexander E. Lukyanov** — Национальный исследовательский ядерный университет МИФИ; оценка **2 = 2**
  - работы: «Correlated disorder as a way towards robust superconductivity» (2022); «Exploring disorder correlations in superconducting systems: spectroscopic insights and matrix element effects» (2024); «Nonlinear spectroscopy of excitonic states in transition metal dichalcogenides» (2022)
- `A5064599758` **Vyacheslav D. Neverov** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Correlated disorder as a way towards robust superconductivity» (2022); «Exploring disorder correlations in superconducting systems: spectroscopic insights and matrix element effects» (2024); «Nonlinear spectroscopy of excitonic states in transition metal dichalcogenides» (2022)
- `A5029059211` **А. G. Volkov** — Уральский федеральный университет; оценка **1 → 0 ⚠**
  - работы: «Semiconductor-metal transition in FeSi in ultrahigh magnetic fields up to 450 T» (1998); «Electronic structure and magnetic susceptibility of nearly magnetic metals (palladium and platinum)» (2010); «Semiconductor-metal transition in FeSi in an ultrahigh magnetic field» (1999); «Electronic structure and quantum spin fluctuations at the magnetic phase transition in MnSi» (2017); «Effects of pd-hybridization in strongly correlated insulator FeSi» (2016)
- `A5087284937` **Alexey Neilo** — Московский государственный университет; оценка **2 = 2**
  - работы: «Thouless energy in Josephson SN-N-NS bridges» (2024); «Spin-Valve-Controlled Triggering of Superconductivity» (2024); «Effective Exchange Energy in a Thin, Spatially Inhomogeneous CuNi Layer Proximized by Nb» (2022); «Magnetic Control of the Kinetic Inductance in Elements of Superconducting Electronics» (2025)

## `q07` — Интересен deep learning для физики частиц, хочу применять нейросети к данным с детекторов

*Разошлось:* s5. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 0 | 0 | 0.578 | `A5112651411` (1 = 1), `A5107839879` (1 = 1), `A5083103730` (1 → 2 ⚠), `A5107174121` (1 → 0 ⚠), `A5107902822` (1 = 1) |
| потолок 9 010 | 0 | 1 | 0.578 | `A5112651411` (1 = 1), `A5029181198` (2 → 1 ⚠), `A5027535433` (2 = 2), `A5107839879` (1 = 1), `A5083103730` (1 → 2 ⚠) |
| 12 119 | 0 | 1 | 0.578 | `A5112651411` (1 = 1), `A5029181198` (2 → 1 ⚠), `A5027535433` (2 = 2), `A5107839879` (1 = 1), `A5083103730` (1 → 2 ⚠) |

- `A5112651411` **Kenenbek Arzymatov** — Высшая школа экономики; оценка **1 = 1**
  - работы: «First observation of the decay $B_s^0 \to K^-\mu^+\nu_\mu$ and Measurement of $|V_{ub}|/|V_{cb}|$» (2021); «Online Neural Networks for Change-Point Detection» (2026); «NEURAL NETWORK APPROACH TO APPROXIMATION OF LOCAL COALESCENTE TIME» (2023); «Deep Learning for Inferring Distribution of Time to the Last Common Ancestor from a Diploid Genome» (2022)
- `A5107839879` **Д. Деркач** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Polarization Drift Compensation for Quantum Key Distribution Using Machine Learning» (2025); «Evolutionary Two-Stage Hyperparameter Optimization Strategies for Physics-Informed Neural Networks» (2026); «Correcting Sensor-Induced Distribution Drift with Wasserstein Adversarial Learning» (2026)
- `A5083103730` **M. Hushchyn** — Высшая школа экономики; оценка **1 → 2 ⚠**
  - работы: «Data-Efficient Unsupervised Recalibration of Calorimeter Sensor Arrays Using Wasserstein Adversarial Learning» (2026); «Correcting Sensor-Induced Distribution Drift with Wasserstein Adversarial Learning» (2026); «Artificial intelligence and digital twins for failure prediction in data center cooling systems: a comprehensive literature review (2018–2026)» (2026); «Observation of the Doubly Charmed Baryon Ξ c c + +» (2017)
- `A5107174121` **D. Sidorov** — Уральский федеральный университет; оценка **1 → 0 ⚠**
  - работы: «Measurement of the top quark mass in the tt¯→dilepton channel from s=8 TeV ATLAS data» (2016); «Design and Research of a 24 GHz Range Data Transmission System Based on the Use of Doppler Sensors» (2024); «Measurement of the Higgs boson mass from the H→γγ and H→ZZ*→4ℓ channels in pp collisions at center-of-mass energies of 7 and 8 TeV with the ATLAS detector» (2014)
- `A5107902822` **Yu. A. Tikhonov** — Новосибирский государственный университет; оценка **1 = 1**
  - работы: «Search for long-lived, weakly interacting particles that decay to displaced hadronic jets in proton-proton collisions at s=8 TeV with the ATLAS detector» (2015); «Experimental Investigation of High-Energy Photon Splitting in Atomic Fields» (2002); «The KEDR detector» (2013); «New precision measurement of the J/ψ- and ψ′-meson masses» (2003); «Two-phase argon and xenon avalanche detectors based on Gas Electron Multipliers» (2005)
- `A5029181198` **Denis Derkach** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «Toward Machine Learning Optimization of Experimental Design» (2021); «NFAD: fixing anomaly detection using normalizing flows» (2021); «Normalizing flows for deep anomaly detection» (2019); «Online Neural Networks for Change-Point Detection» (2026)
- `A5027535433` **F. Ratnikov** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Optimization of the Accelerator Control by Reinforcement Learning: A Simulation-Based Approach» (2025); «Neutron Reconstruction in the BM@N Experiment Using Machine Learning» (2024); «Measurement of the $Λ^0_b\rightarrow J/ψΛ$ angular distribution and the $Λ^0_b$ polarisation in $pp$ collisions» (2020)

## `q08` — Хочу заниматься NLP и graph neural networks, желательно на русскоязычных данных

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.509 | `A5001784131` (2 → 1 ⚠), `A5000934507` (1 → 0 ⚠), `A5018958751` (0 = 0), `A5058806392` (1 → 0 ⚠), `A5101711419` (0 = 0) |
| потолок 9 010 | 1 | 1 | 0.527 | `A5083490320` (2 → 1 ⚠), `A5001784131` (2 → 1 ⚠), `A5000934507` (1 → 0 ⚠), `A5002957144` (1 = 1), `A5002542089` (0 = 0) |
| 12 119 | 1 | 1 | 0.527 | `A5083490320` (2 → 1 ⚠), `A5001784131` (2 → 1 ⚠), `A5000934507` (1 → 0 ⚠), `A5002957144` (1 = 1), `A5002542089` (0 = 0) |

- `A5001784131` **Alena Fenogenova** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «mGPT: Few-Shot Learners Go Multilingual» (2022); «mGPT: Few-Shot Learners Go Multilingual» (2024); «Russian Paraphrasers: Paraphrase with Transformers» (2021); «MMTEB: Massive Multilingual Text Embedding Benchmark» (2025)
- `A5000934507` **Natalia Slioussar** — Высшая школа экономики; оценка **1 → 0 ⚠**
  - работы: «Expanding horizons of cross-linguistic research on reading: The Multilingual Eye-movement Corpus (MECO)» (2022); «Text reading in English as a second language: Evidence from the Multilingual Eye-Movements Corpus» (2022); «Processing of a Free Word Order Language: The Role of Syntax and Context» (2011); «Forms and features: The role of syncretism in number agreement attraction» (2018); «Gender Agreement Attraction in Russian: Production and Comprehension Evidence» (2016)
- `A5018958751` **Polina Lemenkova** — Санкт-Петербургский государственный университет; оценка **0 = 0**
  - работы: «Determination of ecological significance based on geostatistical assessment: a case study from the Slovak Natura 2000 protected area» (2013); «STATISTICAL ANALYSIS OF THE MARIANA TRENCH GEOMORPHOLOGY USING R PROGRAMMING LANGUAGE» (2019); «LAND PLANNING AS A SUPPORT FOR SUSTAINABLE DEVELOPMENT BASED ON TOURISM: A CASE STUDY OF SLOVAK RURAL REGION» (2017)
- `A5058806392` **Olga Dragoy** — Высшая школа экономики; оценка **1 → 0 ⚠**
  - работы: «Diffusion-tensor imaging of major white matter tracts and their role in language processing in aphasia» (2016); «Processing polarity: ERP evidence for differences between positive and negative polarity» (2012); «Russian normative data for 375 action pictures and verbs» (2014); «Verb production and word order in Russian agrammatic speakers» (2009); «Grey and white matter substrates of action naming» (2019); «RusLan-M: longitudinal multimedia corpus of early child speech in Russian» (2026); «Moscow Wada protocol: an optimised protocol for language and memory lateralization» (2026); «Contribution of attentional mechanisms to verbal and nonverbal communication in boys with ASD» (2026)
- `A5101711419` **Alexander Sergeev** — Высшая школа экономики; оценка **0 = 0**
  - работы: «Horovod: fast and easy distributed deep learning in TensorFlow» (2018); «Combining spatial autocorrelation with machine learning increases prediction accuracy of soil heavy metals» (2018); «The topology of fMRI-based networks defines the performance of a graph neural network for the classification of patients with major depressive disorder» (2023); «High variation topsoil pollution forecasting in the Russian Subarctic: Using artificial neural networks combined with residual kriging» (2017); «Serum Levels of Mitochondrial and Microbial Metabolites Reflect Mitochondrial Dysfunction in Different Stages of Sepsis» (2019); «Land Use Approach for High-Resolution Spatial Modeling of Industrial Emissions» (2026)
- `A5083490320` **Maria Tikhonova** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «A Family of Pretrained Transformer Language Models for Russian» (2023); «MMTEB: Massive Multilingual Text Embedding Benchmark» (2025); «MERA: A Comprehensive LLM Evaluation in Russian» (2024); «RussianSuperGLUE: A Russian Language Understanding Evaluation Benchmark» (2020)
- `A5002957144` **Kai North** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Overview of the HASOC Subtrack at FIRE 2022: Hate Speech and Offensive Content Identification in English and Indo-Aryan Languages» (2022); «Findings of the VarDial Evaluation Campaign 2023» (2023); «Lexical Complexity Prediction: An Overview» (2022); «Lexical simplification benchmarks for English, Portuguese, and Spanish» (2022)
- `A5002542089` **Olga Soloukhina** — Высшая школа экономики; оценка **0 = 0**
  - работы: «Grey and white matter substrates of action naming» (2019); «The Russian Aphasia Test: The first comprehensive, quantitative, standardized, and computerized aphasia language battery in Russian» (2021); «Prevalence of Verb and Sentence Impairment in Aphasia as Demonstrated by Cluster Analysis» (2020); «Investigating comprehension of nouns and verbs: is there a difference?» (2017); «‘Moderate global aphasia’: A generalized decline of language processing caused by glioma surgery but not stroke» (2021)

## `q10` — Хочу делать data science в физике: анализ больших данных с экспериментов, Python, ML-пайплайны

*Разошлось:* s1, s5, top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 0 | 0 | 0.466 | `A5112651411` (1 = 1), `A5103568609` (1 = 1), `A5030454460` (1 = 1), `A5075534567` (1 → 0 ⚠), `A5084513745` (1 → 0 ⚠) |
| потолок 9 010 | 1 | 1 | 0.472 | `A5029181198` (2 → 1 ⚠), `A5112651411` (1 = 1), `A5027535433` (2 = 2), `A5103568609` (1 = 1), `A5030454460` (1 = 1) |
| 12 119 | 1 | 1 | 0.517 | `A5069979785` (2 = 2), `A5029181198` (2 → 1 ⚠), `A5112651411` (1 = 1), `A5027535433` (2 = 2), `A5103568609` (1 = 1) |

- `A5112651411` **Kenenbek Arzymatov** — Высшая школа экономики; оценка **1 = 1**
  - работы: «First observation of the decay $B_s^0 \to K^-\mu^+\nu_\mu$ and Measurement of $|V_{ub}|/|V_{cb}|$» (2021); «Online Neural Networks for Change-Point Detection» (2026); «NEURAL NETWORK APPROACH TO APPROXIMATION OF LOCAL COALESCENTE TIME» (2023); «Deep Learning for Inferring Distribution of Time to the Last Common Ancestor from a Diploid Genome» (2022)
- `A5103568609` **P. Parfenov** — Национальный исследовательский ядерный университет МИФИ; оценка **1 = 1**
  - работы: «Production of protons, deuterons and tritons in argon-nucleus interactions at 3.2 A GeV» (2025); «Hyperon global polarization in isobar Ru+Ru and Zr+Zr collisions at s N N = 200 G e V» (2025); «Performance study of the Highly Granular Neutron Detector prototype in the BM@N experiment» (2025); «Production of Λ hyperons in 4.0A GeV and 4.5A GeV carbon-nucleus interactions at the Nuclotron» (2026)
- `A5030454460` **Evgeni Burovski** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Author Correction: SciPy 1.0: fundamental algorithms for scientific computing in Python» (2020); «PyTorch 2: Faster Machine Learning Through Dynamic Python Bytecode Transformation and Graph Compilation» (2024); «Critical Temperature and Thermodynamics of Attractive Fermions at Unitarity» (2006); «Quantitative Determination of Temperature in the Approach to Magnetic Order of Ultracold Fermions in an Optical Lattice» (2010)
- `A5075534567` **I. Alekseev** — Национальный исследовательский ядерный университет МИФИ; оценка **1 → 0 ⚠**
  - работы: «Search for Large Extra Dimensions in the DANSS Experiment» (2025); «Searches for New Physics in the DANSS Experiment» (2026); «The super fine-grained detector for the T2K neutrino oscillation experiment» (2026); «Borehole muon tomograph for search and evaluation of ore deposits» (2025)
- `A5084513745` **C. Z. Yuan** — Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики; оценка **1 → 0 ⚠**
  - работы: «An Efficient Scheduling Method in Supply Chain Logistics Based on Network Flow» (2025); «A study of artificial intelligence in writing assessment for secondary school students: a comparative analysis based on the GPT-4 and human raters» (2025); «The structure-preserving spectral graph neural network for dual kinase inhibitors and synergy scoring in gastric cancer» (2025)
- `A5029181198` **Denis Derkach** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «Toward Machine Learning Optimization of Experimental Design» (2021); «NFAD: fixing anomaly detection using normalizing flows» (2021); «Normalizing flows for deep anomaly detection» (2019); «Online Neural Networks for Change-Point Detection» (2026)
- `A5027535433` **F. Ratnikov** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Optimization of the Accelerator Control by Reinforcement Learning: A Simulation-Based Approach» (2025); «Neutron Reconstruction in the BM@N Experiment Using Machine Learning» (2024); «Measurement of the $Λ^0_b\rightarrow J/ψΛ$ angular distribution and the $Λ^0_b$ polarisation in $pp$ collisions» (2020)
- `A5069979785` **Maria Grigorieva** — Московский государственный университет; оценка **2 = 2**
  - работы: «Clustering error messages produced by distributed computing infrastructure during the processing of high energy physics data» (2021); «Methods of Data Popularity Evaluation in the ATLAS Experiment at the LHC» (2021); «BigData and computing challenges in high energy and nuclear physics» (2017)

## `q11` — Интересует оптимизация маршрутов доставки и алгоритмы для логистики

*Разошлось:* s1, top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 0 | 1 | 0.491 | `A5086469184` (1 = 1), `A5075059819` (2 → 1 ⚠), `A5035328594` (2 → 1 ⚠), `A5112269203` (2 → 1 ⚠), `A5035075324` (2 → 1 ⚠) |
| потолок 9 010 | 1 | 1 | 0.492 | `A5107965221` (2 = 2), `A5086469184` (1 = 1), `A5075059819` (2 → 1 ⚠), `A5013081744` (1 = 1), `A5051886862` (1 = 1) |
| 12 119 | 1 | 1 | 0.492 | `A5107965221` (2 = 2), `A5086469184` (1 = 1), `A5075059819` (2 → 1 ⚠), `A5013081744` (1 = 1), `A5051886862` (1 = 1) |

- `A5086469184` **А. В. Пантелеев** — Московский авиационный институт; оценка **1 = 1**
  - работы: «Application of the Tomtit Flock Metaheuristic Optimization Algorithm to the Optimal Discrete Time Deterministic Dynamical Control Problem» (2022); «Application of a Memetic Algorithm for the Optimal Control of Bunches of Trajectories of Nonlinear Deterministic Systems with Incomplete Feedback» (2018); «Meta-heuristic interval methods of search of optimal in average control of nonlinear determinate systems with incomplete information about its parameters» (2017)
- `A5075059819` **Alexander Petunin** — Уральский федеральный университет; оценка **2 → 1 ⚠**
  - работы: «Challenges and Opportunities in Industry 4.0 for Mechatronics, Artificial Intelligence and Cybernetics» (2021); «Optimization Models of Tool Path Problem for CNC Sheet Metal Cutting Machines» (2016); «Model of megalopolises in the tool path optimisation for CNC plate cutting machines» (2018)
- `A5035328594` **A. G. Chent︠s︡ov** — Уральский федеральный университет; оценка **2 → 1 ⚠**
  - работы: «Asymptotic Attainability» (1997); «Finitely Additive Measures and Relaxations of Extremal Problems» (1996); «The dynamic programming method in the generalized traveling salesman problem» (1997); «Development of Methods for Route Optimization of Work in Inhomogeneous Radiation Fields to Minimize the Dose Load of Personnel» (2022); «Model of megalopolises in the tool path optimisation for CNC plate cutting machines» (2018)
- `A5112269203` **Valery Lukinskiy** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «Methods of Accident Reconstruction and Investigation Given the Parameters of Vehicle Condition and Road Environment» (2017); «Concept of Quantitative Assessment of Knowledge Uncertainty in Accident Reconstruction Tasks» (2017); «Problems of the Supply Chain Reliability Evaluation» (2014); «Control of inventory dynamics: A survey of special cases for products with low demand» (2020); «A probabilistic approach to information management of order fulfilment reliability with the help of perfect-order analytics» (2022)
- `A5035075324` **Victor Zakharov** — Санкт-Петербургский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Optimization Models and Methods for Equilibrium Traffic Assignment» (2019); «DESIGNING BATCH-MANUFACTURING ENTERPRISES USING ONTOLOGIES» (2018); «Data Mining Methods and Techniques for Fault Detection and Predictive Maintenance in Housing and Utility Infrastructure» (2018); «Competitive Traffic Assignment in Road Networks» (2016)
- `A5107965221` **P. A. Chentsov** — Уральский федеральный университет; оценка **2 = 2**
  - работы: «Routing under constraints: Problem of visit to megalopolises» (2016); «Local dynamic programming incuts in routing problems with restrictions» (2014); «The routing problems with optimization of the starting point: dynamic programming» (2019); «About a Routing Problem of the Tool Motion on Sheet Cutting» (2015)
- `A5013081744` **V. A. Rasskazova** — Московский авиационный институт; оценка **1 = 1**
  - работы: «On Track Procession Assignment Problem at the Railway Network Sections» (2020); «Modelling railway freight traffic using the methods of graph theory and combinatorial optimization» (2016); «An Inference Algorithm for Monotone Boolean Functions Associated with Undirected Graphs» (2016); «Learning and Intelligent Optimization» (2022); «Convex Hulls in Solving Multiclass Pattern Recognition Problem» (2020); «ML and MILP Models in Production Planning Under Uncertainty» (2026)
- `A5051886862` **Dmitry Arkhipov** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Operator assignment problem in aircraft assembly lines: a new planning approach taking into account economic and ergonomic constraints» (2018); «An efficient pseudo-polynomial algorithm for finding a lower bound on the makespan for the Resource Constrained Project Scheduling Problem» (2018); «Scheduling jobs with equal processing times on a single machine: minimizing maximum lateness and makespan» (2016); «Skills management in the optimization of aircraft maintenance processes» (2017); «Work planning in low-volume assembly lines under ergonomic constraints» (2018)

## `q14` — Хочу разобраться в квантовой теории информации: пропускная способность квантовых каналов, запутанность

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.440 | `A5017383854` (2 = 2), `A5012166541` (2 → 1 ⚠), `A5017633244` (2 → 1 ⚠), `A5103199431` (2 → 1 ⚠), `A5007384660` (2 → 1 ⚠) |
| потолок 9 010 | 1 | 1 | 0.450 | `A5111692775` (2 = 2), `A5017383854` (2 = 2), `A5012166541` (2 → 1 ⚠), `A5017633244` (2 → 1 ⚠), `A5103199431` (2 → 1 ⚠) |
| 12 119 | 1 | 1 | 0.450 | `A5111692775` (2 = 2), `A5017383854` (2 = 2), `A5012166541` (2 → 1 ⚠), `A5017633244` (2 → 1 ⚠), `A5103199431` (2 → 1 ⚠) |

- `A5017383854` **M. E. Shirokov** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Continuous Ensembles and the Capacity of Infinite-Dimensional Quantum Channels» (2006); «On the notion of entanglement in Hilbert spaces» (2005); «On approximation of infinite-dimensional quantum channels» (2008); «Entropy characteristics of subsets of states. I» (2006)
- `A5012166541` **Anton Kozubov** — Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики; оценка **2 → 1 ⚠**
  - работы: «Subcarrier wave continuous variable quantum key distribution with discrete modulation: mathematical model and finite-key analysis» (2020); «Feasibility of twin-field quantum key distribution based on multi-mode coherent phase-coded states» (2019); «Sideband quantum communication at 1 Mbit/s on a metropolitan area network» (2017)
- `A5017633244` **S. P. Kulik** — Московский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Quantum Teleportation of a Polarization State with a Complete Bell State Measurement» (2001); «Delayed “Choice” Quantum Eraser» (2000); «Infrared spectroscopy with visible light» (2016); «Charge transfer across C–H⋅⋅⋅O hydrogen bonds stabilizes oil droplets in water» (2021)
- `A5103199431` **Lan Zhou** — Московский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Quantum Secure Direct Communication with Quantum Memory» (2017); «Controllable Scattering of a Single Photon inside a One-Dimensional Resonator Waveguide» (2008); «Quantum Routing of Single Photons with a Cyclic Three-Level System» (2013); «Device-independent quantum secure direct communication against collective attacks» (2019)
- `A5007384660` **V. L. Kurochkin** — Московский физико-технический институт; оценка **2 → 1 ⚠**
  - работы: «Demonstration of a quantum key distribution network in urban fibre-optic communication lines» (2017); «Semi-Empirical Satellite-to-Ground Quantum Key Distribution Model for Realistic Receivers» (2023); «Eurasian-scale experimental satellite-based quantum key distribution with detector efficiency mismatch analysis» (2024)
- `A5111692775` **A. I. Trubilko** — Санкт-Петербургский государственный университет; оценка **2 = 2**
  - работы: «Can the states of the W-class be suitable for teleportation?» (2003); «Quantum teleportation of an Einstein-Podolsy-Rosen pair using an entangled three-particle state» (2000); «Quantum teleportation of EPR pair by three-particle entanglement» (1999); «On preparation of the entangled W-states from atomic ensembles» (2003); «On multiparticle W states, their implementations and application in the quantum informational problems» (2005)

## `q15` — Поиск тёмной материи

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.391 | `A5069514467` (2 → 1 ⚠), `A5039966405` (2 = 2), `A5032951968` (2 → 1 ⚠), `A5107980327` (1 = 1), `A5024187788` (2 = 2) |
| потолок 9 010 | 1 | 1 | 0.404 | `A5071620748` (2 = 2), `A5069514467` (2 → 1 ⚠), `A5039966405` (2 = 2), `A5032951968` (2 → 1 ⚠), `A5107980327` (1 = 1) |
| 12 119 | 1 | 1 | 0.442 | `A5020876643` (2 = 2), `A5071620748` (2 = 2), `A5069514467` (2 → 1 ⚠), `A5039966405` (2 = 2), `A5071164723` (2 → 1 ⚠) |

- `A5069514467` **I. V. Arkhangelskaja** — Национальный исследовательский ядерный университет МИФИ; оценка **2 → 1 ⚠**
  - работы: «Status of the GAMMA-400 project» (2012); «Design and performance of the GAMMA-400 gamma-ray telescope for dark matter searches» (2013); «The GAMMA-400 experiment: Status and prospects» (2015); «Characteristics of the GAMMA-400 gamma-ray telescope for searching for dark matter signatures» (2013); «Magnetic storm of November, 2004: Solar, interplanetary, and magnetospheric disturbances» (2007)
- `A5039966405` **A. Bolozdynya** — Национальный исследовательский ядерный университет МИФИ; оценка **2 = 2**
  - работы: «First Results from the LUX Dark Matter Experiment at the Sanford Underground Research Facility» (2014); «Observation of coherent elastic neutrino-nucleus scattering» (2017); «First Results from the XENON10 Dark Matter Experiment at the Gran Sasso National Laboratory» (2008); «Search for Light Dark Matter in XENON10 Data» (2011); «The Large Underground Xenon (LUX) experiment» (2012)
- `A5032951968` **A. I. Arkhangelskiy** — Национальный исследовательский ядерный университет МИФИ; оценка **2 → 1 ⚠**
  - работы: «Status of the GAMMA-400 project» (2012); «Design and performance of the GAMMA-400 gamma-ray telescope for dark matter searches» (2013); «The GAMMA-400 experiment: Status and prospects» (2015); «Characteristics of the GAMMA-400 gamma-ray telescope for searching for dark matter signatures» (2013); «Gamma- and Cosmic-Ray observations with the GAMMA-400 Gamma-Ray telescope» (2022)
- `A5107980327` **А. Антонов** — Московский государственный университет; оценка **1 = 1**
  - работы: «Serine and glycine metabolism in cancer» (2014); «Proof of principle for a light dark matter search with low-energy positron beams at NA64» (2025); «Excessive scarring in glaucoma surgery. Part 2: Anti-inflammatory therapy, antimetabolites, angiogenesis inhibitors» (2025)
- `A5024187788` **A. A. Feshchenko** — Уральский федеральный университет; оценка **2 = 2**
  - работы: «ATLAS: Technical proposal for a general-purpose p p experiment at the Large Hadron Collider at CERN» (1994); «Dark Matter Search in Missing Energy Events with NA64» (2019); «Search for a Hypothetical 16.7 MeV Gauge Boson and Dark Photons in the NA64 Experiment at CERN» (2018); «Search for Axionlike and Scalar Particles with the NA64 Experiment» (2020)
- `A5071620748` **A. Ilyasov** — Национальный исследовательский ядерный университет МИФИ; оценка **2 = 2**
  - работы: «First Direct Detection Constraints on Planck-Scale Mass Dark Matter with Multiple-Scatter Signatures Using the DEAP-3600 Detector» (2022); «Constraints on dark matter-nucleon effective couplings in the presence of kinematically distinct halo substructures using the DEAP-3600 detector» (2020); «Pulse-shape discrimination against low-energy Ar-39 beta decays in liquid argon with 4.5 tonne-years of DEAP-3600 data» (2021)
- `A5020876643` **S. Chashin** — Московский государственный университет; оценка **2 = 2**
  - работы: «Separating $^{39}$Ar from $^{40}$Ar by cryogenic distillation with Aria for dark matter searches» (2021); «Search for dark matter annual modulation with DarkSide-50» (2023); «Long-term temporal stability of the DarkSide-50 dark matter detector» (2024)
- `A5071164723` **M. Chernyavskiy** — Московский государственный университет; оценка **2 → 1 ⚠**
  - работы: «A facility to Search for Hidden Particles (SHiP) at the CERN SPS» (2015); «Method for Determining the Etching Rate in Phosphate Glass Detectors» (2022); «Phosphate Glass Detectors for Heavy Ion Identification» (2022); «Quantitative description of internal 3D structure of a geological sample using algebraic topology methods» (2025)

## `q16` — Мемристоры и нейроморфные вычисления

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.429 | `A5101578748` (2 = 2), `A5034121563` (2 = 2), `A5091785597` (2 = 2), `A5061341300` (0 = 0), `A5056817341` (2 → 1 ⚠) |
| потолок 9 010 | 1 | 1 | 0.491 | `A5083126736` (2 = 2), `A5101578748` (2 = 2), `A5034121563` (2 = 2), `A5061589446` (2 = 2), `A5091785597` (2 = 2) |
| 12 119 | 1 | 1 | 0.491 | `A5083126736` (2 = 2), `A5075899988` (2 = 2), `A5101578748` (2 = 2), `A5053176048` (2 = 2), `A5034121563` (2 = 2) |

- `A5101578748` **А. А. Несмелов** — Московский государственный технический университет имени Н. Э. Баумана; оценка **2 = 2**
  - работы: «Reliable Memristive Synapses Based on Parylene-MoOx Nanocomposites for Neuromorphic Applications» (2023); «Poly-para-xylylene-Based Memristors on Flexible Substrates» (2019); «Parylene-based memristive synapses for hardware neural networks capable of dopamine-modulated STDP learning» (2021)
- `A5034121563` **A. V. Emelyanov** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Journal of Magnetism and Magnetic Materials» (2022); «Necessary conditions for STDP-based pattern recognition learning in a memristive spiking neural network» (2020); «Noise-assisted persistence and recovery of memory state in a memristive spiking neuromorphic network» (2021); «First steps towards the realization of a double layer perceptron based on organic memristive devices» (2016); «Hardware elementary perceptron based on polyaniline memristive devices» (2015); «Electrochemical origins underlying enhanced resistive switching reliability in flexible Cu/parylene-MoOx/ITO memristors for wearable neuromorphic applications» (2026)
- `A5091785597` **В. А. Демин** — Московский государственный университет; оценка **2 = 2**
  - работы: «Neurohybrid Memristive CMOS-Integrated Systems for Biosensors and Neuroprosthetics» (2020); «Necessary conditions for STDP-based pattern recognition learning in a memristive spiking neural network» (2020); «Noise-assisted persistence and recovery of memory state in a memristive spiking neuromorphic network» (2021); «Transfer of Silver Nanoparticles through the Placenta and Breast Milk during in vivo Experiments on Rats.» (2013); «First steps towards the realization of a double layer perceptron based on organic memristive devices» (2016)
- `A5061341300` **G. Bueldt** — Московский физико-технический институт; оценка **0 = 0**
  - работы: «Inward H + pump xenorhodopsin: Mechanism and alternative optogenetic approach» (2017); «Conformation of phosphatidylethanolamine in the gel phase as seen by neutron diffraction» (1980); «SANS investigations of the lipidic cubic phase behaviour in course of bacteriorhodopsin crystallization» (2004); «Examining transfer of TERT to mitochondria under oxidative stress» (2024)
- `A5056817341` **Victor Kazantsev** — Московский физико-технический институт; оценка **2 → 1 ⚠**
  - работы: «Neurohybrid Memristive CMOS-Integrated Systems for Biosensors and Neuroprosthetics» (2020); «Real-Time EEG–EMG Human–Machine Interface-Based Control System for a Lower-Limb Exoskeleton» (2020); «Noise-assisted persistence and recovery of memory state in a memristive spiking neuromorphic network» (2021); «Design of Cultured Neuron Networks in vitro with Predefined Connectivity Using Asymmetric Microfluidic Channels» (2017)
- `A5083126736` **А. Н. Мацукатова** — Московский государственный университет; оценка **2 = 2**
  - работы: «Combination of Organic‐Based Reservoir Computing and Spiking Neuromorphic Systems for a Robust and Efficient Pattern Classification» (2023); «Scalable nanocomposite parylene-based memristors: Multifilamentary resistive switching and neuromorphic applications» (2022); «Resistive switching kinetics and second-order effects in parylene-based memristors» (2020)
- `A5061589446` **Anton Khanas** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Second‐Order Memristor Based on All‐Oxide Multiferroic Tunnel Junction for Biorealistic Emulation of Synapses» (2022); «Chemical, structural and magnetic properties of the Fe/Sb2Te3 interface» (2018); «Universal Synaptic Plasticity of Interface‐Based Second‐Order Memristors» (2024); «Fe/Sb2Te3 Interface Reconstruction through Mild Thermal Annealing» (2020)
- `A5075899988` **A. I. Iliasov** — Московский государственный университет; оценка **2 = 2**
  - работы: «Adapted MLP-Mixer network based on crossbar arrays of fast and multilevel switching (Co–Fe–B) x (LiNbO 3 ) 100− x nanocomposite memristors» (2023); «Convolutional Neural Network Based on Crossbar Arrays of (Co-Fe-B)x(LiNbO3)100−x Nanocomposite Memristors» (2022); «Memristors Based on Nanoscale Layers LiNbO3 and (Co40Fe40B20)x(LiNbO3)100 – x» (2020)
- `A5053176048` **Boris S. Shvetsov** — Московский государственный университет; оценка **2 = 2**
  - работы: «On the resistive switching mechanism of parylene-based memristive devices» (2019); «Parylene-based memristive crossbar structures with multilevel resistive switching for neuromorphic computing» (2022); «Poly-para-xylylene-Based Memristors on Flexible Substrates» (2019); «Parylene-based memristive synapses for hardware neural networks capable of dopamine-modulated STDP learning» (2021); «Plasticity of parylene memristors: Compact phenomenological model and synaptic properties» (2024)

## `q17` — Нейтринные эксперименты и безнейтринный двойной бета-распад

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.477 | `A5059653984` (2 = 2), `A5107886204` (1 → 2 ⚠), `A5000525652` (2 = 2), `A5070029333` (1 → 0 ⚠), `A5009133662` (1 → 0 ⚠) |
| потолок 9 010 | 1 | 1 | 0.496 | `A5104688244` (2 = 2), `A5059653984` (2 = 2), `A5107886204` (1 → 2 ⚠), `A5000525652` (2 = 2), `A5104387273` (2 → 1 ⚠) |
| 12 119 | 1 | 1 | 0.496 | `A5104688244` (2 = 2), `A5059653984` (2 = 2), `A5107886204` (1 → 2 ⚠), `A5000525652` (2 = 2), `A5104387273` (2 → 1 ⚠) |

- `A5059653984` **В. Н. Корноухов** — Национальный исследовательский ядерный университет МИФИ; оценка **2 = 2**
  - работы: «Results on Neutrinoless Double- β Decay of Ge76 from Phase I of the GERDA Experiment» (2013); «Light Sterile Neutrinos: A White Paper» (2012); «Results from SAGE (The Russian-American gallium solar neutrino experiment)» (1994); «Final Results of GERDA on the Search for Neutrinoless Double- β Decay» (2020)
- `A5107886204` **S. Belogurov** — Национальный исследовательский ядерный университет МИФИ; оценка **1 → 2 ⚠**
  - работы: «Results on Neutrinoless Double- β Decay of Ge76 from Phase I of the GERDA Experiment» (2013); «Final Results of GERDA on the Search for Neutrinoless Double- β Decay» (2020); «Improved Limit on Neutrinoless Double- β Decay of Ge76 from GERDA Phase II» (2018)
- `A5000525652` **Л. В. Инжечик** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Results on Neutrinoless Double- β Decay of Ge76 from Phase I of the GERDA Experiment» (2013); «Final Results of GERDA on the Search for Neutrinoless Double- β Decay» (2020); «Improved Limit on Neutrinoless Double- β Decay of Ge76 from GERDA Phase II» (2018); «Probing Majorana neutrinos with double-β decay» (2019)
- `A5070029333` **V. Belyaev** — Национальный исследовательский ядерный университет МИФИ; оценка **1 → 0 ⚠**
  - работы: «Direct photon production in Pb–Pb collisions at s NN = 2.76 TeV» (2016); «H Λ 3 and H ‾ Λ ¯ 3 production in Pb–Pb collisions at s NN = 2.76 TeV» (2016); «Multi-strange baryon production in p Pb collisions at s NN = 5.02 TeV» (2016); «The ALICE experiment: a journey through QCD» (2024)
- `A5009133662` **A. E. Blinov** — Новосибирский государственный университет; оценка **1 → 0 ⚠**
  - работы: «Direct CP Violating Asymmetry in B0→K+π− Decays» (2004); «Measurement of double charmonium production in e+e− annihilations at s=10.6 GeV» (2005); «Measurements of the Absolute Branching Fractions of B±→K±Xcc¯» (2006); «Measurement of branching fractions and CP and isospin asymmetries for B→K*γ» (2004)
- `A5104688244` **S. G. Belogurov** — Национальный исследовательский ядерный университет МИФИ; оценка **2 = 2**
  - работы: «Double beta decay of 100Mo» (2001); «New experimental limit on the 42Ar content in the Earth’s atmosphere» (1998); «Search for double beta decay of 100Mo with liquid argon ionization chamber (first results)» (1999); «New requirements on enriched isotopes for experiments studying neutrinoless double β-decay (GERDA experiment)» (2006); «Development of scintillation LXe/LKr electromagnetic calorimeter with wavelength shifting light collection» (1996); «Population of tetraneutron continuum in reactions of He 8 on deuterium» (2025)
- `A5104387273` **I. N. Machulin** — Национальный исследовательский ядерный университет МИФИ; оценка **2 → 1 ⚠**
  - работы: «Antineutrino-deuteron experiment at the Krasnoyarsk reactor» (2000); «Today and future neutrino experiments at Krasnoyarsk nuclear reactor» (2000); «Geoneutrinos» (2015); «reactor experiments of a new type to detect neutrino oscillations» (1992); «Double Chooz project: Status of a reactor experiment aimed at searches for neutrino oscillations» (2009)

## `q19` — Хочу что-нибудь на стыке физики и программирования

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 0 | 1 | 0.426 | `A5063523050` (0 = 0), `A5085935136` (0 = 0), `A5032107945` (0 → 1 ⚠), `A5030454460` (2 = 2), `A5087415130` (0 = 0) |
| потолок 9 010 | 0 | 1 | 0.452 | `A5107892335` (1 → 0 ⚠), `A5063523050` (0 = 0), `A5055391580` (0 = 0), `A5015779508` (2 = 2), `A5110984172` (0 = 0) |
| 12 119 | 0 | 1 | 0.452 | `A5107892335` (1 → 0 ⚠), `A5063523050` (0 = 0), `A5055391580` (0 = 0), `A5015779508` (2 = 2), `A5110984172` (0 = 0) |

- `A5063523050` **А. С. Бондаренко** — Санкт-Петербургский государственный университет; оценка **0 = 0**
  - работы: «Observation of collisionless shocks in a large current‐free laboratory plasma» (2014); «Dynamics of exploding plasmas in a large magnetized plasma» (2013); «Influence of grain boundary state on electrical resistivity of ultrafine grained aluminium» (2016); «Effect of annealing on microhardness and electrical resistivity of nanostructured SPD aluminium» (2016)
- `A5085935136` **I. Yu. Skobelev** — Национальный исследовательский ядерный университет МИФИ; оценка **0 = 0**
  - работы: «Laboratory formation of a scaled protostellar jet by coaligned poloidal magnetic field» (2014); «High Energy Density Z -Pinch Plasma Conditions with Picosecond Time Resolution» (2002); «Acceleration of highly charged GeV Fe ions from a low-Z substrate by intense femtosecond laser» (2015)
- `A5032107945` **В. А. Попов** — Новосибирский государственный университет; оценка **0 → 1 ⚠**
  - работы: «Novel electron beam based test facility for observation of dynamics of tungsten erosion under intense ELM-like heat loads» (2016); «Two-dimensional numerical simulation of tungsten melting in exposure to pulsed electron beam» (2018); «Heating of tungsten target by intense pulse electron beam» (2016); «In-situ imaging of tungsten surface modification under ITER-like transient heat loads» (2016)
- `A5030454460` **Evgeni Burovski** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Author Correction: SciPy 1.0: fundamental algorithms for scientific computing in Python» (2020); «PyTorch 2: Faster Machine Learning Through Dynamic Python Bytecode Transformation and Graph Compilation» (2024); «Critical Temperature and Thermodynamics of Attractive Fermions at Unitarity» (2006); «Quantitative Determination of Temperature in the Approach to Magnetic Order of Ultracold Fermions in an Optical Lattice» (2010)
- `A5087415130` **M. I. Guseva** — Высшая школа экономики; оценка **0 = 0**
  - работы: «Erosion of Be as plasma-facing material» (1997); «Sputtering of beryllium, tungsten, tungsten oxide and mixed W–C layers by deuterium ions in the near-threshold energy range» (1999); «Radiation blistering» (1981); «Chemical sputtering of graphite by H+ ions» (1976); «Radiation blistering of Nb Implanted sequentially with helium ions of different energies (3–500 keV)» (1976); «Functional Equivalence and Institutional Divergence in Cross-Border Settlement Systems» (2026); «Vitaphospholip® (water-soluble phosphatidylcholine) in the treatment of combined hyperlipidemia: a randomized, placebo-controlled clinical trial» (2025); «Ultra-small phospholipid nanoparticles in the treatment of combined hyperlipidemia: a randomized placebo-controlled clinical trial» (2024)
- `A5107892335` **S. M. Polozov** — Национальный исследовательский ядерный университет МИФИ; оценка **1 → 0 ⚠**
  - работы: «The SYLA Linear Electronic Accelerator–Injector for a Specialized Source of Synchrotron Radiation of the Fourth Generation» (2023); «Photoemission of Picosecond Electron Bunches with Large Charge in RF Guns» (2021); «Design of a Radio-Frequency Photogun for the Linac Injector of the Free-Electron Laser of the SYLA Ultimate Source of Synchrotron Radiation» (2024); «Design and Testing of the Photogun Resonator and Biperiodic Accelerating Structure with Traveling Wave for the Photoinjector at the IAP RAS» (2023)
- `A5055391580` **В. А. Платонов** — Уральский федеральный университет; оценка **0 = 0**
  - работы: «The wide-aperture gamma-ray telescope TAIGA-HiSCORE in the Tunka Valley: Design, composition and commissioning» (2016); «The TAIGA experiment: From cosmic-ray to gamma-ray astronomy in the Tunka valley» (2016); «Study of Dyeing of Thermostable Para/Meta-Aramid Fibre» (2005); «The TAIGA experiment: from cosmic ray to gamma-ray astronomy in the Tunka valley» (2016); «Properties of polyphosphoric acid» (2000); «Bis-Pyrene-Appended Polyvinyl Chloride: Mechanosynthesis and Nitro-Explosive Detection» (2026)
- `A5015779508` **S. L. Yakovlev** — Санкт-Петербургский государственный университет; оценка **2 = 2**
  - работы: «Nektar++: An open-source spectral/ h p element framework» (2015); «Investigation of He3 trimer on the base of Faddeev equations in configuration space» (2000); «Three-potential formalism for the three-body scattering problem with attractive Coulomb interactions» (2001); «Four-body Yakubovsky differential equations for identical particles» (1984); «High-order spectral/hp element discretisation for reaction–diffusion problems on surfaces: Application to cardiac electrophysiology» (2013)
- `A5110984172` **A. A. Shirokova** — Московский государственный технический университет имени Н. Э. Баумана; оценка **0 = 0**
  - работы: «Excitation functions for deuterium-induced reactions on 194Pt near the coulomb barrier» (2012); «Recoil-nucleus spectra in the interaction of cosmic-ray protons with spacecraft electronics» (2008); «Kinetically blocked self-assembly of colloidal strings with tunable interactions in magnetic fields» (2024)

## `q21` — Хочу заниматься новыми материалами и их применением в технике

*Разошлось:* s1, top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.424 | `A5050234205` (2 → 1 ⚠), `A5017448390` (2 = 2), `A5087662164` (1 = 1), `A5084061415` (1 = 1), `A5025897376` (2 = 2) |
| потолок 9 010 | 0 | 1 | 0.444 | `A5055391580` (1 = 1), `A5078249510` (2 = 2), `A5020775138` (2 = 2), `A5086295663` (2 = 2), `A5050234205` (2 → 1 ⚠) |
| 12 119 | 0 | 1 | 0.444 | `A5055391580` (1 = 1), `A5050009688` (2 = 2), `A5062677587` (2 = 2), `A5078249510` (2 = 2), `A5020775138` (2 = 2) |

- `A5050234205` **А. А. Васин** — Московский физико-технический институт; оценка **2 → 1 ⚠**
  - работы: «Progress and challenges of 3D-printing technologies in the manufacturing of piezoceramics» (2020); «First ground-level laboratory test of the two-phase xenon emission detector RED-100» (2020); «The RED-100 experiment» (2022); «Effect of Mechanical Pressure on the Recrystallization of Zinc Oxide in a Water Fluid Medium under Cold Sintering» (2021)
- `A5017448390` **Nikolay Andreev** — Национальный исследовательский технологический университет МИСиС; оценка **2 = 2**
  - работы: «Investigation of the influence of the thickness of nanolayers in wear-resistant layers of Ti-TiN-(Ti,Cr,Al)N coating on destruction in the cutting and wear of carbide cutting tools» (2020); «Investigation of wear dynamics for cutting tools with multilayer composite nanostructured coatings in turning constructional steel» (2018); «Investigation of wear mechanisms for the rake face of a cutting tool with a multilayer composite nanostructured Cr–CrN-(Ti,Cr,Al,Si)N coating in high-speed steel turning» (2019); «Investigation of multicomponent nanolayer coatings based on nitrides of Cr, Mo, Zr, Nb, and Al» (2020); «Influence of the nanostructure of Ti-TiN-(Ti,Al,Cr)N multilayer composite coating on tribological properties and cutting tool life» (2020); «Enhanced magnetic properties in Mn Co1−Fe2O4 nanoparticles: Unraveling the composition–annealing synergy» (2025)
- `A5087662164` **Н. В. Селезнева** — Уральский федеральный университет; оценка **1 = 1**
  - работы: «Additive manufacturing of heavy rare earth free high-coercivity permanent magnets» (2020); «Magnetic order, field-induced phase transitions and magnetoresistance in the intercalated compound Fe 0.5 TiS 2» (2013); «Ferromagnetism and structural transformations caused by Cr intercalation into TiTe2» (2009)
- `A5084061415` **Nikolay Ivanov** — Московский авиационный институт; оценка **1 = 1**
  - работы: «System Approach of Usability of HTS Electrical Machines in Future Electric Aircraft» (2017); «Thermal Management challenges for HEA – FUTPRINT 50» (2021); «Development and testing of 10 kW fully HTS generator» (2020); «Manufacturing and Testing of AC HTS-2 Coil for Small Electrical Motor» (2019)
- `A5025897376` **Pavel Peretyagin** — Московский государственный университет; оценка **2 = 2**
  - работы: «Direct Ink Writing Technology (3D Printing) of Graphene-Based Ceramic Nanocomposites: A Review» (2020); «Effect of graphene addition on the mechanical and electrical properties of Al 2 O 3 -SiCw ceramics» (2017); «Development of DLC-Coated Solid SiAlON/TiN Ceramic End Mills for Nickel Alloy Machining: Problems and Prospects» (2021); «Experimental Approbation of Selective Laser Melting of Powders by the Use of Non-Gaussian Power Density Distributions» (2014)
- `A5055391580` **В. А. Платонов** — Уральский федеральный университет; оценка **1 = 1**
  - работы: «The wide-aperture gamma-ray telescope TAIGA-HiSCORE in the Tunka Valley: Design, composition and commissioning» (2016); «The TAIGA experiment: From cosmic-ray to gamma-ray astronomy in the Tunka valley» (2016); «Study of Dyeing of Thermostable Para/Meta-Aramid Fibre» (2005); «The TAIGA experiment: from cosmic ray to gamma-ray astronomy in the Tunka valley» (2016); «Properties of polyphosphoric acid» (2000); «Bis-Pyrene-Appended Polyvinyl Chloride: Mechanosynthesis and Nitro-Explosive Detection» (2026)
- `A5078249510` **Anton Seleznev** — Московский государственный университет; оценка **2 = 2**
  - работы: «Direct Ink Writing Technology (3D Printing) of Graphene-Based Ceramic Nanocomposites: A Review» (2020); «Effect of adhesion and the wear-resistant layer thickness ratio on mechanical and performance properties of ZrN - (Zr,Al,Si)N coatings» (2018); «Properties of (Cr,Al,Si)N-(DLC-Si) composite coatings deposited on a cutting ceramic substrate» (2020); «Nano-scale multi-layered coatings for improved efficiency of ceramic cutting tools» (2016); «DLC-coating Application to Improve the Durability of Ceramic Tools» (2019); «Application of vanadium nitride coatings to improve wear resistance of stainless steel products» (2025); «Features of the Process of Surface Preparation of Products Using Glow Discharge Plasma During the Deposition of Modifying Coatings» (2025)
- `A5020775138` **S. D. Shlyapin** — Московский авиационный институт; оценка **2 = 2**
  - работы: «Investigation of the process of diffusion bonding of alloys based on titanium nickelide» (2012); «Mechanism of destruction of the Al–Al4C3–Al2O3 alumo-matrix dispersion-hardened composite material with a layered structure on static and shock loading» (2020); «Preparation of Porous Ceramic Based on Al2O3 as a Result of Zonal Compaction During Sintering of Powder Workpieces of Very Fine Aluminum Powder PAP-2 Combustion Products» (2019)
- `A5086295663` **Roman Khmyrov** — Московский государственный университет; оценка **2 = 2**
  - работы: «On the Possibility of Selective Laser Melting of Quartz Glass» (2014); «Crack-free selective laser melting of silica glass: single beads and monolayers on the substrate of the same material» (2015); «Obtaining Crack-free WC-Co Alloys by Selective Laser Melting» (2016); «Phase composition and microstructure of WC–Co alloys obtained by selective laser melting» (2017)
- `A5050009688` **Anastasia A. Kholodkova** — Московский государственный университет; оценка **2 = 2**
  - работы: «Progress and challenges of 3D-printing technologies in the manufacturing of piezoceramics» (2020); «The Fabrication and Characterization of BaTiO3 Piezoceramics Using SLA 3D Printing at 465 nm Wavelength» (2022); «Crystalline barium titanate synthesized in sub- and supercritical water» (2016); «Solid state synthesis of barium titanate in air and in supercritical water: Properties of powder and ceramics» (2019); «Properties of barium titanate ceramics based on powder synthesized in supercritical water» (2018); «Cold sintering of calcium titanate-based material» (2026); «Cold sintering and magnetic properties of high-entropy oxide (Mn,Fe,Co,Ni,Cu)3O4 ceramics» (2026)
- `A5062677587` **Alexander P. Malakhinsky** — Московский государственный университет; оценка **2 = 2**
  - работы: «Processing and Characterization of Spark Plasma Sintered SiC-TiB2-TiC Powders» (2022); «Granulation of Silicon Nitride Powders by Spray Drying: A Review» (2022); «The Influence of Surface Texturing of Ceramic and Superhard Cutting Tools on the Machining Process—A Review» (2022)

## `q23` — Квантовые компьютеры

*Разошлось:* top1. *Тип запроса:* edge.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.454 | `A5095070139` (2 = 2), `A5033682739` (2 = 2), `A5025096043` (2 = 2), `A5078641429` (2 → 1 ⚠), `A5111760858` (2 = 2) |
| потолок 9 010 | 1 | 1 | 0.454 | `A5095070139` (2 = 2), `A5065309599` (2 = 2), `A5020945978` (2 = 2), `A5033682739` (2 = 2), `A5025096043` (2 = 2) |
| 12 119 | 1 | 1 | 0.467 | `A5046709716` (2 = 2), `A5095070139` (2 = 2), `A5065309599` (2 = 2), `A5020945978` (2 = 2), `A5080313215` (2 = 2) |

- `A5095070139` **Hadi Salloum** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Comprehensive Overview of Reward Engineering and Shaping in Advancing Reinforcement Learning Applications» (2024); «Integration of Machine Learning with Quantum Annealing» (2024); «Quantum Microservices: Transforming Software Architecture with Quantum Computing» (2024); «Performance of Quantum Annealing Machine Learning Classification Models on ADMET Datasets» (2025); «Mini-scale traffic flow optimization: an iterative QUBOs approach converting from hybrid solver to pure quantum processing unit» (2025)
- `A5033682739` **Evgeniy O. Kiktenko** — Национальный исследовательский технологический университет МИСиС; оценка **2 = 2**
  - работы: «Quantum computers put blockchain security at risk» (2018); «Single qudit realization of the Deutsch algorithm using superconducting many-level quantum circuits» (2015); «Multilevel superconducting circuits as two-qubit systems: Operations, state preparation, and entropic inequalities» (2015); «Scalable quantum computing with qudits on a graph» (2020); «Bidirectional imperfect quantum teleportation with a single Bell state» (2016)
- `A5025096043` **Ilya A. Simakov** — Национальный исследовательский технологический университет МИСиС; оценка **2 = 2**
  - работы: «High fidelity two-qubit gates on fluxoniums using a tunable coupler» (2022); «Tunable coupling scheme for implementing two-qubit gates on fluxonium qubits» (2021); «Demonstration of a parity-time-symmetry-breaking phase transition using superconducting and trapped-ion qutrits» (2024)
- `A5078641429` **A. P. Alodjants** — Санкт-Петербургский национальный исследовательский университет информационных технологий, механики и оптики; оценка **2 → 1 ⚠**
  - работы: «Quantum machine learning: from physics to software engineering» (2023); «Qubits Based on Polariton Rabi Oscillators» (2014); «Classical (Local and Contextual) Probability Model for Bohm–Bell Type Experiments: No-Signaling as Independence of Random Variables» (2019)
- `A5111760858` **Yuriy Makhlin** — Высшая школа экономики; оценка **2 = 2**
  - работы: «Quantum-state engineering with Josephson-junction devices» (2001); «Josephson-junction qubits with controlled couplings» (1999); «Decoherence in a superconducting quantum bit circuit» (2005); «Nonlocal Properties of Two-Qubit Gates and Mixed States, and the Optimization of Quantum Computations» (2002); «Continuous-Time Monitoring of Landau-Zener Interference in a Cooper-Pair Box» (2006)
- `A5065309599` **Alexander Yu. Vlasov** — Санкт-Петербургский государственный университет; оценка **2 = 2**
  - работы: «Quantum Computations and Images Recognition» (1997); «Clifford algebras and universal sets of quantum gates» (2001); «RedShift» (2022); «Clifford Algebras, Spin Groups and Qubit Trees» (2022)
- `A5020945978` **Aleksey N. Bolgar** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «Quantum Regime of a Two-Dimensional Phonon Cavity» (2018); «Demonstration of a parity-time-symmetry-breaking phase transition using superconducting and trapped-ion qutrits» (2024); «Hybrid quantum learning with data reuploading on a small-scale superconducting quantum simulator» (2024)
- `A5046709716` **Yuri Ozhigov** — Московский государственный университет; оценка **2 = 2**
  - работы: «Quantum Computers Speed Up Classical with Probability Zero» (1998); «Amplitude quanta in multiparticle-system simulation» (2006); «Quantum Computer Can Not Speed Up Iterated Applications of a Black Box» (1999); «Using a modified version of the Tavis–Cummings–Hubbard model to simulate the formation of neutral hydrogen molecule» (2023); «About Chemical Modifications of Finite Dimensional QED Models» (2021)
- `A5080313215` **Gleb Kalachev** — Московский государственный университет; оценка **2 = 2**
  - работы: «Asymptotically good Quantum and locally testable classical LDPC codes» (2022); «Degenerate Quantum LDPC Codes With Good Finite Length Performance» (2021); «Quantum LDPC Codes With Almost Linear Minimum Distance» (2021); «Multi-Tensor Contraction for XEB Verification of Quantum Circuits» (2021)

## `q25` — Свепроводимость и купперовские пары, хочу занматься теорией

*Разошлось:* s5, top1. *Тип запроса:* edge.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 0 | 1 | 0.388 | `A5069750047` (1 = 1), `A5036186489` (2 = 2), `A5089465154` (1 → 0 ⚠), `A5064613329` (0 = 0), `A5001985637` (1 → 0 ⚠) |
| потолок 9 010 | 0 | 1 | 0.390 | `A5015225689` (1 → 0 ⚠), `A5069750047` (1 = 1), `A5011816761` (1 → 0 ⚠), `A5031290021` (1 → 0 ⚠), `A5036186489` (2 = 2) |
| 12 119 | 0 | 0 | 0.407 | `A5007376506` (1 → 0 ⚠), `A5015225689` (1 → 0 ⚠), `A5051814793` (0 = 0), `A5014271194` (0 = 0), `A5069750047` (1 = 1) |

- `A5069750047` **В. И. Воронкова** — Московский государственный университет; оценка **1 = 1**
  - работы: «Influence of oxygen stoichiometry on the irreversible magnetization and flux creep inR Ba2 Cu3 O7−δ (R=Y,Tm) single crystals» (1995); «Ferroelectric Phase Transitions and Properties of Crystals of the KTiOPO4 Family» (1986); «Structure and properties of crystals in the potassium titanyl phosphate family: A review» (2007)
- `A5036186489` **M. Yu. Kupriyanov** — Московский физико-технический институт; оценка **2 = 2**
  - работы: «The current-phase relation in Josephson junctions» (2004); «Beyond Moore’s technologies: operation principles of a superconductor alternative» (2017); «Degenerate Ground State in a Mesoscopic YBa2Cu3O7−x Grain Boundary Josephson Junction» (2001); «Theoretical investigation of Josephson tunnel junctions with spatially inhomogeneous superconducting electrodes» (1988)
- `A5089465154` **V. V. Pavlovskiy** — Высшая школа экономики; оценка **1 → 0 ⚠**
  - работы: «NbS3 : A unique quasi-one-dimensional conductor with three charge density wave transitions» (2017); «The operation of THz quantum cascade laser in the region of negative differential resistance» (2019); «Pressure-induced reentrant transition in NbS3 phases: Combined Raman scattering and x-ray diffraction study» (2019)
- `A5064613329` **Ivan L. Ivanov** — Уральский федеральный университет; оценка **0 = 0**
  - работы: «Thermodynamics of formation of hybrid perovskite-type methylammonium lead halides» (2017); «Chemical lattice strain in nonstoichiometric oxides: an overview» (2022); «Formation Thermodynamics, Stability, and Decomposition Pathways of CsPbX3 (X = Cl, Br, I) Photovoltaic Materials» (2020); «New phase transition in CsPbBr3» (2020); «Oxygen content, crystal structure and chemical expansion of PrBaCo 2−x Fe x O 6−δ double perovskites» (2014)
- `A5001985637` **Pavel V. Ovcharov** — Московский государственный технический университет имени Н. Э. Баумана; оценка **1 → 0 ⚠**
  - работы: «Particle-Resolved Phase Identification in Two-Dimensional Condensable Systems» (2017); «Flame propagation in two-dimensional solids: Particle-resolved studies with complex plasmas» (2017); «2D colloids in rotating electric fields: A laboratory of strong tunable three-body interactions» (2021); «Experimental studies of two-dimensional complex plasma crystals: waves and instabilities» (2019)
- `A5015225689` **M. A. Prosnikov** — Высшая школа экономики; оценка **1 → 0 ⚠**
  - работы: «Direct Observation of Magnon-Phonon Strong Coupling in Two-Dimensional Antiferromagnet at High Magnetic Fields» (2021); «Bright Exciton Fine-Structure in Two-Dimensional Lead Halide Perovskites» (2020); «Strain-Induced Exciton Hybridization in WS2 Monolayers Unveiled by Zeeman-Splitting Measurements» (2022); «Lattice dynamics and spontaneous magnetodielectric effect in ilmenite CoTiO3» (2020)
- `A5011816761` **N.A. Artiukhova** — Новосибирский государственный университет; оценка **1 → 0 ⚠**
  - работы: «Cu( ii ) complex with nitronyl nitroxide whose paramagnetism is suppressed by temperature decrease and/or pressure increase» (2016); «Heterospin complex showing spin transition at room temperature» (2015); «Spin-state-correlated optical properties of copper( ii )–nitroxide based molecular magnets» (2017); «Spirocyclic derivatives of nitronyl nitroxides in the design of heterospin CuII complexes manifesting spin transitions» (2013); «Spin transition characteristics of molecular solvates of CuII complexes with nitroxides: sensitivity to the packing type» (2019)
- `A5031290021` **Maria Kuznetsova** — Санкт-Петербургский государственный университет; оценка **1 → 0 ⚠**
  - работы: «Perovskite CsPbX3 (X=Cl, Br, I) Nanocrystals in fluorophosphate glasses» (2021); «Mode locking of hole spin coherences in CsPb(Cl, Br)3 perovskite nanocrystals» (2023); «Excitons in asymmetric quantum wells» (2016); «Tailoring the Electron and Hole Landé Factors in Lead Halide Perovskite Nanocrystals by Quantum Confinement and Halide Exchange» (2023); «Submillisecond Spin Relaxation in CsPb(Cl,Br)3 Perovskite Nanocrystals in a Glass Matrix» (2022); «Two-component nuclear spin relaxation dynamics in GaAs:Mn» (2026)
- `A5007376506` **Tatiana S. Yankova** — Московский государственный университет; оценка **1 → 0 ⚠**
  - работы: «Field-induced criticality in a gapped quantum magnet with bond disorder» (2012); «Order Parameters ⟨P2⟩, ⟨P4⟩, and ⟨P6⟩ of Aligned Nematic Liquid-Crystalline Polymer As Determined by Numerical Simulation of Electron Paramagnetic Resonance Spectra» (2012); «Long-lived magnons throughout the Brillouin zone of the strong-leg spin ladder (C 7 H 10 N) 2 CuBr 4» (2011)
- `A5051814793` **Julia V. Novoselova** — Санкт-Петербургский государственный университет; оценка **0 = 0**
  - работы: «Polymeric Metal Salen‐Type Complexes as Catalysts for Photoelectrocatalytic Hydrogen Peroxide Production» (2018); «Electrochemical deposition of PEDOT/MoS2 composite films for supercapacitors» (2022); «Tuning cationic transport in Nisalen polymers via pseudo-crown functionality» (2022); «Inversion of the Photogalvanic Effect of Conductive Polymers by Porphyrin Dopants» (2021); «Uncovering the mechanism of water-promoted electrochemical degradation of NiSalen polymers» (2023)
- `A5014271194` **Ekaterina M. Zubanova** — Московский государственный университет; оценка **0 = 0**
  - работы: «Femtosecond spectroscopy and TD-DFT calculations of CuCl 4 2− excited states» (2014); «UV–Vis Identification and DFT-Assisted Prediction of Structures of Cu(II)–Alkyl Chlorocomplexes» (2012); «Photochemistry of tetraalkylammonium tetrachlorocuprates in low-temperature matrices» (2009); «CuCl-based SILCs in the thiophene oxidation – Experimental and DFT-assisted study» (2019)

## `q30` — Интересует маркетинг в социальных сетях и продвижение бренда

*Разошлось:* top1. *Тип запроса:* in-domain.

| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |
|---|---|---|---|---|
| 5 538 | 1 | 1 | 0.481 | `A5006757486` (2 → 1 ⚠), `A5011298864` (2 → 1 ⚠), `A5020072191` (1 → 0 ⚠), `A5110589505` (1 = 1), `A5003350728` (2 → 1 ⚠) |
| потолок 9 010 | 1 | 1 | 0.481 | `A5006757486` (2 → 1 ⚠), `A5011298864` (2 → 1 ⚠), `A5020072191` (1 → 0 ⚠), `A5110589505` (1 = 1), `A5030795507` (1 = 1) |
| 12 119 | 1 | 1 | 0.523 | `A5045100844` (2 → 1 ⚠), `A5006757486` (2 → 1 ⚠), `A5011298864` (2 → 1 ⚠), `A5020072191` (1 → 0 ⚠), `A5110589505` (1 = 1) |

- `A5006757486` **Vera Butkouskaya** — Высшая школа экономики; оценка **2 → 1 ⚠**
  - работы: «Obstacles to Sustainable Entrepreneurship amongst Tourism Students: A Gender Comparison» (2020); «Entrepreneurial Orientation (EO), Integrated Marketing Communications (IMC), and Performance in Small and Medium-Sized Enterprises (SMEs): Gender Gap and Inter-Country Context» (2020); «Inter-Country Customer-Perspective Analysis of Strategic Antecedents and Consequences for Post-Purchase Behaviour in Integrated Marketing Communications (IMC)» (2020)
- `A5011298864` **Maria Smirnova** — Санкт-Петербургский государственный университет; оценка **2 → 1 ⚠**
  - работы: «The impact of market orientation on the development of relational capabilities and performance outcomes: The case of Russian industrial firms» (2010); «Development and Validation of a Cross-Nationally Stable Scale of Consumer Animosity» (2011); «Understanding the role of marketing–purchasing collaboration in industrial markets: The case of Russia» (2010); «Customer orientation as a multidimensional construct: Evidence from the Russian markets» (2017); «Assessing relationship quality in four business‐to‐business markets» (2009); «How to succeed in a dysfunctional environment: Configuring marketing agility components for better performance» (2025); «Accepting Artificial Intelligence at the Individual Level: Empirical Evidence from Russian Market» (2025)
- `A5020072191` **Svetlana S. Bodrunova** — Санкт-Петербургский государственный университет; оценка **1 → 0 ⚠**
  - работы: «The Ukraine conflict and the European media: A comparative study of newspapers in 13 European countries» (2018); «Beyond Left and Right: Real-World Political Polarization in Twitter Discussions on Inter-Ethnic Conflicts» (2019); «Who is the censor? Self-censorship of Russian journalists in professional routines and social networking» (2020); «Please Follow Us» (2017)
- `A5110589505` **Olessia Koltsova** — Высшая школа экономики; оценка **1 = 1**
  - работы: «Topic modelling for qualitative studies» (2015); «Latent dirichlet allocation» (2014); «News Media and Power in Russia» (2006); «Mapping the public agenda with topic modeling: The case of the Russian livejournal» (2013); «Detecting ethnicity-targeted hate speech in Russian social media texts» (2021)
- `A5003350728` **Song Yao** — Новосибирский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Sequential Search with Refinement: Model and Application with Click-Stream Data» (2016); «How do firms make money selling digital goods online?» (2014); «EXPRESS: the impact of soda taxes: pass-through, tax avoidance, and nutritional effects» (2020); «Determining Consumers’ Discount Rates with Field Studies» (2012); «The Impact of Soda Taxes: Pass-through, Tax Avoidance, and Nutritional Effects» (2018)
- `A5030795507` **Svetlana Berezka** — Высшая школа экономики; оценка **1 = 1**
  - работы: «The role of tourist gastronomy experiences in regional tourism in Russia» (2018); «Consumer’s Attitude to the Sharing Economy in Russia» (2020); «Sustainability trends and consumer perceived risks towards private labels» (2020); «The impact of relationship marketing practices on companies’ market and financial performance in emerging markets» (2024)
- `A5045100844` **Валентина Герасименко** — Московский государственный университет; оценка **2 → 1 ⚠**
  - работы: «Digital competencies in management: A way to superior competitiveness and resistance to changes» (2020); «Buildings from the Socialist Past as part of a City’s Brand Identity: The case of Warsaw» (2018); «APPROACH FOR MANAGEMENT OF BRAND POSITIONING: QUANTIFICATION OF VALUE MATCHING BETWEEN BRAND AND TARGET AUDIENCE» (2021); «Evaluation of consumer behaviour on the Internet under the conditions of pandemic shock based on search activity in the luxury segment» (2021)

---

## Часть 2. Случайная выборка новой партии


13 случайных пар из пула в 13 пар (seed=20260829). Шкала: **2** — прямое совпадение специализации, **1** — смежная область, **0** — нерелевантно.

## 1. `q28` × `A5015793075` — grade **0**

- **Запрос:** Хочу заниматься гражданским правом и договорным регулированием
- **НР:** Е. И. Моисеев — Московский государственный университет; Differential Equations and Boundary Problems; Differential Equations and Numerical Methods; Advanced Mathematical Modeling in Engineering; Stability and Controllability of Differential Equations
- **Работы из профиля (по ним ставится оценка):** «Optimization of boundary controls of string vibrations» (2005); «The basis property inL p of the systems of eigenfunctions corresponding to two problems with a spectral parameter in the boundary condition» (2000); «Convergence of spectral expansions for functions of the hölder class for two problems with a spectral parameter in the boundary condition» (2000); «A Remark on the Convergence Problem for Spectral Expansions Corresponding to a Classical Problem with Spectral Parameter in the Boundary Condition» (2001); «Radial multipliers in solutions of the Helmholtz equations» (2018); «On the generalized solvability to one nonlinear problem of mixed type» (2025)
- **Обоснование:** артефакт классификатора; работы про краевые задачи и управление колебаниями струны

## 2. `q22` × `A5020280635` — grade **2**

- **Запрос:** Интересно математическое моделирование реальных процессов, чтобы было применимо на практике
- **НР:** Leonid Kondratenko — Московский авиационный институт; Engineering Technology and Methodologies; Mechanical Systems and Engineering; Metallurgy and Material Forming; Industrial Engineering and Technologies
- **Работы из профиля (по ним ставится оценка):** «INVESTIGATION OF THE DYNAMICS OF NONLINEAR MECHANICAL SYSTEMS WITH LONG POWER LINES THROUGH DIGITAL MODELING» (2019); «Mathematical modeling of the processing of holes on CNC machines» (2019); «On the question of the relationship between longitudinal and torsional vibrations in the manufacture of holes in the details» (2017); «Investigation of dynamics of roll forming processes» (2018)
- **Обоснование:** моделирование динамики обработки отверстий на ЧПУ и раскатки труб — прикладное

## 3. `q21` × `A5086295663` — grade **2**

- **Запрос:** Хочу заниматься новыми материалами и их применением в технике
- **НР:** Roman Khmyrov — Московский государственный университет; Additive Manufacturing Materials and Processes; Additive Manufacturing and 3D Printing Technologies; Laser Material Processing Techniques; High Entropy Alloys Studies
- **Работы из профиля (по ним ставится оценка):** «On the Possibility of Selective Laser Melting of Quartz Glass» (2014); «Crack-free selective laser melting of silica glass: single beads and monolayers on the substrate of the same material» (2015); «Obtaining Crack-free WC-Co Alloys by Selective Laser Melting» (2016); «Phase composition and microstructure of WC–Co alloys obtained by selective laser melting» (2017)
- **Обоснование:** селективное лазерное плавление WC-Co и кварцевого стекла — материалы для аддитивных технологий

## 4. `q04` × `A5029059211` — grade **1**

- **Запрос:** Хочу в тему сверхпроводимости, но боюсь, что это слишком сложно для меня
- **НР:** А. G. Volkov — Уральский федеральный университет; Rare-earth and actinide compounds; Magnetic properties of thin films; Magnetic and transport properties of perovskites and related materials; Magnetic Properties of Alloys
- **Работы из профиля (по ним ставится оценка):** «Semiconductor-metal transition in FeSi in ultrahigh magnetic fields up to 450 T» (1998); «Electronic structure and magnetic susceptibility of nearly magnetic metals (palladium and platinum)» (2010); «Semiconductor-metal transition in FeSi in an ultrahigh magnetic field» (1999); «Electronic structure and quantum spin fluctuations at the magnetic phase transition in MnSi» (2017); «Effects of pd-hybridization in strongly correlated insulator FeSi» (2016)
- **Обоснование:** магнетизм и электронная структура FeSi, MnSi, Pd; сверхпроводимости нет

## 5. `q01` × `A5022906506` — grade **1**

- **Запрос:** Хочу заниматься машинным обучением для анализа текстов, интересна тема депрессии в соцсетях. Есть кто-то, кто этим занимается?
- **НР:** Oxana Mikhaylova — Высшая школа экономики; Impact of Technology on Adolescents; Social Media and Politics; Youth Education and Societal Dynamics; Sociopolitical Dynamics in Russia
- **Работы из профиля (по ним ставится оценка):** «Depression representations on the most popular Russian-language YouTube channels» (2023); «Radical Self-Representation in a Hostile Setting: Discursive Strategies of the Russian Lesbian Feminist Movement» (2021); «Self-representations of the experience of anorexia on YouTube: The joint influence of the explanatory model and the web platform» (2022)
- **Обоснование:** депрессия и анорексия на YouTube — дискурс-анализ, ML и NLP нет

## 6. `q25` × `A5031290021` — grade **1**

- **Запрос:** Свепроводимость и купперовские пары, хочу занматься теорией
- **НР:** Maria Kuznetsova — Санкт-Петербургский государственный университет; Perovskite Materials and Applications; Quantum and electron transport phenomena; Semiconductor Quantum Structures and Devices; Optical properties and cooling technologies in crystalline materials
- **Работы из профиля (по ним ставится оценка):** «Perovskite CsPbX3 (X=Cl, Br, I) Nanocrystals in fluorophosphate glasses» (2021); «Mode locking of hole spin coherences in CsPb(Cl, Br)3 perovskite nanocrystals» (2023); «Excitons in asymmetric quantum wells» (2016); «Tailoring the Electron and Hole Landé Factors in Lead Halide Perovskite Nanocrystals by Quantum Confinement and Halide Exchange» (2023); «Submillisecond Spin Relaxation in CsPb(Cl,Br)3 Perovskite Nanocrystals in a Glass Matrix» (2022); «Two-component nuclear spin relaxation dynamics in GaAs:Mn» (2026)
- **Обоснование:** спиновая физика перовскитных нанокристаллов, экситоны — смежно, эксперимент, сверхпроводимости нет

## 7. `q30` × `A5030795507` — grade **1**

- **Запрос:** Интересует маркетинг в социальных сетях и продвижение бренда
- **НР:** Svetlana Berezka — Высшая школа экономики; Consumer Behavior in Brand Consumption and Identification; Diverse Aspects of Tourism Research; Customer Service Quality and Loyalty; Digital Marketing and Social Media
- **Работы из профиля (по ним ставится оценка):** «The role of tourist gastronomy experiences in regional tourism in Russia» (2018); «Consumer’s Attitude to the Sharing Economy in Russia» (2020); «Sustainability trends and consumer perceived risks towards private labels» (2020); «The impact of relationship marketing practices on companies’ market and financial performance in emerging markets» (2024)
- **Обоснование:** маркетинг и бренды (частные марки, relationship marketing); соцсетей в работах нет

## 8. `q28` × `A5033826700` — grade **1**

- **Запрос:** Хочу заниматься гражданским правом и договорным регулированием
- **НР:** Alexey Yu. Mamychev — Московский государственный университет; Legal and Policy Issues; Security, Politics, and Digital Transformation; Digital Transformation in Law; Sociopolitical Dynamics in Russia
- **Работы из профиля (по ним ставится оценка):** «Criteria for Recognition of AI as a Legal Person» (2019); «Sociocultural Bases of State - Legal Development Coding» (2015); «UNITY AND DIVERSITY IN "STATE" AS A CONCEPT IN POLITICAL-LEGAL THOUGHT» (2023); «The Convergence of Law: The Diversity of Discourses» (2015)
- **Обоснование:** теория и философия права, правосубъектность ИИ; гражданского и договорного нет

## 9. `q25` × `A5011816761` — grade **1**

- **Запрос:** Свепроводимость и купперовские пары, хочу занматься теорией
- **НР:** N.A. Artiukhova — Новосибирский государственный университет; Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Magnetism in coordination complexes; Crystallography and molecular interactions
- **Работы из профиля (по ним ставится оценка):** «Cu( ii ) complex with nitronyl nitroxide whose paramagnetism is suppressed by temperature decrease and/or pressure increase» (2016); «Heterospin complex showing spin transition at room temperature» (2015); «Spin-state-correlated optical properties of copper( ii )–nitroxide based molecular magnets» (2017); «Spirocyclic derivatives of nitronyl nitroxides in the design of heterospin CuII complexes manifesting spin transitions» (2013); «Spin transition characteristics of molecular solvates of CuII complexes with nitroxides: sensitivity to the packing type» (2019)
- **Обоснование:** молекулярные магнетики Cu(II)-нитроксилы, спиновые переходы — магнетизм, не сверхпроводимость

## 10. `q16` × `A5061589446` — grade **2**

- **Запрос:** Мемристоры и нейроморфные вычисления
- **НР:** Anton Khanas — Московский физико-технический институт; Advanced Memory and Neural Computing; Ferroelectric and Negative Capacitance Devices; Multiferroics and related materials; Neuroscience and Neural Engineering
- **Работы из профиля (по ним ставится оценка):** «Second‐Order Memristor Based on All‐Oxide Multiferroic Tunnel Junction for Biorealistic Emulation of Synapses» (2022); «Chemical, structural and magnetic properties of the Fe/Sb2Te3 interface» (2018); «Universal Synaptic Plasticity of Interface‐Based Second‐Order Memristors» (2024); «Fe/Sb2Te3 Interface Reconstruction through Mild Thermal Annealing» (2020)
- **Обоснование:** мемристоры второго порядка на мультиферроидных переходах, синаптическая пластичность, 2 работы

## 11. `q13` × `A5090699168` — grade **1**

- **Запрос:** Интересна рентгеновская дифракция и определение структуры кристаллов
- **НР:** Margarita S. Avdontceva — Санкт-Петербургский государственный университет; Crystallization and Solubility Studies; X-ray Diffraction in Crystallography; Crystal Structures and Properties; Crystallography and molecular interactions
- **Работы из профиля (по ним ставится оценка):** «Structural and chemical complexity of minerals: an update» (2022); «Diiodomethane as a halogen bond donor toward metal-bound halides» (2017); «Ligation-Enhanced π-Hole···π Interactions Involving Isocyanides: Effect of π-Hole···π Noncovalent Bonding on Conformational Stabilization of Acyclic Diaminocarbene Ligands» (2018)
- **Обоснование:** кристаллография в темах; работы — сложность минералов, галогенные связи, метод не показан

## 12. `q06` × `A5110579031` — grade **1**

- **Запрос:** Мне нравится возиться с лазерами в лаборатории, хочу что-то экспериментальное по оптике
- **НР:** E. A. Sharandin — Московский государственный технический университет имени Н. Э. Баумана; Laser Design and Applications; Solid State Laser Technologies; Geophysics and Sensor Technology; Pulsars and Gravitational Waves Research
- **Работы из профиля (по ним ставится оценка):** «High frequency gravitational waves generation by optical methods» (2020); «Experimental studies of polarization of laser radiation in a rotating optical glass» (2013); «A Mobile Full-Revolving Radiometric Complex for Astronomical and Atmospheric Research» (2023)
- **Обоснование:** одна экспериментальная работа по поляризации лазера (2013); рядом ГВ и мм-радиометр

## 13. `q28` × `A5037747723` — grade **0**

- **Запрос:** Хочу заниматься гражданским правом и договорным регулированием
- **НР:** Д. А. Никишин — Московский государственный университет; Reproductive Biology and Fertility; Neuroendocrine regulation and behavior; Ovarian function and disorders; Legal and Regulatory Analysis
- **Работы из профиля (по ним ставится оценка):** «Angiogenic potential of spheroids from umbilical cord and adipose-derived multipotent mesenchymal stromal cells within fibrin gel» (2018); «The Duo of Osteogenic and Angiogenic Differentiation in ADSC-Derived Spheroids» (2021); «Ladder-Shaped Ion Channel Ligands: Current State of Knowledge» (2017); «Selection of stable expressed reference genes in native and vitrified/thawed human ovarian tissue for analysis by qRT-PCR and Western blot» (2018)
- **Обоснование:** артефакт классификатора; работы про стромальные клетки и ионные каналы
