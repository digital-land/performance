#!/usr/bin/env python3

import sys
import re
import csv
from math import pi, sqrt
from html import escape


csv.field_size_limit(sys.maxsize)

entity_url = "https://www.planning.data.gov.uk/entity/"
llc_url = "https://www.gov.uk/government/publications/hm-land-registry-local-land-charges-programme/local-land-charges-programme"
odp_url = "https://opendigitalplanning.org/community-members"
drupal_url = "https://localgovdrupal.org/community/our-councils"
proptech_url = "https://www.localdigital.gov.uk/digital-planning/case-studies/"
data_url = ""

funds = {}
funded_organisation = {}
circles = {}
lpas = {}


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
            r = sqrt(float(row["amount"])/pi)/25
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

    # funding awards and interventions
    for award, row in awards.items():
        organisation = row["organisation"]
        intervention = row["intervention"]
        amount = int(row["amount"])

        add_award(organisation, intervention, amount)

        partners = filter(None, row["organisations"].split(";"))
        for partner in partners:
            add_award(partner, intervention, 0)


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

.shapes {
 width: 800px;
 resize: both;
}

.shapes svg {
 width: 100%;
 fill: 	#0b0c0c;
}

.points {
 width: 800px;
 resize: both;
}

.points svg {
 width: 100%;
 fill: 	#0b0c0c;
}

.shapes svg path {
  fill:none;
  stroke:#000;
  stroke-width:1px;
}

svg path {
  fill:none;
  stroke:#000;
  stroke-width:1px;
}

svg circle {
  fill:red;
  opacity: 0.25;
}

svg path.software, svg path.improvement, svg path.integration { fill: #F46A25;}

</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script>google.charts.load('current', {'packages':['corechart','bar','sankey', 'treemap', 'geochart']});</script>
</head>
<body>
"""
    )

    print("<h1 id='Funding'>Digital Planning Funding</h1>")

    #
    #  point map ..
    #
    re_id = re.compile(r"id=\"(?P<id>\w+)")

    with open("var/cache/point.svg") as f:
        for line in f.readlines():
            if "<circle" in line:
                match = re_id.search(line)
                if match:
                    area = match.group("id")
                    circles[area] = line

    print('<div class="points">')
    first = True
    with open("var/cache/point.svg") as f:
        for line in f.readlines():
            if "<circle" in line:
                if first:
                    for organisation, row in funded_organisation.items():
                        print(circle(row))

                    first = False
            else:
                print(line, end="")
                #if "<svg" in line:
                    #print('<text x="0" y="35" class="small">Funding in £k</text>')
                

    print('</div>')


    print('<div class="shapes">')
    re_id = re.compile(r"id=\"(?P<lpa>\w+)")

    with open("var/cache/local-planning-authority.svg") as f:
        for line in f.readlines():

            line = line.replace(' fill-rule="evenodd"', '')
            line = line.replace('class="polygon ', 'class="')

            _class = ""
            lpa = ""
            match = re_id.search(line)
            if match:
                lpa = match.group("lpa")
                if lpa in lpas:
                    organisation = lpas[lpa]
                    row = funded_organisation[organisation]
                    name = organisations[organisation]["name"]
                    _class = " ".join(list(row["interventions"]))

            if 'class="local-planning-authority"' in line:
                line = line.replace('<path', f'<a href="#{lpa}"><path')
                line = line.replace('class="local-planning-authority"/>', f'class="local-planning-authority {_class}"><title>{name}</title></path></a>')

            print(line, end="")

    print('</div>')

    print("<h1 id='awards'>Awards</h1>")
    print(f"""
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
    """)

    for award, row in awards.items():
        print(f"<tr>")
        print(f'<td>{award}</td>')
        print(f'<td>{row["start-date"]}</td>')
        print(f'<td><a href="https://www.planning.data.gov.uk/curie/{row["organisation"]}">{escape(organisations[row["organisation"]]["name"])}</a></td>')
        print(f'<td>{funds[row["fund"]]["name"]}</td>')
        print(f'<td>{interventions[row["intervention"]]["name"]}</td>')
        n = int(row["amount"])
        amount = f'£{n:,}' if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')
        print(f'<td>')
        sep = ""
        for organisation in [o for o in row["organisations"].split(";") if o]:
            print(f'{sep}<a href="https://www.planning.data.gov.uk/curie/{row["organisation"]}">{organisations[organisation]["name"]}</a>', end="")
            sep = ", "
        print(f'</td>')
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

    print("""
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js" integrity="sha512-F/gIMdDfda6OD2rnzt/Iyp2V9JLHlFQ+EUyixDg9+rkwjqgW1snpkpx7FD5FV1+gG2fmFj7I3r6ReQDUidHelA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js" integrity="sha512-dRD755QRxlybm0h3LXXIGrFcjNakuxW3reZqnPtUkMv6YsSWoJf+slPjY5v4lZvx2ss+wBZQFegepmA7a2W9eA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
new Tablesort(document.getElementById('sortable'), { descending: true });
new Tablesort(document.getElementById('awards-table'));
</script>
""")
    print("</body>")
