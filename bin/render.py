#!/usr/bin/env python3

import sys
import csv
from html import escape


entity_url = "https://www.planning.data.gov.uk/entity/"
llc_url = "https://www.gov.uk/government/publications/hm-land-registry-local-land-charges-programme/local-land-charges-programme"
odp_url = "https://opendigitalplanning.org/community-members"
drupal_url = "https://localgovdrupal.org/community/our-councils"
proptech_url = "https://www.localdigital.gov.uk/digital-planning/case-studies/"
data_url = ""
circles = "·○◉●"
daggar = "†"
ddaggar = "‡"
bullet = "●"

odp_cols = {
    "CA": [
        "conservation-area",
        "conservation-area-document",
    ],
    "A4": [
        "article-4-direction",
        "article-4-direction-area",
        ], 
    "LBO": [
        "listed-building-outline",
    ],
    "TPO": [
        "tree-preservation-order",
        "tree",
        "tree-preservation-zone",
    ]
}
odp_datasets = {}
for col, datasets in odp_cols.items():
    for dataset in datasets:
        odp_datasets[dataset] = col

rows = {}
sets = {}


def load(path, key, opt=None):
    d = {}
    for row in csv.DictReader(open(path, newline="")):
        if (not opt) or opt(row):
            d[row[key]] = row
    return d


def add_organisation(organisation, role):
    rows.setdefault(
        organisation,
        {
            "organisation": organisation,
            "role": role,
            "projects": set(),
            "interventions": {},
            "score": 0,
            "adoption": "",
        },
    )


def set_add(name, organisation):
    sets.setdefault(name, set())
    sets[name].add(organisation)


def overlaps(one, two):
    return (
        str(len(sets[one] - sets[two]))
        + "," + str(len(sets[two] & sets[one]))
        + "," + str(len(sets[two] - sets[one]))
        #+ "," + str(len(sets["organisation"] - sets[one] - sets[two]))
    )


if __name__ == "__main__":
    organisations = load("var/cache/organisation.csv", "organisation")
    interventions = load("specification/intervention.csv", "intervention")
    cohorts = load("specification/cohort.csv", "cohort")
    awards = load("specification/award.csv", "award")
    quality = load("data/quality.csv", "organisation")

    organisation_roles = {}
    for row in csv.DictReader(open("specification/role-organisation.csv", newline="")):
        organisation = row["organisation"]
        organisation_roles.setdefault(organisation, [])
        organisation_roles[organisation].append(row["role"])

    # add LPAs
    for organisation, roles in organisation_roles.items():
        if (
            "local-planning-authority" in roles
            and not organisations[organisation]["end-date"]
        ):
            o = organisations[organisation]
            add_organisation(organisation, role="local-planning-authority")

    # load projects
    for row in csv.DictReader(
        open("specification/project-organisation.csv", newline="")
    ):
        organisation = row["organisation"]
        if organisation not in rows:
            if "local-planning-authority" in organisation_roles.get(organisation, []):
                role = "local-planning-authority"
            else:
                role = "other"
            add_organisation(organisation, role="other")

        rows[organisation]["projects"].add(row["project"])
        rows[organisation]["score"] = rows[organisation]["score"] + 1

        # create intervention for awards ..
        if row["cohort"]:
            intervention = cohorts[row["cohort"]]["intervention"]
            rows[organisation]["interventions"][intervention] = {}

    """
    # add awards to interventions
    for award, row in awards.items():
        organisation = row["organisation"]

        partners = filter(None, row["organisations"].split(";"))
        for organisation in partners:

        rows[organisation]["Funding"] = "Partner"
        # add award under intervention column
        col = intervention_cols[row["intervention"]]
        table[organisation].setdefault(col, 0)
        table[organisation][col] += int(row["amount"])
    """

    # add data quality
    for organisation, row in quality.items():
        if row["ready_for_ODP_adoption"] == "yes":
            set_add("data-ready", organisation)

    # add adoption
    for row in csv.DictReader(open("data/adoption.csv", newline="")):
        organisation = row["organisation"]
        set_add(row["adoption-status"], organisation)
        rows[organisation]["adoption"] = row["adoption-status"]

    # add missing columns
    for organisation in rows:
        rows[organisation]["name"] = organisations[organisation]["name"]
        rows[organisation]["entity"] = organisations[organisation]["entity"]
        rows[organisation]["end-date"] = organisations[organisation]["end-date"]

    # create sets of organisations
    for organisation, row in rows.items():
        set_add("organisation", organisation)
        set_add(row["role"], organisation)
        for project in row["projects"]:
            set_add(project, organisation)

        # TBD: funded includes partners?
        if "proptech" in row["projects"] or "open-digital-planning" in row["projects"]:
            set_add("funded", organisation)

    # score rows
    for organisation, row in rows.items():
        if "proptech" in row["projects"]:
            rows[organisation]["score"] += 10

        if "open-digital-planning" in row["projects"]:
            rows[organisation]["score"] += 100

        if organisation in quality:
            n = 0
            for dataset in odp_datasets:
                try:
                    n += int(quality[organisation][dataset][0])
                except:
                    continue
            rows[organisation]["score"] += n * 1000
            if n > 2:
                set_add("providing", organisation)

        if organisation in sets["data-ready"]:
            rows[organisation]["score"] += 10000000

        if organisation in sets["interested"]:
            rows[organisation]["score"] += 100000000
        if organisation in sets["adopting"]:
            rows[organisation]["score"] += 200000000
        if organisation in sets["guidance"]:
            rows[organisation]["score"] += 300000000
        if organisation in sets["submission"]:
            rows[organisation]["score"] += 400000000

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
thead {
  position: sticky;
  top: 1px;
  background: #fff;
}
th, td {
  text-align: left;
  border: 1px solid #ddd;
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
.dot a { text-decoration: none }
.submission { font-weight: bolder }
.guidance { font-weight: bolder }
.interested { color: #888}
</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script>google.charts.load('current', {'packages':['corechart','bar','sankey']});</script>
</head>
<body>
"""
    )

    print("<h1>Organisations adopting PlanX</h1>")

    print(
        """
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_adoption)
      function draw_adoption() {
        var data = google.visualization.arrayToDataTable([
          ['Status', 'Count'],
          ['LPA', """
        + str(len(sets["local-planning-authority"]))
        + """],
          ['Funded', """
        + str(len(sets["funded"]))
        + """],
          ['Software funding', """
        + str(len(sets["open-digital-planning"]))
        + """],
          ['Providing data', """
        + str(len(sets["providing"]))
        + """],
          ['Data ready', """
        + str(len(sets["data-ready"]))
        + """],
          ['Interested in PlanX', """
        + str(len(sets["interested"]))
        + """],
          ['Adopting', """
        + str(len(sets["adopting"]))
        + """],
          ['Adopted PlanX', """
        + str(len(sets["guidance"] | sets["submission"]))
        + """]
        ]);

        var options = {
          title: "Number of organisations",
          bars: 'vertical',
          colors: ['#27a0cc', '#206095', '#003c57', '#871a5b', '#a8bd3a', '#f66068'],
          legend: { position: "none" },
        };

        var view = new google.visualization.DataView(data);
        view.setColumns([0, 
                       { calc: "stringify",
                         sourceColumn: 1,
                         type: "string",
                         role: "annotation" },
                       1]);
        var chart = new google.visualization.ColumnChart(document.getElementById("adoption-chart"));
        chart.draw(view, options);

      }
    </script>
    <div id="adoption-chart" style="width: 1024px; height: 480px;"></div>
    """
    )

    print("<h1>Data and PlanX adoption</h1>")
    print(
        """
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_sankey)
      function draw_sankey() {
        var data = new google.visualization.DataTable();
        data.addColumn('string', 'From');
        data.addColumn('string', 'To');
        data.addColumn('number', 'Count');
        data.addColumn({type: 'string', role: 'tooltip'});
        data.addRows([
        """
    )

    project = "open-digital-planning"

    sep = ""
    """
    for organisation, row in rows.items():
        if row["funded"]:
            print(f'{sep}["Funded organisation", "{row["role"]}", 1, "{row["name"]}"]', end="")
            sep = ",\n"

    for organisation, row in rows.items():
        if project in row["projects"]:
            print(f'{sep}["{row["role"]}", "ODP member", 1, "{row["name"]}"]', end="")
            sep = ",\n"

    for organisation, row in rows.items():
        source = "ODP member" if project in row["projects"] else "Funded" if row["funded"] else row["role"]
        if organisation in sets("providing"):
            print(f'{sep}["{source}", "Providing data", 1, "{row["name"]}"]', end="")
            sep = ",\n"

    for organisation, row in rows.items():
        if row["data-ready"] == "ODP":
            print(f'{sep}["Providing data", "Data ready for PlanX", 1, "{row["name"]}"]', end="")
            sep = ",\n"
    """

    for organisation, row in rows.items():
        if organisation in sets["providing"]:
            print(
                f'{sep}["Providing data", "Data ready for PlanX", 1, "{row["name"]}"]',
                end="",
            )
            sep = ",\n"

    for organisation, row in rows.items():
        dest = {
            "": "",
            "interested": "Interested in adopting PlanX",
            "adopting": "Adopting PlanX",
            "guidance": "Have adopted PlanX",
            "submission": "Have adopted PlanX",
        }[row["adoption"]]

        if dest:
            source = (
                "Data ready for PlanX"
                if organisation in sets["data-ready"]
                else "Providing data"
            )
            print(f'{sep}["{source}", "{dest}", 1, "{row["name"]}"]', end="")

    print(
        """]);
        options = {
            sankey: {
                link: { color: { fill: '#d5d5d6' } },
                node: { colors: [ '#222' ],
                label: { color: '#222' } },
            }
        };
        var chart = new google.visualization.Sankey(document.getElementById("sankey-chart"));
        chart.draw(data, options);
      }
    </script>
    <div id="sankey-chart" style="width: 1024px; height: 480px;"></div>
    """
    )

    print("<h1>Overlaps between projects</h1>")
    print(
        """
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_overlap)
      function draw_overlap() {
        var data = google.visualization.arrayToDataTable([
          ['Project', 
          'First only', 
          'Both projects', 
          'Second only'],
          ['ODP and LPA', """ + overlaps("local-planning-authority", "open-digital-planning") + """],
          ['PropTech and LPA', """ + overlaps("local-planning-authority", "proptech") + """],
          ['LCC and LPA', """ + overlaps("local-planning-authority", "local-land-charges")+ """],
          ['Drupal and LPA', """ + overlaps("local-planning-authority", "localgov-drupal") + """],
          ['ODP and PropTech', """ + overlaps("open-digital-planning", "proptech") + """],
          ['ODP and LLC', """ + overlaps("open-digital-planning", "local-land-charges") + """],
          ['ODP and Drupal', """ + overlaps("open-digital-planning", "localgov-drupal") + """],
          ['PropTech and LLC', """ + overlaps("proptech", "local-land-charges") + """],
          ['PropTech and Drupal', """ + overlaps("proptech", "localgov-drupal") + """],
          ['Drupal and LLC', """ + overlaps("localgov-drupal", "local-land-charges") + """],
        ]);

        var options = {
          title: "Number of organisations",
          bars: 'horizontal',
          colors: [ "#222", "#707071", "#d5d5d6", "#f5f5f6"],
          isStacked: true,
        };

        var chart = new google.visualization.BarChart(document.getElementById("overlap-chart"));
        chart.draw(data, options);

      }
    </script>
    <div id="overlap-chart" style="width: 1024; height: 480px;"></div>
    """
    )

    print("<h1>LPAs and other funded organisations</h1>")
    print("<table>")
    print("<thead>")
    print(f'<th scope="col" align="left">Organisation</th>')
    print(f'<th scope="col" align="left">Ended</th>')
    print(f'<th scope="col" align="left">LPA</th>')
    print(f'<th scope="col" align="left">Drupal</th>')
    print(f'<th scope="col" align="left">LLC</th>')
    print(f'<th scope="col" align="left">PropTech</th>')
    print(f'<th scope="col" align="left">ODP</th>')

    for col, datasets in odp_cols.items():
        colspan = len(datasets)
        print(f'<th class="odp-col" scope="col" align="left" colspan={colspan}>{col}</th>')

    print(f'<th scope="col" align="left">Data ready</th>')
    print(f'<th scope="col" align="left">PlanX</th>')
    print("</thead>")
    print("</tbody>")

    for organisation, row in sorted(
        rows.items(), key=lambda x: x[1]["score"], reverse=True
    ):
        if not "interventions" in row:
            print(f"<!-- skipping {organisation} {row['name']} -->")
            continue

        print(f"<tr>")
        print(f'<td><a href="{entity_url}{row["entity"]}">{escape(row["name"])}</a></td>')
        print(f'<td>{row.get("end-date", "")}</td>')

        # roles
        dot = (
            '●' if organisation in sets["local-planning-authority"] else ""
        )
        print(f'<td class="dot">{dot}</td>')

        # projects
        dot = (
            f'<a href="{drupal_url}">●</a>'
            if "localgov-drupal" in row["projects"]
            else ""
        )
        print(f'<td class="dot">{dot}</td>')

        dot = (
            f'<a href="{llc_url}">●</a>'
            if "local-land-charges" in row["projects"]
            else ""
        )
        print(f'<td class="dot">{dot}</td>')

        dot = f'<a href="{proptech_url}">●</a>' if "proptech" in row["projects"] else ""
        print(f'<td class="dot">{dot}</td>')

        dot = (
            f'<a href="{odp_url}">●</a>'
            if "open-digital-planning" in row["projects"]
            else ""
        )
        print(f'<td class="dot">{dot}</td>')

        # datasets
        dots = ""
        for col, datasets in odp_cols.items():
            for dataset in datasets:
                q = quality.get(organisation, {}).get(dataset, "")
                status = {
                    "": "&nbsp;",
                    "0. no data": "&nbsp;",
                    "1. some data": "·",
                    "2. authoritative data from the LPA": "○",
                    "3. data that is good for ODP": "●",
                    "4. data that is trustworthy": "◉",
                }[q]
                print(f'<td class="dot"><a href="{data_url}" title="{dataset} : {q}">{status}</a></td>')

        # data
        dot = f'<a href="{data_url}">●</a>' if organisation in sets["data-ready"] else ""
        print(f'<td class="dot">{dot}</td>')

        # adoption
        print(f'<td class="{row["adoption"]}">{row["adoption"]}</td>')

        print("</tr>")

    print("</tbody>")
    print("</table>")
    print("""
        <h1>Data sources</h1>
    """)


    print("</body>")
