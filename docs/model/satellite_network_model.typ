// Модель спутниковой сети: математическое описание алгоритмов бекенда.
// Сборка: typst compile satellite_network_model.typ
// Используются только встроенные шрифты Typst и ни одного внешнего пакета.

// Палитра и общие настройки

#let ink = rgb("#1c2433")
#let muted = rgb("#5d6878")
#let hair = rgb("#d9dee6")
#let paper-tint = rgb("#f4f6f9")
#let c1 = rgb("#2563eb")
#let c2 = rgb("#7c3aed")
#let c3 = rgb("#0f766e")
#let bad = rgb("#dc2626")
#let mono = "DejaVu Sans Mono"

#set document(title: "Модель спутниковой сети")
#set page(
  paper: "a4",
  margin: (top: 2.3cm, bottom: 2.1cm, x: 2.1cm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(size: 7.5pt, fill: muted, font: mono)
      grid(
        columns: (1fr, auto),
        [МОДЕЛЬ СПУТНИКОВОЙ СЕТИ], [COSMO · КОСМОХАКАТОН 2026],
      )
      v(-5pt)
      line(length: 100%, stroke: 0.4pt + hair)
    }
  },
  footer: context {
    set text(size: 7.5pt, fill: muted, font: mono)
    h(1fr)
    counter(page).display("1 / 1", both: true)
  },
)
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "ru", fill: ink)
#set par(justify: true, leading: 0.62em, spacing: 0.95em)
#set heading(numbering: "1.1")
#set list(indent: 0.3em, body-indent: 0.55em, marker: text(fill: muted)[•])
#set enum(indent: 0.3em, body-indent: 0.55em)
#show raw: set text(font: mono, size: 0.84em)
#set figure(supplement: [Рис.])
#show figure.caption: set text(size: 9pt, fill: muted)
#set table(
  stroke: none,
  inset: (x: 6pt, y: 4.6pt),
  fill: (_, y) => if y > 0 and calc.even(y) { paper-tint },
)
#show table.cell.where(y: 0): set text(weight: "bold", size: 9.2pt)
#show table: set text(size: 9.6pt, hyphenate: false)
#show table: set par(justify: false)
#show table: it => block(breakable: false, width: 100%, it)

// Цвет текущего слоя: заголовки и блоки берут его из состояния

#let layer-color = state("layer-color", ink)

#show heading.where(level: 1): it => context {
  let col = layer-color.get()
  let title = text(size: 20pt, weight: "bold", hyphenate: false, it.body)
  block(width: 100%, above: if it.numbering != none { 2.4em } else { 1.6em }, below: 0.9em, sticky: true)[
    #if it.numbering != none {
      grid(
        columns: (auto, 1fr),
        column-gutter: 10pt,
        align: bottom,
        text(size: 30pt, weight: "bold", fill: col.lighten(15%), counter(heading).display("1")),
        title,
      )
    } else { title }
    #v(-3pt)
    #line(length: 100%, stroke: 1.2pt + col)
  ]
}

#show heading.where(level: 2): it => context {
  let col = layer-color.get()
  block(above: 1.45em, below: 0.7em, sticky: true)[
    #if it.numbering != none {
      text(font: mono, size: 9pt, weight: "bold", fill: col, counter(heading).display("1.1"))
      h(7pt)
    }
    #text(size: 12.5pt, weight: "bold", it.body)
  ]
}

// Строительные блоки

#let tag(body, col: muted) = text(font: mono, size: 7.6pt, fill: col, tracking: 0.07em, upper(body))

#let code(name) = box(
  inset: (x: 3pt),
  outset: (y: 2.4pt),
  radius: 2pt,
  fill: rgb("#eef1f5"),
  text(font: mono, size: 7.9pt, fill: muted, name),
)

#let layer-card(tagline, question, input, output) = context {
  let col = layer-color.get()
  block(width: 100%, fill: col.lighten(93%), radius: 5pt, inset: (x: 13pt, y: 11pt), above: 0.3em, below: 1.1em)[
    #tag(tagline, col: col.darken(10%))
    #v(2pt)
    #text(size: 11.5pt, weight: "bold", question)
    #v(3pt)
    #grid(
      columns: (auto, 1fr),
      column-gutter: 10pt,
      row-gutter: 6pt,
      tag[Вход], text(size: 9.8pt, input),
      tag[Выход], text(size: 9.8pt, output),
    )
  ]
}

#let rule(title, body) = context {
  let col = layer-color.get()
  block(
    width: 100%,
    fill: col.lighten(95%),
    stroke: (left: 2.2pt + col),
    inset: (left: 12pt, right: 11pt, top: 8pt, bottom: 9pt),
    radius: (right: 3pt),
    breakable: false,
    above: 0.9em,
    below: 0.9em,
  )[
    #tag(title, col: col.darken(12%))
    #v(-1pt)
    #body
  ]
}

#let insight(title, body) = block(
  width: 100%,
  fill: paper-tint,
  inset: (x: 11pt, y: 8pt),
  radius: 3pt,
  above: 0.85em,
  below: 0.85em,
)[
  #set par(spacing: 0.6em)
  #text(size: 9.8pt)[*#title.* #body]
]

#let part(label) = context {
  let col = layer-color.get()
  block(above: 1.6em, below: 0.4em, sticky: true)[
    #grid(
      columns: (auto, 1fr),
      column-gutter: 8pt,
      align: horizon,
      tag(label, col: col),
      line(length: 100%, stroke: 0.5pt + col.lighten(50%)),
    )
  ]
}

// Примитивы рисования: координаты задаются от левого верхнего угла рисунка

#let fig-seg(a, b, stroke: 0.7pt + ink) = place(top + left, line(start: a, end: b, stroke: stroke))
#let fig-dot(p, r: 2.7pt, fill: ink) = place(top + left, dx: p.at(0) - r, dy: p.at(1) - r, circle(radius: r, fill: fill, stroke: 0.6pt + white))
#let fig-ring(c, r, stroke: 0.7pt + ink, fill: none) = place(top + left, dx: c.at(0) - r, dy: c.at(1) - r, circle(radius: r, stroke: stroke, fill: fill))
#let fig-polar(c, r, ang) = (c.at(0) + r * calc.cos(ang), c.at(1) - r * calc.sin(ang))
#let fig-mid(a, b) = ((a.at(0) + b.at(0)) / 2, (a.at(1) + b.at(1)) / 2)
#let fig-label(p, body, dx: 0pt, dy: 0pt, width: 3.2cm, align-to: left, size: 8.4pt, fill: ink) = place(
  top + left,
  dx: p.at(0) + dx - (if align-to == center { width / 2 } else if align-to == right { width } else { 0pt }),
  dy: p.at(1) + dy,
  box(width: width, align(align-to, text(size: size, fill: fill, body))),
)
#let fig-arc(c, r, a0, a1, n: 18, stroke: 0.6pt + ink) = {
  for k in range(n) {
    fig-seg(fig-polar(c, r, a0 + (a1 - a0) * k / n), fig-polar(c, r, a0 + (a1 - a0) * (k + 1) / n), stroke: stroke)
  }
}
#let fig-arrow(a, b, paint: ink, thickness: 0.7pt, head: 4.2pt) = {
  fig-seg(a, b, stroke: thickness + paint)
  let dx = (b.at(0) - a.at(0)) / 1pt
  let dy = (b.at(1) - a.at(1)) / 1pt
  let len = calc.sqrt(dx * dx + dy * dy)
  let (ux, uy) = (dx / len, dy / len)
  let base = (b.at(0) - ux * head, b.at(1) - uy * head)
  place(top + left, polygon(
    fill: paint,
    stroke: none,
    b,
    (base.at(0) - uy * head * 0.45, base.at(1) + ux * head * 0.45),
    (base.at(0) + uy * head * 0.45, base.at(1) - ux * head * 0.45),
  ))
}
#let fig-dash(paint, thickness: 0.6pt) = (paint: paint, thickness: thickness, dash: "dashed")

// Титул

#block(width: 100%, below: 1.1em)[
  #set par(justify: false)
  #tag(col: c3)[КосмоХакатон 2026 · кейс «Проектирование устойчивой спутниковой группировки»]
  #v(5pt)
  #text(size: 25pt, weight: "bold")[Модель спутниковой сети]
  #v(1pt)
  #text(size: 13pt, fill: muted, hyphenate: false)[Как из сценария получаются маршруты, их характеристики и оценка отказоустойчивости]
  #v(9pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 3pt,
    rect(width: 100%, height: 3pt, fill: c1, stroke: none),
    rect(width: 100%, height: 3pt, fill: c2, stroke: none),
    rect(width: 100%, height: 3pt, fill: c3, stroke: none),
  )
]

Сервис отвечает на главный вопрос кейса: есть ли у каждого наземного клиента сквозной путь «клиент → спутники → шлюз», какой это путь и что с ним станет при отказе аппарата. Расчёт устроен как три слоя. Каждый слой отвечает на свой вопрос, получает готовый результат предыдущего и не пересчитывает его. Третий слой повторяется на каждом отсчёте сетки времени и сводит мгновенные результаты в показатели за период.

#heading(numbering: none)[Схема расчёта]

#let stage(col, label, title, sub) = box(
  width: 100%,
  height: 1.95cm,
  fill: col.lighten(92%),
  stroke: 0.7pt + col.lighten(45%),
  radius: 5pt,
  inset: (x: 5pt, y: 8pt),
)[
  #set align(center)
  #set par(justify: false)
  #set text(hyphenate: false)
  #tag(label, col: col.darken(8%))
  #v(1pt)
  #text(size: 10.5pt, weight: "bold", title)
  #v(-3pt)
  #text(size: 8.4pt, fill: muted, sub)
]
#let flow = text(size: 14pt, fill: muted)[→]

#figure(
  block(width: 100%)[
    #grid(
      columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr),
      column-gutter: 5pt,
      align: horizon,
      stage(muted, [вход], [Сценарий], [JSON cosmo-A-1.0]),
      flow,
      stage(c1, [слой 1], [3D-модель], [где узлы и кто работает]),
      flow,
      stage(c2, [слой 2], [Граф связности], [какие линии есть]),
      flow,
      stage(c3, [слой 3], [Алгоритмы], [путь и его устойчивость]),
    )
    #v(5pt)
    #box(width: 100%, fill: paper-tint, radius: 5pt, inset: (x: 11pt, y: 7pt))[
      #set text(size: 9.2pt)
      #grid(
        columns: (auto, auto, 1fr, auto),
        column-gutter: 8pt,
        align: horizon,
        text(size: 12pt, fill: muted)[↻],
        tag[слои 1, 2, 3 на каждом отсчёте],
        [$t_i = i Delta t, space i = 0, dots, N - 1$],
        [→ #h(2pt) *показатели за период*],
      )
    ]
  ],
  caption: [Слои расчёта. Время появляется только в самом верху: геометрия и граф вычисляются для отдельного момента.],
)

#table(
  columns: (auto, 1.35fr, 1fr, 1fr),
  align: (left, left, left, left),
  table.header([Слой], [Вопрос], [Результат], [Компоненты]),
  table.hline(stroke: 0.6pt + ink),
  [*1*], [Где в момент $t$ находится каждый узел и работает ли он], [координаты и флаги работоспособности], [#code("cosmo_a_json") #code("spatial3d")],
  [*2*], [Какие прямые линии связи существуют], [граф $G(t)$ с длинами линий], [#code("spatial3d") #code("spatial_static_adapter")],
  [*3*], [Есть ли сквозной путь, какой он, почему его нет, насколько он устойчив], [маршруты, причины, $kappa$, критичность, метрики], [#code("static_model") #code("dynamic_model")],
  table.hline(stroke: 0.4pt + hair),
)

Три принципа, которые держат модель целостной:

+ *Измерение, правило и сервис разделены.* Угол возвышения является измерением, условие «угол не ниже порога» является правилом линии, существование пути является свойством сервиса. Поэтому «спутник виден», «линия есть» и «связь есть» остаются тремя разными фактами.
+ *Геометрия и граф не знают о времени.* Положения вычисляются по замкнутым формулам для любого $t$, граф анализируется как самостоятельный объект. Сетку отсчётов и агрегирование ведёт только динамическая модель.
+ *Итог выводится из первичных данных.* Для каждого отсчёта хранятся полный снимок и полный анализ графа, поэтому любая сводная величина воспроизводима, а не является кэшированным баллом.

// СЛОЙ 1

#pagebreak(weak: true)
#layer-color.update(c1)

= 3D-модель: где находятся узлы

#layer-card(
  [Слой 1 из 3 · spatial3d, cosmo_a_json],
  [Где в момент $t$ находится каждый узел и какие узлы работают],
  [сценарий cosmo-A-1.0 и момент времени $t$],
  [снимок: координаты всех спутников и пунктов в системе, связанной с Землёй; флаги работоспособности],
)

== Сценарий как набор параметров

JSON проверяется на контракт кейса и раскладывается на две независимые части: спецификацию узлов (идентификаторы, очереди запуска, наземные пункты, интервалы отказов, пределы связи) и описание траектории (высота, наклонение, плоскости, слоты). Модель движения поэтому заменяема: другой источник траекторий, например TLE, не затрагивает остальные слои.

#table(
  columns: (auto, 1fr, auto),
  table.header([Символ], [Смысл], [Источник]),
  table.hline(stroke: 0.6pt + ink),
  [$R$], [радиус сферической Земли, 6371 км], [константа],
  [$mu$], [гравитационный параметр, 398 600,435507 км³/с²], [константа],
  [$T_⊕$], [период вращения Земли, 86 164,09054 с], [константа],
  [$h, space i, space theta_0$], [высота орбит, наклонение, начальный поворот Земли], [`environment`],
  [$e_min, space D$], [порог угла возвышения, предельная дальность ISL], [`environment`],
  [$H, space Delta t, space A^*$], [горизонт, шаг расчёта, целевая доступность], [`environment`],
  [$L$], [этап развёртывания: сколько очередей запущено], [`design.launch_stage`],
  [$Omega_p, space psi_p$], [RAAN и фазирование плоскости $p$], [`design.planes`],
  [$p(s), space sigma_s, space b_s$], [плоскость, начальный слот и очередь запуска спутника $s$], [`design.satellites`],
  [$phi_g, space lambda_g$], [широта и долгота наземного пункта $g$], [`ground_sites`],
  [$F_s, space O_w$], [объединение интервалов отказа спутника и простоя шлюза], [`failures`, `gateway_outages`],
  table.hline(stroke: 0.4pt + hair),
)

Множества узлов: $S$ спутники, $C$ клиенты, $W$ шлюзы. Вход отклоняется до расчёта, если числа не конечны или вне допустимых диапазонов, идентификаторы повторяются или совпадают у спутника и пункта, ссылка на плоскость, спутник или шлюз не разрешается, $H$ не кратно $Delta t$, интервал отказа выходит за $[0, H]$ или имеет нулевую длину, нет ни одного клиента или шлюза. Ошибка возвращается значением с путём к полю, программа не падает.

== Кто участвует в расчёте

#rule[Работоспособность узла][
  $ chi_s (t) <==> b_s <= L and t in.not F_s, quad quad chi_w (t) <==> t in.not O_w, quad quad chi_c (t) = 1 $
]

Интервалы отказов полуоткрыты: начало входит, конец нет, пересекающиеся интервалы объединяются естественно. Этап развёртывания работает как фильтр, а не как процесс запуска: даты и порядок запусков в расчёт не входят. Неработающий спутник продолжает двигаться и отображается на сцене, но исключается из всех линий.

== Движение спутника

#rule[Круговая орбита в инерциальной системе][
  $ r = R + h, quad quad n = sqrt(mu / r^3), quad quad u_s (t) = (sigma_s + psi_(p(s))) pi / 180 + n t $
  $ bold(x)_s^I (t) = r thin cal(R)_z (Omega) thin cal(R)_x (i) vec(cos u, sin u, 0) = r vec(
    cos Omega cos u - sin Omega sin u cos i,
    sin Omega cos u + cos Omega sin u cos i,
    sin u sin i,
  ), quad Omega = Omega_(p(s)), space u = u_s (t) $
]

Точка окружности радиуса $r$ поворачивается на наклонение вокруг оси $x$ и на RAAN вокруг оси $z$. Фазирование сдвигает спутники вдоль орбиты, не поворачивая плоскость. Переход в систему, связанную с Землёй, учитывает её вращение:

#rule[Система, связанная с Землёй][
  $ theta (t) = theta_0 pi / 180 + (2 pi t) / T_⊕, quad quad bold(x)_s^E (t) = cal(R)_z (-theta (t)) thin bold(x)_s^I (t) = vec(
    cos theta thin x^I + sin theta thin y^I,
    -sin theta thin x^I + cos theta thin y^I,
    z^I,
  ) $
]

#insight[Масштаб][Формулы замкнутые: положение в любой момент вычисляется сразу, без интегрирования и без зависимости от предыдущего шага. При $h = 550$ км период $2 pi slash n approx 5730$ с, то есть 95,5 мин и около 15 оборотов в сутки при скорости 7,59 км/с. За один шаг сетки 120 с спутник проходит около 911 км. Это сопоставимо с радиусом зоны видимости пункта (раздел 2.1), поэтому граф заметно меняется от отсчёта к отсчёту.]

== Наземные пункты

#rule[Координаты пункта][
  $ bold(g) = R vec(cos phi_g cos lambda_g, cos phi_g sin lambda_g, sin phi_g) $
]

Пункты неподвижны в системе, связанной с Землёй, и их координаты от $t$ не зависят. Рельеф и сплюснутость Земли не учитываются: так задано условием кейса.

// СЛОЙ 2

#layer-color.update(c2)

= Граф связности: какие линии существуют

#layer-card(
  [Слой 2 из 3 · spatial3d, spatial_static_adapter],
  [Какие прямые линии связи существуют в момент $t$],
  [снимок слоя 1],
  [граф $G(t)$ с длинами рёбер и отдельное отношение геометрической видимости],
)

Формирование графа выполняется в два шага. Сначала для пар узлов измеряется геометрия, затем правило решает, допустима ли линия. Правило не знает о маршрутах: кто может быть транзитным узлом, задаётся только при построении графа запроса (раздел 2.4).

== Наземная линия: конус видимости

#let cone-figure = {
  let W = 8.0cm
  let H = 5.0cm
  let O = (3.5cm, 5.3cm)
  let g = (3.5cm, 2.4cm)
  let tan-e = calc.tan(10deg)
  let left-edge = (0cm, 2.4cm - 3.5cm * tan-e)
  let right-edge = (W, 2.4cm - 4.5cm * tan-e)
  let A = fig-polar(O, 3.9cm, 76deg)
  let B = fig-polar(O, 3.9cm, 51deg)
  box(width: W, height: H, clip: true, {
    place(top + left, polygon(fill: c2.lighten(90%), stroke: none, g, right-edge, (W, 0cm), (0cm, 0cm), left-edge))
    fig-ring(O, 3.9cm, stroke: fig-dash(muted.lighten(20%)))
    fig-ring(O, 2.9cm, stroke: 0.8pt + rgb("#9fb3c8"), fill: rgb("#e6edf5"))
    fig-seg((1.0cm, 2.4cm), (6.0cm, 2.4cm), stroke: (paint: muted, thickness: 0.5pt, dash: "dotted"))
    fig-seg(g, left-edge, stroke: 0.9pt + c2)
    fig-seg(g, right-edge, stroke: 0.9pt + c2)
    fig-arrow(g, (3.5cm, 0.55cm), paint: muted, thickness: 0.6pt)
    fig-arc(g, 1.25cm, 0deg, 10deg, n: 6, stroke: 0.7pt + c2)
    fig-seg(g, A, stroke: 0.6pt + c2.darken(10%))
    fig-seg(g, B, stroke: fig-dash(muted))
    fig-dot(g, fill: ink)
    fig-dot(A, fill: c2)
    fig-dot(B, fill: muted)
    fig-label(g, $bold(g)$, dx: -0.42cm, dy: 0.08cm, width: 0.4cm)
    fig-label((3.5cm, 0.55cm), $bold(n)$, dx: 0.12cm, dy: -0.12cm, width: 0.6cm)
    fig-label((5.25cm, 1.64cm), $e_min$, width: 1cm, fill: c2.darken(10%))
    fig-label(A, [$A$: $e >= e_min$], dx: 0.16cm, dy: -0.36cm, width: 2.4cm)
    fig-label(B, [$B$: $e < e_min$], dx: 0.16cm, dy: -0.05cm, width: 1.9cm)
    fig-label((3.5cm, 3.75cm), [Земля], width: 2cm, align-to: center, fill: muted)
    fig-label((1.05cm, 2.46cm), [горизонт], width: 2cm, fill: muted, size: 7.6pt)
    fig-label((0.2cm, 0.2cm), [видимая область], width: 3cm, fill: c2.darken(10%), size: 7.6pt)
    fig-label((0.15cm, 3.42cm), [орбита], width: 2cm, fill: muted, size: 7.6pt)
  })
}

#rule[Измерение][
  $ bold(d) = bold(s) - bold(g), quad quad rho = norm(bold(d)), quad quad sin e = (bold(d) dot bold(g)) / (rho R) $
]

Угол $e$ вычисляется для каждой пары «пункт, работающий спутник»; при $rho = 0$ он равен $90°$.

#rule[Правило][
  $ "vis"(g, s, t) <==> chi_s (t) and e >= e_min, quad quad "link"(g, s, t) <==> "vis"(g, s, t) and chi_g (t) $
]

#grid(
  columns: (1fr, 8.0cm),
  column-gutter: 16pt,
  align: horizon,
  [
    Направления с $e >= e_min$ образуют конус с вершиной в пункте, осью по местной вертикали $bold(n) = bold(g) slash R$ и полураствором $90° - e_min$. Видимы спутники внутри конуса, равенство порогу тоже считается видимостью.

    Простой шлюза не отменяет видимость, но снимает его линии. Так модель отличает «шлюз выключен» от «шлюз никто не видит».
  ],
  box(width: 8.0cm, figure(cone-figure, caption: [$A$ выше порога и виден, $B$ над горизонтом, но ниже порога. Не в масштабе.])),
)

#insight[Эквивалентные формы][Без арксинуса правило записывается как $(bold(s) - bold(g)) dot bold(n) >= norm(bold(s) - bold(g)) sin e_min$. Для орбит одной высоты угол возвышения убывает с наклонной дальностью, поэтому конус равносилен шару вокруг пункта: $norm(bold(s) - bold(g)) <= L_max = sqrt(r^2 - R^2 cos^2 e_min) - R sin e_min$. В базовых сценариях $L_max approx 1815$ км.]

== Межспутниковая линия: шар дальности и зазор над Землёй

#let isl-figure = {
  let W = 8.0cm
  let H = 5.5cm
  let O = (4.0cm, 3.35cm)
  let A = fig-polar(O, 2.6cm, 125deg)
  let B = fig-polar(O, 2.6cm, 80deg)
  let C = fig-polar(O, 2.6cm, 35deg)
  let mab = fig-mid(A, B)
  let mac = fig-mid(A, C)
  let rim = fig-polar(A, 3.9cm, 240deg)
  box(width: W, height: H, clip: true, {
    fig-ring(A, 3.9cm, stroke: fig-dash(c2.lighten(25%)), fill: c2.lighten(94%))
    fig-ring(O, 2.6cm, stroke: fig-dash(muted.lighten(20%)))
    fig-seg(A, C, stroke: 1pt + bad)
    fig-ring(O, 2.1cm, stroke: 0.8pt + rgb("#9fb3c8"), fill: rgb("#e6edf5"))
    fig-seg(A, rim, stroke: 0.5pt + c2.lighten(20%))
    fig-seg(A, B, stroke: 1.2pt + c2)
    fig-seg(O, mab, stroke: fig-dash(ink, thickness: 0.5pt))
    fig-seg(O, mac, stroke: fig-dash(bad, thickness: 0.6pt))
    fig-dot(O, r: 1.6pt, fill: ink)
    fig-dot(mab, r: 1.7pt, fill: ink)
    fig-dot(mac, r: 1.7pt, fill: bad)
    fig-dot(A, fill: c2)
    fig-dot(B, fill: c2)
    fig-dot(C, fill: bad)
    fig-label(A, $bold(a)$, dx: -0.5cm, dy: -0.22cm, width: 0.5cm)
    fig-label(B, $bold(b)$, dx: 0.14cm, dy: -0.42cm, width: 0.5cm)
    fig-label(C, $bold(c)$, dx: 0.16cm, dy: -0.2cm, width: 0.5cm)
    fig-label((2.3cm, 1.88cm), $delta_(a b) > R$, width: 1.4cm)
    fig-label((4.42cm, 2.15cm), text(fill: bad)[$delta_(a c) < R$], width: 1.5cm)
    fig-label(fig-mid(A, rim), $D$, dx: -0.42cm, dy: -0.1cm, width: 0.4cm, fill: c2.darken(10%))
    fig-label((4.0cm, 4.2cm), [Земля], width: 2cm, align-to: center, fill: muted)
    fig-label((2.75cm, 0.08cm), [шар дальности вокруг $bold(a)$], width: 3.2cm, fill: c2.darken(10%), size: 7.6pt)
  })
}

#rule[Измерение][
  $ bold(d) = bold(b) - bold(a), quad rho_(a b) = norm(bold(d)), quad q^* = op("clip") (-(bold(a) dot bold(d)) / (bold(d) dot bold(d)), 0, 1), quad delta_(a b) = norm(bold(a) + q^* bold(d)) $
]

Здесь $delta_(a b)$ есть расстояние от центра Земли до ближайшей точки отрезка: параметр $q^*$ минимизирует $norm(bold(a) + q bold(d))^2$ на $[0, 1]$, а при совпадении точек $delta_(a b) = norm(bold(a))$.

#rule[Правило][
  $ "isl"(a, b, t) <==> chi_a (t) and chi_b (t) and rho_(a b) < D and delta_(a b) > R $
]

#grid(
  columns: (1fr, 8.0cm),
  column-gutter: 16pt,
  align: horizon,
  [
    Геометрически это два условия: второй спутник лежит внутри открытого шара радиуса $D$ вокруг первого, а соединяющий их отрезок не касается замкнутого шара Земли.

    Обе границы строгие: ровно предельная дальность или касание Земли означают отсутствие линии. Проверяются все пары работающих спутников, принадлежность к одной плоскости значения не имеет.
  ],
  box(width: 8.0cm, figure(isl-figure, caption: [$bold(b)$ в шаре и отрезок выше Земли: линия есть. $bold(c)$ тоже в шаре, но отрезок задевает Землю: линии нет. Не в масштабе.])),
)

#insight[Что ограничивает на самом деле][Если оба спутника на высоте $h$, ближайшая к центру точка лежит в середине отрезка, и $delta_(a b) = sqrt(r^2 - rho_(a b)^2 slash 4)$. Условие зазора равносильно $rho_(a b) < 2 sqrt(r^2 - R^2) approx 5408$ км, поэтому при $D = 3000$ или $2000$ км связывает дальность, а не Земля. Соседи в плоскости из 16 спутников разнесены на $2 r sin(pi slash 16) approx 2700$ км: при $D = 3000$ км они образуют замкнутые кольца, при $D = 2000$ км кольца распадаются, и главной причиной перерывов становится разрыв межспутниковой сети.]

== Граф снимка

#rule[Неориентированный граф линий][
  $ G(t) = (V, E(t), d), quad quad V = S ∪ C ∪ W $
  $ E(t) = {{a, b} : "isl"(a, b, t)} ∪ {{g, s} : g in C ∪ W, space s in S, space "link"(g, s, t)} $
]

Каждое ребро несёт длину линии $d_e$ в километрах, наземное ребро также угол возвышения. Узлы хранят флаг работоспособности $chi$. Отдельно от рёбер сохраняется отношение видимости #box[$"Vis"(t) = {(g, s) : "vis"(g, s, t)}$]: оно нужно, чтобы отличать покрытие от сервиса и диагностировать простой шлюза. Отметка времени на этом шаге отбрасывается, и дальше граф анализируется как самостоятельный объект.

Проверок на снимок: #box[$binom(abs(S_"раб"), 2)$] пар спутников, то есть 1128 при 48 аппаратах, и #box[$abs(C ∪ W) dot abs(S_"раб")$] пар «пункт, спутник».

== Граф запроса клиента

Кейс запрещает использовать наземные пункты как ретрансляторы. Это ограничение не вносится в геометрию: для каждого клиента $c$ из $G(t)$ строится ориентированный граф $G_c$ с ролями узлов.

#table(
  columns: (1.5fr, 1fr, auto, auto),
  table.header([Узел графа $G(t)$], [Роль в $G_c$], [Отдаёт], [Принимает]),
  table.hline(stroke: 0.6pt + ink),
  [клиент $c$, для которого строится запрос], [источник], [да], [нет],
  [работающий спутник], [транзит], [да], [да],
  [работающий шлюз], [цель], [нет], [да],
  [прочие клиенты, неработающие узлы, узлы, исключённые при моделировании отказа], [блок], [нет], [нет],
  table.hline(stroke: 0.4pt + hair),
)

#rule[Дуги графа запроса][
  $ (u -> v) in E_c <==> {u, v} in E(t) and "role"_c (u) in {"источник", "транзит"} and "role"_c (v) in {"транзит", "цель"} $
]

#insight[Следствие][Любой путь в $G_c$ имеет вид $c -> s_1 -> dots -> s_k -> w$ при $k >= 1$ и $w in W$: клиент только отдаёт, шлюз только принимает, транзит возможен лишь через спутники. Рёбер между наземными пунктами нет, поэтому хотя бы один спутник есть на любом пути. Отказ спутника $s$ моделируется одной операцией: узел получает роль «блок», то есть рассматривается граф $G_c - s$.]

// СЛОЙ 3

#layer-color.update(c3)

= Алгоритмы над графом

#layer-card(
  [Слой 3 из 3 · static_model, dynamic_model, variant_comparison],
  [Есть ли сквозной путь, какой он, почему его нет, насколько он устойчив и что это даёт за период],
  [графы $G(t_i)$ на всех отсчётах сетки],
  [маршруты и их характеристики, причины перерывов, связность $kappa$, критичные спутники, доступность и перерывы по клиентам, критичность аппаратов за период],
)

Часть А работает с одним графом и не знает о времени. Часть Б прогоняет часть А на каждом отсчёте и сводит результаты.

#part[Часть А · один снимок]

== Покрытие, сервис и входы

#rule[Три множества для клиента $c$][
  $ "Vis"_c = {s : (c, s) in "Vis"(t)}, quad quad T_c = {w in W : c ~> w "в" G_c} $
  $ I_c = {s : (c -> s) in E_c, space s ~> W "в" G_c} $
]

Покрытие означает $"Vis"_c != emptyset$, сквозная доступность означает $T_c != emptyset$. Множество $I_c$ содержит пригодные спутники входа: видимый спутник, из которого нет пути ни к одному шлюзу, в него не входит. $T_c$ получается одним обходом графа из $c$ за $O(abs(V) + abs(E))$, множество $I_c$ проверкой достижимости шлюза из каждого соседа $c$.

== Причина отсутствия маршрута

Если $T_c = emptyset$, причина определяется проверками в фиксированном порядке:

#rule[Классификация][
  $ "reason"_c = cases(
    "нет видимого спутника" & "если" "Vis"_c = emptyset,
    "шлюз недоступен" & "иначе, если" chi_w = 0 "для всех" w in W,
    "нет контакта со шлюзом" & "иначе, если в" E(t) "нет рёбер к работающим шлюзам",
    "разрыв ISL-сети" & "в остальных случаях",
  ) $
]

Порядок проверок делает ответ однозначным: у каждого отсчёта без маршрута ровно одна причина. Последний случай означает, что и клиент, и шлюз касаются спутниковой сети, но между их частями нет цепочки межспутниковых линий.

== Маршруты

Маршрут оценивается не одним числом, а вектором качества $q(P)$: каждое измерение имеет имя, значение и направление, минимизировать или максимизировать. Векторы сравниваются покомпонентно, по Парето, поэтому два маршрута могут оказаться несравнимыми. Чтобы выбрать один, стратегия задаёт лексикографический порядок своих измерений.

#table(
  columns: (auto, 1fr, auto),
  table.header([Стратегия], [Вектор качества по убыванию приоритета], [Эталонный план]),
  table.hline(stroke: 0.6pt + ink),
  [`minimum_hops`], [$("hop"(P) arrow.b)$], [да, основная],
  [`minimum_distance`], [$("len"(P) arrow.b, space "hop"(P) arrow.b)$], [да],
  [`resilient_distance`], [$("survive"(P) arrow.t, space "backup"(P) arrow.b, space "len"(P) arrow.b, space "hop"(P) arrow.b)$], [нет, раздел 3.5],
  table.hline(stroke: 0.4pt + hair),
)

Здесь $"hop"(P) = abs(E(P))$ есть число переходов, включая обе наземные линии, а $"len"(P) = sum_(e in P) d_e$ есть длина маршрута в километрах.

#rule[Выбор кратчайшего маршрута][
  $ P_tau = op("arg min", limits: #true)_(P : c ~> tau "в" G_c) (W(P), space "hop"(P), space P), quad W(P) = sum_(e in P) w(e), quad w(e) in {1, space d_e}, quad tau in T_c $
  $ P^* = op("arg min", limits: #true)_(tau in T_c) (q(P_tau), space tau, space P_tau) quad "лексикографически" $
]

Путь до каждого достижимого шлюза ищет алгоритм Дейкстры с явным полным порядком: сумма весов, затем число переходов, затем список узлов. Поэтому при равной стоимости результат не зависит от порядка обхода графа и воспроизводим, стоимость $O((abs(V) + abs(E)) log abs(V))$ на шлюз. Вес $w(e) = 1$ даёт минимум переходов, вес $w(e) = d_e$ даёт минимум длины.

Маршрут хранится как последовательность узлов и сегментов (тип линии, длина, угол возвышения наземного сегмента), универсальные показатели $"hop"$ и $"len"$ и вектор качества своей стратегии. Путь основной стратегии выгружается в результат `cosmo-A-result-1.0`: одна запись $(t_i, c, P^*)$ на каждую пару отсчёта и клиента, пустой список при отсутствии пути.

#insight[Свойство][Все стратегии ищут путь в одном и том же $G_c$, поэтому путь находится тогда и только тогда, когда $T_c != emptyset$. Стратегия не меняет доступность связи; она меняет характеристики маршрутов: число переходов, километры и частоту переключений.]

== Устойчивость в момент $t$

Число $kappa_c$ есть наибольшее число путей от $c$ к шлюзам, попарно не имеющих общих спутников. По теореме Менгера оно равно наименьшему числу спутников, отказ которых отрезает клиента от всех работающих шлюзов:

#rule[Спутниковая связность][
  $ kappa_c = max{m : P_1, dots, P_m "попарно без общих спутников"} = min{abs(X) : X subset.eq S, space T_c (G - X) = emptyset} $
]

Вычисление сводится к максимальному потоку. Каждый узел $v$ графа $G_c$ заменяется парой $v_"in" -> v_"out"$, и путь превращается в цепочку

$ c_"out" -> s_"in" limits(->)^1 s_"out" -> s'_"in" limits(->)^1 s'_"out" -> dots -> w_"in" -> w_"out" -> z $

#rule[Расщепление вершин][
  $ "cap"(v_"in" -> v_"out") = cases(1 & "если" v in S, M & "иначе"), quad "cap"(u_"out" -> v_"in") = M, quad "cap"(w_"out" -> z) = M $
  $ kappa_c = "maxflow"(c_"out", z), quad quad X_c = {s : s_"in" "в части источника", space s_"out" "в части стока"} $
]

Единичная ёмкость внутри спутника запрещает двум путям проходить через один аппарат. Число $M$ больше количества спутников в $G_c$, поэтому наземные узлы и дуги потоку не мешают и в минимальный разрез не попадают. Минимальный разрез даёт конкретное множество $X_c$ из $kappa_c$ спутников, отказ которых обрывает связь.

#block(breakable: false)[#grid(
  columns: (1fr, 1fr),
  column-gutter: 14pt,
  align: horizon,
  [
    #rule[Критичные спутники][
      $ "Crit"_c = {s : chi_s = 1, space T_c (G - s) = emptyset} $
      $ "N1"_c <==> T_c != emptyset and "Crit"_c = emptyset $
    ]
  ],
  table(
    columns: (auto, 1fr),
    table.header([$kappa_c$], [Смысл]),
    table.hline(stroke: 0.6pt + ink),
    [$0$], [связи нет],
    [$1$], [есть спутник, отказ которого обрывает связь],
    [$2$], [любой одиночный отказ выдерживается],
    [$k + 1$], [выдерживается отказ любых $k$ спутников],
    table.hline(stroke: 0.4pt + hair),
  ),
)]

Множество $"Crit"_c$ находится прямым перебором: каждый работающий спутник по очереди блокируется. При наличии пути #box[$"N1"_c <==> kappa_c >= 2$], и это следует из теоремы Менгера: одиночной точки отказа нет ровно тогда, когда есть два пути без общих спутников.

== Маршрут с лучшим резервом

Стратегия `resilient_distance` выбирает основной маршрут так, чтобы отказ любого спутника на нём оставлял как можно более короткий обходной путь. Она включается планом `reference_case_with_resilient_routing` и там становится основной. Сначала для каждого работающего спутника вычисляется лучший резерв клиента:

#rule[Резерв и качество пути][
  $ B(s) = cases(min_(tau in T_c) min_(P : c ~> tau "в" G_c - s) "len"(P) & "если" s in.not "Crit"_c, Pi = sum_(e in E(t)) d_e + 1 & "если" s in "Crit"_c) $
  $ "survive"(P) = min_(s in P ∩ S) [s in.not "Crit"_c], quad quad "backup"(P) = max_(s in P ∩ S) B(s) $
]

Штраф $Pi$ больше длины любого пути и обозначает, что резерва нет. Лексикографический минимум по $("survive" arrow.t, "backup" arrow.b, "len" arrow.b, "hop" arrow.b)$ находится точно, без перебора путей:

#rule[Пороговый минимакс][
  + Если существует путь в обход $"Crit"_c$, эти спутники исключаются из графа.
  + Пороги $theta_1 < theta_2 < dots$ есть различные значения $B(s)$ оставшихся спутников.
  + Для $k = 1, 2, dots$ из графа убираются спутники с $B(s) > theta_k$ и ищется кратчайший по длине маршрут. Первый порог, при котором путь нашёлся, даёт ответ.
]

Все пути найденного подграфа имеют $"backup"(P) = theta_k$: путь с меньшим значением нашёлся бы на меньшем пороге. Поэтому минимум длины внутри подграфа и есть лексикографический оптимум. Стоимость на клиента $O(abs(S) dot abs(W) dot (abs(V) + abs(E)) log abs(V))$: по одному поиску резерва на спутник и не больше $abs(S)$ пороговых поисков.

#insight[Что это даёт на практике][Критичный спутник лежит на каждом пути клиента, поэтому $"survive"(P)$ одинаково для всех путей и равно $"N1"_c$: первое измерение пути не различает. При $kappa_c = 1$ у всех путей $"backup"(P) = Pi$, и стратегия выбирает тот же маршрут, что `minimum_distance`. При $kappa_c >= 2$ она минимизирует худший резерв и платит за это длиной основного маршрута.]

== Последствия отказа конкретного спутника

Для каждого работающего спутника $s$ анализ клиента повторяется на $G - s$, и результат сравнивается с исходным. Верхний индекс $-s$ обозначает величину после отказа.

#table(
  columns: (auto, 1fr),
  table.header([Показатель], [Определение]),
  table.hline(stroke: 0.6pt + ink),
  [потеря сервиса], [$T_c != emptyset and T_c^(-s) = emptyset$],
  [потеря покрытия], [$"Vis"_c != emptyset and "Vis"_c^(-s) = emptyset$],
  [потери видимых спутников, входов, шлюзов], [$max(0, abs("Vis"_c) - abs("Vis"_c^(-s)))$, так же для $I_c$ и $T_c$],
  [потеря связности], [$max(0, kappa_c - kappa_c^(-s))$],
  [маршрут каждой стратегии], [потерян; изменён список узлов; качество после отказа по отношению к исходному: лучше, равно или хуже],
  table.hline(stroke: 0.4pt + hair),
)

Спутники ранжируются лексикографически, без взвешенной суммы: число клиентов, потерявших сервис; потерявших покрытие; суммарные потери входов, шлюзов и связности; число потерянных и изменённых маршрутов. Любое место в рейтинге объясняется конкретным вектором потерь. Стоимость: $abs(S_"раб") dot abs(C)$ повторных анализов на снимок.

#part[Часть Б · во времени]

== Сетка и ряды

#rule[Сетка и индикаторы][
  $ t_i = i Delta t, quad i = 0, dots, N - 1, quad N = H slash Delta t $
  $ v_c (i) = ["Vis"_c (t_i) != emptyset], quad quad r_c (i) = [T_c (t_i) != emptyset] $
  $ V_c = 1 / N sum_(i=0)^(N-1) v_c (i), quad quad A_c = 1 / N sum_(i=0)^(N-1) r_c (i), quad quad "цель выполнена" <==> A_c >= A^* $
]

Отсчёт $t_i$ представляет интервал $[t_i, t_i + Delta t)$, правый конец горизонта в сетку не входит: 720 отсчётов за сутки при шаге 120 с. На каждом отсчёте выполняется полный анализ части А, включая $kappa$ и последствия отказов.

Ряд $r_c$ разбивается на максимальные серии одинаковых значений. Серия нулей на отсчётах #box[$j, dots, k - 1$] даёт перерыв #box[$[t_j, t_k)$] длительностью #box[$(k - j) Delta t$]\; серия, дошедшая до конца горизонта, закрывается его границей. Перерывы в начале и в конце периода обрабатываются этим же правилом. Для каждого клиента сохраняются все интервалы, их число, суммарная, средняя и максимальная длительность, а также время, проведённое в каждой из четырёх причин, в долях периода и в долях времени без связи.

== История маршрутов

Маршрут считается тем же, пока совпадает упорядоченный список узлов: длины линий меняются непрерывно, но переключением это не считается.

#rule[Переключение][
  $ "switch"_c (i) <==> P_i^* != bot and P_(i-1)^* != bot and P_i^* != P_(i-1)^* $
]

Здесь $bot$ означает отсутствие маршрута. Перерыв разрывает непрерывность: восстановление после него начинает новый эпизод, но переключением не считается. Для каждой стратегии сохраняются маршрут на каждом отсчёте, эпизоды, переключения и статистика $"hop"$, $"len"$ и каждого измерения вектора качества по отсчётам с маршрутом.

== Устойчивость за период

#rule[Сводка мгновенной устойчивости][
  $ "N1"_c^"доля" = 1 / N sum_i ["N1"_c (t_i)], quad quad "crit"_c (s) = 1 / N sum_i [s in "Crit"_c (t_i)] $
]

Дополнительно по ряду $kappa_c (t_i)$ вычисляются минимум, максимум и среднее. Доля $"crit"_c (s)$ показывает, как долго конкретный спутник является единственной точкой отказа для клиента.

== Критичность спутника за период

Вопрос: что будет с клиентом, если спутник $s$ неисправен весь горизонт. Отказ не меняет геометрию и остальные линии, он только блокирует узел. Поэтому контрфактический ряд собирается из уже посчитанных мгновенных последствий, без повторного расчёта геометрии:

#rule[Контрфактическая доступность][
  $ r_c^(-s) (i) = cases(r_c (i) and not "lost"_c (s, t_i) & "если" chi_s (t_i) = 1, r_c (i) & "иначе"), quad quad "lost"_c (s, t) <==> T_c != emptyset and T_c^(-s) = emptyset $
  $ A_c^(-s) = 1 / N sum_i r_c^(-s) (i), quad quad Delta A_c (s) = A_c - A_c^(-s) >= 0 $
]

Неотрицательность следует из монотонности: блокировка узла не создаёт новых путей, и модель проверяет это при каждом расчёте. По ряду $r_c^(-s)$ заново строятся перерывы, откуда получаются дополнительное время без связи, рост максимального перерыва и изменение числа перерывов; последнее может быть отрицательным, когда перерывы сливаются. Спутник нарушает цель для клиента, если $A_c >= A^*$, а $A_c^(-s) < A^*$. Потери покрытия, входов, шлюзов и связности интегрируются по времени, а история маршрутов перестраивается для оценки роста числа переключений. Для каждой стратегии также считается, на скольких отсчётах качество маршрута после отказа стало лучше, равным, хуже или несравнимым с исходным.

Рейтинг за период тоже лексикографический и следует цели кейса: число клиентов, опустившихся ниже цели; суммарное дополнительное время без связи; наибольшая потеря доступности; наибольший рост максимального перерыва; интегральные потери покрытия, входов, шлюзов и связности; потерянные и изменённые маршруты; рост числа переключений.

#insight[Два разных вопроса об устойчивости][$"N1"_c^"доля"$ отвечает, в какой доле моментов нет ни одного спутника, отказ которого оборвёт связь прямо сейчас. $A_c^(-s)$ отвечает, какой будет доступность, если один конкретный спутник неисправен все сутки. Первая величина может быть низкой при высокой второй: критичный спутник меняется по мере движения группировки.]

== Сравнение вариантов

Сравниваются полные результаты части Б двух и более вариантов относительно выбранного базового. Сетки времени обязаны совпадать, иначе сравнение отклоняется. Для каждой величины сохраняются оба значения и разность $Delta x = x_"вариант" - x_"базовый"$; направление улучшения не нормируется, общий балл не вычисляется. Параметры конфигурации сопоставляются по смысловым путям, например `design.planes[P2].phase_deg`, поэтому перестановка элементов JSON изменением не считается. Сравниваются доступность и покрытие по клиентам, перерывы и их причины, характеристики маршрутов каждой стратегии (средние длина, переходы и значение каждого измерения качества), доля $"N1"$, средняя связность и сдвиги в рейтинге критичности.

// ИТОГИ

#layer-color.update(ink)

= Что получается на данных кейса

Числа получены эталонным расчётом #code("dynamic_model") на четырёх сценариях кейса: сутки с шагом 120 с, полный анализ части А, включая $kappa$ и последствия отказов, на каждом из 720 отсчётов. Жирным выделена доступность, достигающая цели 90%.

#table(
  columns: (2.45cm, 1.05cm, 1.4cm, 1.5cm, 1.7cm, 1fr, 1.7cm, 2.1cm),
  align: (left + horizon, left, right, right, right, left, right, right),
  fill: none,
  table.header(
    [Сценарий], [Пункт], [$V_c$, %], [$A_c$, %], [Перерыв, мин], [Главная причина перерывов], [$"N1"^"доля"$, %], [$min_s A_c^(-s)$, %],
  ),
  table.hline(stroke: 0.6pt + ink),
  table.cell(rowspan: 3, align: horizon)[Полная группировка], [C65], [97,8], [*96,67*], [8], [нет спутника, 67%], [16,5], [94,31],
  [C70], [99,9], [*98,75*], [2], [шлюз без контакта, 89%], [30,6], [96,53],
  [C72], [100,0], [*98,89*], [2], [шлюз без контакта, 100%], [37,2], [96,94],
  table.hline(stroke: 0.4pt + hair),
  table.cell(rowspan: 3, align: horizon)[Первая очередь], [C65], [38,2], [27,22], [572], [нет спутника, 85%], [0,0], [25,14],
  [C70], [48,8], [15,83], [658], [нет спутника, 61%], [0,0], [14,58],
  [C72], [58,5], [12,64], [796], [шлюз без контакта, 52%], [0,0], [10,83],
  table.hline(stroke: 0.4pt + hair),
  table.cell(rowspan: 3, align: horizon)[10 отказов с 6-го часа], [C65], [84,6], [79,31], [24], [нет спутника, 74%], [8,6], [76,11],
  [C70], [90,3], [80,83], [24], [нет спутника, 51%], [20,4], [77,36],
  [C72], [93,1], [82,50], [20], [шлюз без контакта, 51%], [19,7], [78,75],
  table.hline(stroke: 0.4pt + hair),
  table.cell(rowspan: 3, align: horizon)[Дальность ISL 2000 км], [C65], [97,8], [77,50], [94], [разрыв ISL, 85%], [5,7], [75,28],
  [C70], [99,9], [62,22], [178], [разрыв ISL, 97%], [11,1], [60,42],
  [C72], [100,0], [65,14], [4], [разрыв ISL, 97%], [3,2], [62,08],
  table.hline(stroke: 0.4pt + hair),

)

#text(size: 9pt, fill: muted)[$V_c$: доля времени с видимым спутником. $A_c$: доля времени со сквозным путём. $"N1"^"доля"$: доля отсчётов, когда связь переживает отказ любого одного спутника. $min_s A_c^(-s)$: доступность при худшем постоянном отказе одного спутника. Перерыв: наибольший за сутки. Причина указана с долей от времени без связи; «шлюз без контакта» означает, что ни один спутник сети не видит работающий шлюз.]

Что показывают эти числа:

- *Цель 90% для всех пунктов выполняет только полная группировка:* доступность от 96,67 до 98,89%, наибольший перерыв 8 минут.
- *Видимость не гарантирует связь.* При дальности ISL 2000 км пункт C72 видит спутник 100% времени, но сквозной путь у него есть 65,14% времени; 97% перерывов вызваны разрывом ISL-сети, как и предсказывает раздел 2.2.
- *В первой очереди разрывов ISL-сети нет совсем:* 16 спутников одной плоскости при $D = 3000$ км образуют связное кольцо. Узкое место в покрытии: клиент не видит спутник, или ни один спутник не видит шлюз.
- *Мгновенная и суточная устойчивость различаются.* В полной группировке связь C65 переживает отказ любого спутника лишь в 16,5% моментов, но даже постоянный отказ самого вредного для C65 спутника оставляет доступность 94,31%, выше цели. Самый критичный аппарат за период, S44, добавляет суммарно 90 минут перерывов по трём пунктам и ни один пункт не опускает ниже цели.
- *Стратегия меняет маршрут, но не доступность.* Для C72 в полной группировке маршрут минимальной длины в среднем на 7% короче маршрута минимума переходов (4819 км против 5188 км) при том же среднем числе переходов 3,15 и переключается реже: 547 раз за сутки против 599.
- *Резерв стоит длины.* Стратегия `resilient_distance` на тех же данных даёт ту же доступность, но в полной группировке средний маршрут C65 почти вдвое длиннее: 6142 км и 3,43 перехода против 3131 км и 2,29 у `minimum_distance`, переключений 441 против 348.

= Вычисления, проверка и границы

== Стоимость расчёта

#table(
  columns: (auto, 1fr, auto),
  table.header([Шаг], [Алгоритм], [Стоимость на снимок]),
  table.hline(stroke: 0.6pt + ink),
  [положения], [замкнутые формулы], [$O(abs(S) + abs(C) + abs(W))$],
  [линии ISL], [все пары работающих спутников], [$O(abs(S)^2)$],
  [наземные линии], [все пары «пункт, спутник»], [$O((abs(C) + abs(W)) abs(S))$],
  [доступность, входы], [обход графа запроса], [$O(abs(V) + abs(E))$ на клиента],
  [маршрут], [Дейкстра до каждого достижимого шлюза], [$O(abs(W) (abs(V) + abs(E)) log abs(V))$],
  [маршрут с резервом], [поиск резервов и пороговый минимакс], [$O(abs(S) abs(W) (abs(V) + abs(E)) log abs(V))$],
  [$kappa_c$ и разрез], [максимальный поток на расщеплённом графе], [поток на $2 abs(V)$ вершинах],
  [$"Crit"_c$, последствия], [перебор $G - s$], [$abs(S)$ повторных анализов на клиента],
  [период], [всё перечисленное на каждом отсчёте], [$N$ снимков],
  table.hline(stroke: 0.4pt + hair),
)

== Проверка корректности

- Геометрия реализована независимо по формулам «Описания данных» и сверена с эталонным `geometry.py` из материалов кейса: координаты, флаги работоспособности, множества линий, длины и углы совпадают на всех 2880 снимках (4 сценария по 720 отсчётов), расхождение меньше $10^(-8)$ км и $10^(-8)$ градуса.
- Число отсчётов с маршрутом воспроизводит контрольные значения по всем четырём сценариям, например 696, 711 и 712 из 720 для клиентов C65, C70 и C72 полной группировки.
- Некорректный вход и несогласованные данные возвращаются как значения ошибок с путём к полю, а не как исключения.

== Границы модели

- Линия либо есть, либо нет: пропускная способность, очереди, задержка обработки и конкуренция клиентов за общие линии не моделируются.
- Маршрут существует в пределах одного отсчёта: передача с хранением до будущего контакта не рассматривается.
- Отказы задаются расписанием сценария; вероятности отказов и восстановление не моделируются.
- Орбиты круговые, Земля сферическая, возмущения орбит не учитываются.

#heading(numbering: none)[Где это в коде]

#table(
  columns: (auto, auto, 1fr),
  table.header([Раздел], [Компонент], [Реализация]),
  table.hline(stroke: 0.6pt + ink),
  [1.1], [#code("cosmo_a_json")], [`ScenarioDto`, `adapt_scenario`],
  [1.2], [#code("spatial3d")], [`DeploymentAndOutageSatelliteAvailability`, `GatewayOutageGroundAvailability`],
  [1.3, 1.4], [#code("spatial3d")], [`CircularOrbitTrajectory.state_at`, `SphericalGroundGeometry`],
  [2.1], [#code("spatial3d")], [`SphericalGroundObservationModel`, `MinimumElevationVisibility`, `VisibleGroundLink`],
  [2.2], [#code("spatial3d")], [`SegmentInterSatelliteObservationModel`, `RangeAndEarthOcclusionInterSatelliteLink`],
  [2.3], [#code("spatial_static_adapter")], [`SpatialModel.snapshot`, `project_network`, `from_spatial_snapshot`],
  [2.4], [#code("static_model")], [`ClientToGatewayReachability`, `NetworkXGraphAlgorithms`],
  [3.1, 3.2], [#code("static_model")], [`reachable_targets`, `viable_first_hops`, `CaseNoRouteReason`],
  [3.3], [#code("static_model")], [`RoutingStrategy`, `ShortestPathRouting`, `RouteQuality`, `compare_lexicographic`],
  [3.4], [#code("static_model")], [`satellite_connectivity`, `ResilienceState`],
  [3.5], [#code("static_model")], [`ResilientThenDistanceRouting`, `StaticAnalysisPlan.reference_case_with_resilient_routing`],
  [3.6], [#code("static_model")], [`SatelliteFailureImpact`, `RouteFailureDelta`, `LexicographicCriticalityRanking`],
  [3.7, 3.8, 3.9], [#code("dynamic_model")], [`TimeGrid`, `DynamicModel.analyze`, `NodePathRouteIdentity`, `QualityDimensionStatistics`],
  [3.10], [#code("dynamic_model")], [`SatelliteTemporalCriticality`, `LexicographicDynamicCriticalityRanking`],
  [3.11], [#code("variant_comparison")], [`VariantComparator`, `cosmo_a_comparison_adapter`],
  [выгрузка], [#code("result_json")], [`result_document_from_dynamic_analysis`],
  table.hline(stroke: 0.4pt + hair),
)
