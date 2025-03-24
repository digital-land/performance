#!/usr/bin/env python3

import csv
from html import escape

funded_organisation = {}
sets = {"lpa": set(), "ended": set()}


def load(path, key, opt=None):
    d = {}
    for row in csv.DictReader(open(path, newline="")):
        if (not opt) or opt(row):
            d[row[key]] = row
    return d


def add_award(organisation, start_date, intervention, amount, partners):
    funded_organisation.setdefault(
        organisation,
        {
            "start-date": start_date,
            "end-date": start_date,
            "interventions": set(),
            "amount": 0,
            "organisations": set(),
        },
    )
    funded_organisation[organisation]["interventions"].add(intervention)
    funded_organisation[organisation]["end-date"] = organisations[organisation]["end-date"]
    funded_organisation[organisation]["organisations"].update(partners)

    if start_date < funded_organisation[organisation]["start-date"]:
        funded_organisation[organisation]["start-date"] = start_date

    funded_organisation[organisation]["amount"] += amount
    sets[intervention].add(organisation)

    if organisations[organisation].get("end-date"):
        sets["ended"].add(organisation)
    
    if organisations[organisation].get("local-planning-authority", ""):
        sets["lpa"].add(organisation)


if __name__ == "__main__":
    organisations = load("var/cache/organisation.csv", "organisation")
    interventions = load("specification/intervention.csv", "intervention")
    awards = load("specification/award.csv", "award")

    for intervention in interventions:
        sets.setdefault(intervention, set())

    # funding awards and interventions
    for award, row in awards.items():
        organisation = row["organisation"]
        start_date = row["start-date"]
        intervention = row["intervention"]
        amount = int(row["amount"])

        if intervention in ["plan-making"] and start_date < "2021-06-01":
            continue

        partners = set(filter(None, row["organisations"].split(";")))

        add_award(organisation, start_date, intervention, amount, partners)

        for partner in partners:
            add_award(partner, start_date, intervention, 0, partners - set(partner) & set(organisation))

    for organisation, row in funded_organisation.items():
        for partner in row["organisations"]:
            funded_organisation[partner]["organisations"].add(organisation)



    print("""<!doctype html>
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
 padding: 2.5em;
}

#membership-map {
 width: 640px;
 resize: both;
 padding: 2.5em;
}

.map {
 width: 640px;
 resize: both;
}

.points svg {
 width: 100%;
 fill: 	#0b0c0c;
 padding: 2.5em;
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
</style>
    """)

    print("""
    </head>
    <body>
    """
    )

    print("<h1 id='Funding'>Open Digital Planning</h1>")

    print("<p>Open Digital Planning community members.</p>")

    print(
        """
        <table id='awards-table' class='sortable'>
        <thead>
            <th scope="col" align="left" class="date">Date</th>
            <th scope="col" align="left">LPA</th>
            <th scope="col" align="left">Organisation</th>
            <th scope="col" align="left">Partners</th>
            <th scope="col" align="left">Interventions</th>
            <th scope="col" align="right">Amount</th>
            <th scope="col" align="left" class="date">End date</th>
        </thead>
        <tbody>
    """)

    for organisation, row in funded_organisation.items():
        print(f"<tr>")
        print(f'<td>{row["start-date"]}</td>')
        dot = "●" if organisation in sets["lpa"] else ""
        print(f'<td class="dot">{dot}</td>')
        print(
            f'<td><a href="https://www.planning.data.gov.uk/curie/{organisation}">{escape(organisations[organisation]["name"])}</a></td>'
        )
        print('<td>')
        sep = ""
        for organisation in row["organisations"]:
            print(f'{sep}<a href="https://www.planning.data.gov.uk/curie/{organisation}">{organisations[organisation]["name"]}</a>', end="")
            sep = ", "
        print(f'</td>')
        print(f'<td>{", ".join([interventions[intervention]["name"] for intervention in row["interventions"]])}</td>')
        n = int(row["amount"])
        amount = f"£{n:,}" if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')
        print(f'<td>{row["end-date"]}</td>')

    print("</tbody>")
    print("</table>")
    print("<h1>Counts</h1>")

    print(f"""
          <ul>
          <li>{len(funded_organisation)} ODP members</p>
          <li>{len(sets["lpa"])} LPAs</p>
          <li>{len(sets["engagement"])} Funded for engagement</p>
          <li>{len(sets["innovation"])} Funded for innovation</p>
          <li>{len(sets["software"])} Funded for product</p>
          <li>{len(sets["integration"])} Funded for integration</p>
          <li>{len(sets["improvement"])} Funded for improvement</p>
          </ul>
          """)

    print(
        """
        <h1>Data sources</h1>
        <ul>
          <li><a href="https://www.planning.data.gov.uk/organisation/">Organisations</a> (<a href="https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv">CSV</a>)
          <li>Funding awards (<a href="https://github.com/digital-land/specification/blob/main/content/award.csv">CSV</a>)
          <li><a href="https://github.com/digital-land/performance/">Open source code</a></li>
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
