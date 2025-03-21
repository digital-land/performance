#!/usr/bin/env python3

import sys
import re
import csv
from math import pi, sqrt
from html import escape

# see https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-colours-in-charts/
legends = [
    {
        "reference": "Software",
        "name": "Software",
        "colour": "#22d0b6",
        "description": "Funded for Software (software, integration or improvement)",
    },
    {
        "reference": "PropTech_Software",
        "name": "PropTech and Software",
        "colour": "#a8bd3a",
        "description": "Funded for Software and PropTech",
    },
    {
        "reference": "Plan-making_Software",
        "name": "Plan-making and Software",
        "colour": "#118c7b",
        "description": "Funded for Software and Plan-making",
    },
    {
        "reference": "Plan-making_PropTech_Software",
        "name": "Plan-making and Software",
        "colour": "#746cb1",
        "description": "Funded for Software, PropTech and Plan-making",
    },
    {
        "reference": "PropTech",
        "name": "PropTech",
        "colour": "#27a0cc",
        "description": "Funded for PropTech (engagement or innovation)",
    },
    {
        "reference": "Plan-making_PropTech",
        "name": "PropTech and Plan-making",
        "colour": "#206095",
        "description": "Funded for PropTech and Plan-making",
    },
    {
        "reference": "Plan-making",
        "name": "Plan-making",
        "colour": "#eee",
        "description": "Funded for Plan-making",
    },
]

funds = {}
funded_organisation = {}
circles = {}
lpas = {}
counts = {}
total = 311
found = set()


def load(path, key, opt=None):
    d = {}
    for row in csv.DictReader(open(path, newline="")):
        if (not opt) or opt(row):
            d[row[key]] = row
    return d


def add_award(organisation, intervention, amount):
    funded_organisation.setdefault(
        organisation,
        {
            "organisation": organisation,
            "name": organisations[organisation]["name"],
            "interventions": set(),
            "amount": 0,
        },
    )
    funded_organisation[organisation]["amount"] += amount
    funded_organisation[organisation]["interventions"].add(intervention)

    lpa = organisations[organisation].get("local-planning-authority", "")
    if lpa:
        lpas[lpa] = organisation


def circle(row):
    o = organisations[row["organisation"]]
    classes = " ".join(list(row["interventions"]))
    for f in ["local-planning-authority", "local-authority-district", "region"]:
        area = o.get(f, "")
        if area in circles:
            line = circles[area]
            r = sqrt(float(row["amount"]) / pi) / 25
            line = line.replace('r="1"', f'r="{r:.2f}"')
            line = line.replace('class="point"', f'class="{classes}"')
            return line

    print(f"circle for {o}: not found", file=sys.stderr)
    return None


if __name__ == "__main__":
    organisations = load("var/cache/organisation.csv", "organisation")
    interventions = load("specification/intervention.csv", "intervention")
    funds = load("specification/fund.csv", "fund")
    awards = load("specification/award.csv", "award")
    interventions = load("specification/intervention.csv", "intervention")

    # funding awards and interventions
    for award, row in awards.items():
        organisation = row["organisation"]
        intervention = row["intervention"]
        amount = int(row["amount"])

        add_award(organisation, intervention, amount)

        partners = filter(None, row["organisations"].split(";"))
        for partner in partners:
            add_award(partner, intervention, 0)

    for row in legends:
        counts[row["reference"]] = 0

    for organisation, row in funded_organisation.items():
        buckets = set()
        if row["interventions"] & set(["innovation", "engagement"]):
            buckets.add("PropTech")
        if row["interventions"] & set(["software", "integration", "improvement"]):
            buckets.add("Software")
        if row["interventions"] & set(["plan-making"]):
            buckets.add("Plan-making")
        row["class"] = "_".join(sorted(list(buckets)))
        counts[row["class"]] += 1

    print(
        """<!doctype html>
<head>
<meta charset="UTF-8">
<style>
body {
  font-family: sans-serif;
}
table {
  border-spacing: 0;
  border: 1px solid #ddd;
}
table.sortable {
  width: 100%;
}
thead {
  position: sticky;
  top: 1px;
  background: #fff;
}
th, td {
  border: 1px solid #ddd;
}
th.date {
    min-width: 5.5em;
}
td.dot {
  valign: center;
  text-align: center;
  font-family: fixed;
}
th.odp-col {
  text-align: center;
}
td.dots {
  valign: center;
  text-align: right;
  font-family: fixed;
}
tr:nth-child(even) {
  background-color: #f2f2f2;
}
.dot a { text-decoration: none; color: #222; }
.submission { font-weight: bolder }
.guidance { font-weight: bolder }
.interested { color: #888}
.amount { text-align: right }
.number { text-align: right }

.some, .some a { color:	#d4351c; }
.authoritative, .authoritative a { color: #f47738; }
.ready, .ready a { color: #a8bd3a; }
.trustworthy, .trustworthy a { color: #00703c; }

.chart {
  width: 100%;
  max-width: 100%;
  min-height: 450px;
}

.tooltip {
    background:#fff;
    padding:10px;
    border-style:solid;
}

/* sortable table */
th[role=columnheader]:not(.no-sort) {
	cursor: pointer;
}

th[role=columnheader]:not(.no-sort):after {
	content: '';
	float: right;
	margin-top: 7px;
	border-width: 0 4px 4px;
	border-style: solid;
	border-color: #404040 transparent;
	visibility: hidden;
	opacity: 0;
	-ms-user-select: none;
	-webkit-user-select: none;
	-moz-user-select: none;
	user-select: none;
}

th[aria-sort=ascending]:not(.no-sort):after {
	border-bottom: none;
	border-width: 4px 4px 0;
}

th[aria-sort]:not(.no-sort):after {
	visibility: visible;
	opacity: 0.4;
}

th[role=columnheader]:not(.no-sort):hover:after {
	visibility: visible;
	opacity: 1;
}

.shapes svg {
 width: 100%;
 fill: 	#0b0c0c;
}

.map {
 width: 640px;
 resize: both;
}

.points svg {
 width: 100%;
 fill: 	#0b0c0c;
}

.shapes svg path {
  fill:none;
  stroke:#000;
  stroke-width:0.5px;
}

svg path {
  fill:none;
  stroke:#000;
  stroke-width:0.5px;
}

svg circle {
  fill:red;
  opacity: 0.125;
}

.stacked-chart {
  display: flex;
  width: 99%;
  margin: 1em 0;
}

.stacked-chart .bar {
  display: flex;
  justify-content: left;
  align-items: center;
  height: 2em;
  text-indent: 1em;
  color: #ffffff;
}

ul.key {
  list-style-type: none;
  margin: 0;
  padding: 0;
}

li.key-item {
   border-left: 16px solid;
   margin-bottom: 5px;
   padding-left: 5px;
}
    """)

    for item in legends:
        (reference, colour) = (item["reference"], item["colour"])
        print(f".stacked-chart .bar.{reference} {{ background-color: {colour}; color: #000 }}")
        print(f".key-item.{reference} {{ border-color: {colour}; }}")
        print(f"svg path.{reference} {{ fill: {colour}; stroke: #000; stroke-width: 0.5px }}")
    print(f"svg path:hover {{ opacity: 0.5 }}")

    print("""
    </style>
    <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
    <script>google.charts.load('current', {'packages':['corechart','bar','sankey', 'treemap', 'geochart']});</script>
    </head>
    <body>
    """
    )

    print("<h1 id='Funding'>Digital Planning Programme funding</h1>")
    print("<p>Local planining authorities funded by the Digital Planning Programme.</p>")


    print('<div class="shapes map">')
    re_id = re.compile(r"id=\"(?P<lpa>\w+)")

    _class = ""
    lpa = ""
    name = ""

    with open("var/cache/local-planning-authority.svg") as f:
        for line in f.readlines():

            if "<svg" in line:
                line = line.replace("455", "465")
            line = line.replace(' fill-rule="evenodd"', "")
            line = line.replace('class="polygon ', 'class="')

            match = re_id.search(line)
            if match:
                lpa = match.group("lpa")
                if lpa in found:
                    print(f"already found {lpa}", file=sys.stderr)
                if lpa not in lpas:
                    _class = ""
                    lpa = ""
                    name = ""
                else:
                    found.add(lpa)
                    organisation = lpas[lpa]
                    row = funded_organisation[organisation]
                    name = organisations[organisation]["name"]
                    _class = row["class"]

            if 'class="local-planning-authority"' in line:
                line = line.replace("<path", f'<a href="#{lpa}"><path')
                line = line.replace(
                    'class="local-planning-authority"/>',
                    f'class="local-planning-authority {_class}"><title>{name}</title></path></a>',
                )

            print(line, end="")

    notfound = list(set(lpas.keys()) - found)
    if notfound:
        print(f"not found {notfound}", file=sys.stderr)

    print("</div>")

    print('<div class="stacked-chart">')

    for item in legends:
        value = counts[item["reference"]]
        if value:
            percent = 100 * value / total
            print(f'<div class="bar {item["reference"]}" style="width:{percent:.2f}%;">{value}</div>')

    print("""</div>
    <ul class="key">""")

    for item in legends:
        value = counts[item["reference"]]
        if value:
            print(f'<li class="key-item {item["reference"]}">{item["description"]}</li>')

    print("""</ul></div>""")

    print("<h1 id='awards'>Awards</h1>")

    re_id = re.compile(r"id=\"(?P<id>\w+)")

    with open("var/cache/point.svg") as f:
        for line in f.readlines():
            if "<circle" in line:
                match = re_id.search(line)
                if match:
                    area = match.group("id")
                    circles[area] = line

    print('<div class="points map">')
    first = True
    with open("var/cache/point.svg") as f:
        for line in f.readlines():
            if "<circle" in line:
                if first:
                    for organisation, row in funded_organisation.items():
                        print(circle(row))

                    first = False
            else:
                if "<svg" in line:
                    line = line.replace("455", "465")
                print(line, end="")
                if "<svg" in line:
                    print(
                        """
                      <circle cx="10" cy="10" r="7.14" />
                      <text x="30" y="15" class="key">£100k</text>
                      """
                    )

    print("</div>")

    print(
        f"""
        <table id='awards-table' class='sortable'>
        <thead>
            <th scope="col" align="right">#</th>
            <th scope="col" align="left" class="date">Date</th>
            <th scope="col" align="left">Organisation</th>
            <th scope="col" align="left">Fund</th>
            <th scope="col" align="left">Intervention</th>
            <th scope="col" align="right">Amount</th>
            <th scope="col" align="left">Partners</th>
            <th scope="col" align="left">Notes</th>
        </thead>
        <tbody>
    """
    )

    for award, row in awards.items():
        print(f"<tr>")
        print(f"<td>{award}</td>")
        print(f'<td>{row["start-date"]}</td>')
        print(
            f'<td><a href="https://www.planning.data.gov.uk/curie/{row["organisation"]}">{escape(organisations[row["organisation"]]["name"])}</a></td>'
        )
        print(f'<td>{funds[row["fund"]]["name"]}</td>')
        print(f'<td>{interventions[row["intervention"]]["name"]}</td>')
        n = int(row["amount"])
        amount = f"£{n:,}" if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')
        print(f"<td>")
        sep = ""
        for organisation in [o for o in row["organisations"].split(";") if o]:
            print(
                f'{sep}<a href="https://www.planning.data.gov.uk/curie/{row["organisation"]}">{organisations[organisation]["name"]}</a>',
                end="",
            )
            sep = ", "
        print(f"</td>")
        print(f'<td class="notes">{row["notes"]}</td>')

    print("</tbody>")
    print("</table>")

    print(
        """
        <h1>Data sources</h1>
        <ul>
          <li><a href="https://www.planning.data.gov.uk/organisation/">Organisations</a> (<a href="https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv">CSV</a>)
          <li>Funding awards (<a href="https://github.com/digital-land/specification/blob/main/content/award.csv">CSV</a>)
        </ul>
    """
    )

    print(
        """
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js" integrity="sha512-F/gIMdDfda6OD2rnzt/Iyp2V9JLHlFQ+EUyixDg9+rkwjqgW1snpkpx7FD5FV1+gG2fmFj7I3r6ReQDUidHelA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js" integrity="sha512-dRD755QRxlybm0h3LXXIGrFcjNakuxW3reZqnPtUkMv6YsSWoJf+slPjY5v4lZvx2ss+wBZQFegepmA7a2W9eA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
new Tablesort(document.getElementById('sortable'), { descending: true });
new Tablesort(document.getElementById('awards-table'));
</script>
"""
    )
    print("</body>")
