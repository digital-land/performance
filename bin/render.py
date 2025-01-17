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

odp_datasets = [
    "article-4-direction",
    "article-4-direction-area",
    "conservation-area",
    "conservation-area-document",
    "listed-building-outline",
    "tree-preservation-order",
    "tree",
    "tree-preservation-zone",
]

rows = {}


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
            "data": "",
            "adoption": "",
            "score": 0,
        },
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
            rows[organisation]["data"] = "ODP"

    # add adoption
    for row in csv.DictReader(open("data/adoption.csv", newline="")):
        organisation = row["organisation"]
        rows[organisation]["adoption"] = row["adoption-status"]

    # add missing columns
    for organisation in rows:
        rows[organisation]["name"] = organisations[organisation]["name"]
        rows[organisation]["entity"] = organisations[organisation]["entity"]
        rows[organisation]["end-date"] = organisations[organisation]["end-date"]

    counts = {
        "lpa": 0,
        "org": 0,
        "proptech": 0,
        "odp": 0,
        "funded": 0,
        "llc": 0,
        "llc-not-odp": 0,
        "llc-and-odp": 0,
        "odp-not-llc": 0,
        "neither-odp-llc": 0,
        "llc-unfunded": 0,
        "providing": 0,
        "data-ready": 0,
        "adopting": 0,
        "adopted": 0,
    }

    for organisation, row in rows.items():
        funded = False
        counts["org"] += 1
        if row["role"] == "local-planning-authority":
            counts["lpa"] += 1

        if "proptech" in row["projects"]:
            counts["proptech"] += 1
            funded = True
        if "open-digital-planning" in row["projects"]:
            counts["odp"] += 1
            funded = True

        if funded:
            counts["funded"] += 1

        if "local-land-charges" in row["projects"]:
            counts["llc"] += 1
            if not funded:
                counts["llc-unfunded"] += 1

            if "open-digital-planning" in row["projects"]:
                counts["llc-and-odp"] += 1
            else:
                counts["llc-not-odp"] += 1
        else:
            if "open-digital-planning" in row["projects"]:
                counts["odp-not-llc"] += 1
            else:
                counts["neither-odp-llc"] += 1

        if row["data"]:
            counts["data-ready"] += 1
        if row["adoption"]:
            if row["adoption"] in ["guidance", "submission"]:
                counts["adopted"] += 1
            else:
                counts["adopting"] += 1

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
                counts["providing"] += 1

        if rows[organisation]["data"]:
            rows[organisation]["score"] += 10000000

        if rows[organisation]["adoption"]:
            rows[organisation]["score"] += (
                100000000
                * {
                    "": 0,
                    "interested": 1,
                    "onboarding": 2,
                    "planning": 2,
                    "guidance": 4,
                    "submission": 5,
                }[row["adoption"]]
            )

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
td.dots {
  valign: center;
  text-align: right;
  font-family: fixed;
}
tr:nth-child(even) {
  background-color: #f2f2f2;
}
.dot a { text-decoration: none }
</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script>google.charts.load('current', {'packages':['corechart','sankey']});</script>
</head>
<body>
"""
    )

    print("<h1>PlanX adoption counts</h1>")

    print(
        """
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_adoption)
      function draw_adoption() {
        var data = google.visualization.arrayToDataTable([
          ['Status', 'Count'],
          ['LPA', """
        + str(counts["lpa"])
        + """],
          ['Funded', """
        + str(counts["funded"])
        + """],
          ['ODP member', """
        + str(counts["odp"])
        + """],
          ['Providing data', """
        + str(counts["providing"])
        + """],
          ['Data ready', """
        + str(counts["data-ready"])
        + """],
          ['Planning to adopt', """
        + str(counts["adopting"])
        + """],
          ['Adopted PlanX', """
        + str(counts["adopted"])
        + """]
        ]);

        var options = {
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

    print("<h1>Adoption pipeline</h1>")
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

    sep = ""
    for organisation, row in rows.items():
        print(f'{sep}["Organisation", "{row["role"]}", 1, "{row["name"]}"]', end="")
        sep = ",\n"

    project = "open-digital-planning"
    for organisation, row in rows.items():
        if project in row["projects"]:
            print(f'{sep}["{row["role"]}", "{project}", 1, "{row["name"]}"]', end="")
            sep = ",\n"

    print(
        """]);
        var options = {};
        var chart = new google.visualization.Sankey(document.getElementById("sankey-chart"));
        chart.draw(data, options);
      }
    </script>
    <div id="sankey-chart" style="width: 1024px; height: 480px;"></div>
    """
    )

    print("<h1>Overlap between projects</h1>")
    print(
        """
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_adoption)
      function draw_adoption() {
        var data = google.visualization.arrayToDataTable([
          ['Project', 
          'Project only', 
          'LLC and project', 
          'LLC only', 
          'Neither'],
          ['ODP', """
        + str(counts["odp-not-llc"])
        + ","
        + str(counts["llc-and-odp"])
        + ","
        + str(counts["llc-not-odp"])
        + ","
        + str(counts["neither-odp-llc"])
        + ","
        + """]
        ]);

        var options = {
          bars: 'horizontal',
          colors: [ "#222", "#707071", "#d5d5d6", "#f5f5f6"],
          isStacked: true,
        };

        var chart = new google.visualization.ColumnChart(document.getElementById("overlap-chart"));
        chart.draw(data, options);

      }
    </script>
    <div id="overlap-chart" style="width: 1024px; height: 480px;"></div>
    """
    )

    print("<h1>Organisations adopting PlanX</h1>")

    print("<table>")
    print("<thead>")
    print(f'<th scope="col" align="left">Organisation</th>')
    print(f'<th scope="col" align="left">Datasets</th>')
    print(f'<th scope="col" align="left">Data ready</th>')
    print(f'<th scope="col" align="left">PlanX adoption</th>')
    print("</thead>")
    print("</tbody>")

    for organisation, row in sorted(rows.items(), key=lambda x: x[1]["score"]):
        if row["adoption"] == "":
            continue

        note = ""
        note = (
            note + ""
            if "local-planning-authority" in organisation_roles[organisation]
            else daggar
        )

        if row.get("end-date", ""):
            if not "interventions" in row:
                print(f"<!-- skipping {organisation} {row['name']} -->")
                continue
            print(
                f"<!-- funded {organisation} {row['name']} ended in {row['end-date']}-->"
            )
            note = note + ddaggar

        print(f"<tr>")
        print(
            f'<td><a href="{entity_url}{row["entity"]}">{escape(row["name"])}</a>{note}</td>'
        )

        # datasets
        dots = ""
        if organisation in quality:
            for dataset in odp_datasets:
                q = quality[organisation][dataset]
                status = {
                    "": "&nbsp;",
                    "0. no data": "&nbsp;",
                    "1. some data": "·",
                    "2. authoritative data from the LPA": "○",
                    "3. data that is good for ODP": "●",
                    "4. data that is trustworthy": "◉",
                }[q]
                dots += f'<a href="{data_url}" title="{dataset} : {q}">{status}</a>'
        print(f'<td class="dot dots">{dots}</td>')

        # data
        dot = f'<a href="{data_url}">●</a>' if row["data"] == "ODP" else ""
        print(f'<td class="dot">{dot}</td>')

        # adoption
        status = {
            "": "",
            "interested": "·",
            "onboarding": "○",
            "planning": "○",
            "guidance": "●",
            "submission": "◉",
        }[row["adoption"]]
        print(f'<td class="adoption">{row["adoption"]}</td>')

        print("</tr>")

    print("</tbody>")
    print("</table>")

    print("<h1>All organisations</h1>")
    print("<table>")
    print("<thead>")
    print(f'<th scope="col" align="left">Organisation</th>')
    print(f'<th scope="col" align="left">Drupal</th>')
    print(f'<th scope="col" align="left">LLC</th>')
    print(f'<th scope="col" align="left">PropTech</th>')
    print(f'<th scope="col" align="left">ODP Membership</th>')
    print(f'<th scope="col" align="left">Datasets</th>')
    print(f'<th scope="col" align="left">Data ready</th>')
    print(f'<th scope="col" align="left">PlanX</th>')
    print("</thead>")
    print("</tbody>")

    for organisation, row in sorted(rows.items(), key=lambda x: x[1]["score"]):
        note = ""
        note = (
            note + ""
            if "local-planning-authority" in organisation_roles[organisation]
            else daggar
        )

        if row.get("end-date", ""):
            if not "interventions" in row:
                print(f"<!-- skipping {organisation} {row['name']} -->")
                continue
            print(
                f"<!-- funded {organisation} {row['name']} ended in {row['end-date']}-->"
            )
            note = note + ddaggar

        print(f"<tr>")
        print(
            f'<td><a href="{entity_url}{row["entity"]}">{escape(row["name"])}</a>{note}</td>'
        )

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
        if organisation in quality:
            for dataset in odp_datasets:
                q = quality[organisation][dataset]
                status = {
                    "": "&nbsp;",
                    "0. no data": "&nbsp;",
                    "1. some data": "·",
                    "2. authoritative data from the LPA": "○",
                    "3. data that is good for ODP": "●",
                    "4. data that is trustworthy": "◉",
                }[q]
                dots += f'<a href="{data_url}" title="{dataset} : {q}">{status}</a>'
        print(f'<td class="dot dots">{dots}</td>')

        # data
        dot = f'<a href="{data_url}">●</a>' if row["data"] == "ODP" else ""
        print(f'<td class="dot">{dot}</td>')

        # adoption
        status = {
            "": "",
            "interested": "·",
            "onboarding": "○",
            "planning": "○",
            "guidance": "●",
            "submission": "◉",
        }[row["adoption"]]
        print(f'<td class="dot"><a href="" title="{row["adoption"]}">{status}</a></td>')

        print("</tr>")

    print("</tbody>")
    print("</table>")
    print("</body>")
