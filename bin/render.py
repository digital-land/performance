#!/usr/bin/env python3

import sys
import csv
from html import escape


csv.field_size_limit(sys.maxsize)

entity_url = "https://www.planning.data.gov.uk/entity/"
llc_url = "https://www.gov.uk/government/publications/hm-land-registry-local-land-charges-programme/local-land-charges-programme"
odp_url = "https://opendigitalplanning.org/community-members"
drupal_url = "https://localgovdrupal.org/community/our-councils"
proptech_url = "https://www.localdigital.gov.uk/digital-planning/case-studies/"
data_url = ""

# TBD make dataset
quality_status = ["none","some","authoritative","ready","trustworthy"]

quality_lookup = {
    "": "",
    "0. no data": "none",
    "1. some data": "some",
    "2. authoritative data from the LPA": "authoritative",
    "3. data that is good for ODP": "ready",
    "4. data that is trustworthy": "trustworthy",
}

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
    ],
}
odp_datasets = {}
for col, datasets in odp_cols.items():
    for dataset in datasets:
        odp_datasets[dataset] = col

rows = {}
sets = {}
area_names = {}


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
        + ","
        + str(len(sets[two] & sets[one]))
        + ","
        + str(len(sets[two] - sets[one]))
        # + "," + str(len(sets["organisation"] - sets[one] - sets[two]))
    )


if __name__ == "__main__":
    organisations = load("var/cache/organisation.csv", "organisation")
    interventions = load("specification/intervention.csv", "intervention")
    awards = load("specification/award.csv", "award")
    quality = load("data/quality.csv", "organisation")
    lpas = load("var/cache/local-planning-authority.csv", "reference")

    # area names
    for organisation, row in organisations.items():
        lpa = row.get("local-planning-authority", "")
        if lpa:
            row['area-name'] = lpas.get(lpa, row)["name"].replace(" LPA", "")
        else:
            row['area-name'] = row["name"]
        area_names[row['area-name']] = organisation

    # fixup quality status
    for organisation, row in quality.items():
        for dataset in odp_datasets:
            row[dataset] = quality_lookup[row.get(dataset, "")]

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

    # funding awards and interventions
    for award, row in awards.items():
        organisation = row["organisation"]
        intervention = row["intervention"]
        partners = filter(None, row["organisations"].split(";"))

        set_add(intervention, organisation)

        if intervention in ["software", "integration", "improvement"]:
            bucket = "Software"
        elif intervention in ["engagement", "innovation"]:
            bucket = "PropTech"
        elif intervention in ["plan-making"]:
            # skipping local plan pathfinders for now ..
            continue
        else:
            raise ValueError(f"unknown intervention: {intervention}")

        set_add(intervention, organisation)
        set_add(bucket, organisation)
        set_add("funded", organisation)

        o = organisations[organisation]
        o.setdefault(intervention, 0)
        o[intervention] += int(row["amount"])

        o.setdefault(bucket, 0)
        o[bucket] += int(row["amount"])

        o.setdefault("amount", 0)
        o["amount"] += int(row["amount"])

    for organisation, row in organisations.items():
        if organisation in sets["PropTech"] & sets["Software"]:
            row["bucket"] = "Both"
        elif organisation in sets["Software"]:
            row["bucket"] = "Software"
        elif organisation in sets["PropTech"]:
            row["bucket"] = "PropTech"
        else:
            row["bucket"] = ""

    # add data quality
    for organisation, row in quality.items():
        if row["ready_for_ODP_adoption"] == "yes":
            set_add("data-ready", organisation)
        for dataset in odp_datasets:
            status = quality[organisation][dataset]
            set_add(f"{dataset}:{status}", organisation)

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

    # score rows
    for organisation, row in rows.items():
        if "proptech" in row["projects"]:
            rows[organisation]["score"] += 10

        if "open-digital-planning" in row["projects"]:
            rows[organisation]["score"] += 100

        if organisation in quality:
            n = 0
            for dataset in odp_datasets:
                n += {
                    "": 0,
                    "none": 0,
                    "some": 1,
                    "authoritative": 2,
                    "ready": 3,
                    "trustworthy": 4,
                }[quality[organisation][dataset]]
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
.dot a { text-decoration: none; color: #222; }
.submission { font-weight: bolder }
.guidance { font-weight: bolder }
.interested { color: #888}

.some, .some a { color:	#d4351c; }
.authoritative, .authoritative a { color: #f47738; }
.ready, .ready a { color: #a8bd3a; }
.trustworthy, .trustworthy a { color: #00703c; }

.chart {
  width: 100%;
  max-width: 1280px;
  min-height: 450px;
}

.tooltip {
    background:#fff;
    padding:10px;
    border-style:solid;
}

</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script>google.charts.load('current', {'packages':['corechart','bar','sankey', 'treemap']});</script>
</head>
<body>
"""
    )

    print("<h1>Digital Planning Programme funding</h1>")
    print(
        f"""
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_funding_treemap)
      function draw_funding_treemap() {{
        var data = new google.visualization.DataTable();
        data.addColumn('string', 'Area name');
        data.addColumn('string', 'Bucket');
        data.addColumn('number', 'Amount');
        data.addColumn('number', 'Color');
        data.addColumn('string', 'Name');
        data.addColumn('string', 'Status');
        data.addRows([
          ['Funded organisation', null, 0, 0, 'All funded organisations', ''],
          ['Software', 'Funded organisation', 0, 0, 'Organisations funded for software', ''],
          ['PropTech', 'Funded organisation', 0, 0, 'Funded for PropTech', ''],
          ['Both', 'Funded organisation', 0, 0, 'Funded for Software and PropTech', ''],
""")
    for organisation in sets["funded"]:
        row = organisations[organisation]
        if not row["bucket"]:
            continue

        color = 0
        status = "Not yet providing data"
        if organisation in sets["data-ready"]:
            color = 1
            status = "Data is ready to adopt PlanX"
        elif organisation in sets["providing"]:
            color = 0.5
            status = "Providing some data"

        print(f"          ['{row['area-name']}', '{row['bucket']}', {row['amount']}, {color}, '{row['name']}', '{status}'],")

    print(f"""]);

        var options = {{
            maxDepth: 2,
            maxPostDepth: 2,
            headerHeight: 15,
            showScale: false,
            //"#00703c", "#a8bd3a", "#f47738", "#d4351c",
            minColor: '#d4351c', 
            midColor: '#f47738',
            maxColor: '#a8bd3a', 
            eventsConfig: {{
              highlight: ['click'],
              unhighlight: ['mouseout'],
              rollup: ['contextmenu'],
              drilldown: ['dblclick'],
            }},
            generateTooltip: showFullTooltip,
        }};

        function showFullTooltip(row, size, value) {{
            return '<div class="tooltip">' +
                   '<span><h2>' + data.getValue(row, 4) + '</h2> ' + 
                   '<p>Awarded £' + data.getValue(row, 2).toLocaleString() + '</p>' +
                   '<p>' + data.getValue(row, 5) + '</p>'
        }}

        var chart = new google.visualization.TreeMap(document.getElementById("funding-treemap-chart"));
        chart.draw(data, options);
      }}
    </script>
    <div id="funding-treemap-chart" class="chart"></div>
    """
    )


    print("<h1>Organisations adopting PlanX</h1>")

    print(
        f"""
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_adoption)
      function draw_adoption() {{
        var data = google.visualization.arrayToDataTable([
          ['Status', 'Count'],
          ['LPA', {len(sets["local-planning-authority"])}],
          ['Funded', {len(sets["funded"])}],
          ['Software funding', {len(sets["Software"])}],
          ['ODP member', {len(sets["open-digital-planning"])}],
          ['Providing some data', {len(sets["providing"])}],
          ['Data ready for PlanX', {len(sets["data-ready"])}],
          ['Interested in PlanX', {len(sets["interested"])}],
          ['Adopting PlanX', {len(sets["adopting"])}],
          ['Adopted PlanX guidance', {len(sets["guidance"])}],
          ['Adopted PlanX submission', {len(sets["submission"])}],
        ]);

        var options = {{
          title: "Number of organisations",
          bars: 'vertical',
          colors: ['#27a0cc'],
          legend: {{ position: "none" }},
          vAxis: {{ gridlines: {{ count:0 }}}}
        }};

        var view = new google.visualization.DataView(data);
        view.setColumns([0, 
                       {{ calc: "stringify",
                         sourceColumn: 1,
                         type: "string",
                         role: "annotation"
                         }}, 1]);
        var chart = new google.visualization.ColumnChart(document.getElementById("adoption-chart"));
        chart.draw(view, options);

      }}
    </script>
    <div id="adoption-chart" class="chart"></div>
    <p>Note: submission includes LPA who have adopted both services.</p>
    """
    )

    print("<h1 id='adoption'>Data needed to adopt PlanX</h1>")
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

    for organisation, row in rows.items():
        dest = {
            "": "",
            "interested": "Have expressd interest in adopting PlanX",
            "adopting": "Are adopting PlanX",
            "guidance": "Have adopted PlanX guidance",
            "submission": "Have adopted PlanX submission",
        }[row["adoption"]]

        if dest:
            if organisation in sets["data-ready"]:
                source = "Have data ready for PlanX"
            elif organisation in sets["providing"]:
                source = "Providing some data"
            else:
                source = "Not yet providing data"
            print(f'{sep}["{source}", "{dest}", 1, "{row["name"]}"]', end="")
            sep = ",\n"

    print(
        """
        ]);
        options = {
            sankey: {
                link: { color: { fill: '#d5d5d6' } },
                node: { colors: [ '#27a0cc' ], width: 20,
                    label: { fontName: 'sans-serif',
                         fontSize: 14,
                         color: '#222',
                         }},
            }
        };
        var chart = new google.visualization.Sankey(document.getElementById("sankey-chart"));
        chart.draw(data, options);
      }
    </script>
    <div id="sankey-chart" class="chart"></div>
    """
    )
    print(f'<p>Note: {len((sets["guidance"]|sets["submission"])-sets["data-ready"])} organisations have adopted PlanX with incomplete data.</p>')

    print("<h1>Overlap between projects</h1>")
    print(
        f"""
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_overlap)
      function draw_overlap() {{
        var data = google.visualization.arrayToDataTable([
          ['Project', 
          'First', 
          'Both', 
          'Second'],
          ['ODP and LLC', {overlaps("open-digital-planning", "local-land-charges")}],
          ['ODP and PropTech', {overlaps("open-digital-planning", "proptech")}],
          ['ODP and Drupal', {overlaps("open-digital-planning", "localgov-drupal")}],
          ['PropTech and LLC', {overlaps("proptech", "local-land-charges")}],
          ['PropTech and Drupal', {overlaps("proptech", "localgov-drupal")}],
          ['Drupal and LLC', {overlaps("localgov-drupal", "local-land-charges")}],
          ['LPA and ODP', {overlaps("local-planning-authority", "open-digital-planning")}],
          ['LPA and PropTech', {overlaps("local-planning-authority", "proptech")}],
          ['LPA and LLC', {overlaps("local-planning-authority", "local-land-charges")}],
          ['LPA and Drupal', {overlaps("local-planning-authority", "localgov-drupal")}],
        ]);

        var options = {{
          title: "Number of organisations",
          bars: 'horizontal',
          colors: [ "#206095", "#003c57", "#27a0cc"],
          isStacked: true,
          hAxis: {{ gridlines: {{ count:0 }}}}
        }};

        var chart = new google.visualization.BarChart(document.getElementById("overlap-chart"));
        chart.draw(data, options);

      }}
    </script>
    <div id="overlap-chart" class="chart"></div>
    """
    )


    print("<h1>Organisations providing data needed to adopt PlanX</h1>")
    print("""
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_provision)
      function draw_provision() {
        var data = google.visualization.arrayToDataTable([
          ['Dataset',
          'Trustworthy data',
          'Data ready for PlanX', 
          'Some authorititive data in this area', 
          'Some data in this area', 
          ],""")

    for dataset in odp_datasets:
        print(f'["{dataset}", ', end="")
        for status in ["trustworthy", "ready", "authoritative", "some"]:
            print(f'{ len( sets.get(dataset+":"+status, set()))},', end="")
        print(f'],')

    print(f"""]);
        var options = {{
          title: "Number of organisations",
          colors: [ "#00703c", "#a8bd3a", "#f47738", "#d4351c", ],
          isStacked: true,
          vAxis: {{ gridlines: {{ count:2 }} }}
        }};

        var chart = new google.visualization.ColumnChart(document.getElementById("provision-chart"));
        chart.draw(data, options);
      }}
    </script>
    <div id="provision-chart" class="chart"></div>
    """
    )


    print("<h1>All LPAs and funded organisations</h1>")
    print(f"""
        <!--
        <table>
            <tr><td class="dot none"></td><td>No data in this area</td></tr>
            <tr><td class="dot some">·</td><td>Some data in this area</td></tr>
            <tr><td class="dot authoritative">○</td><td>Some data in this area from the authoritative source</td></tr>
            <tr><td class="dot ready">●</td><td>Data in this area is ready for PlanX</td></tr>
            <tr><td class="dot trustworthy">◉</td><td>Data in this area can be trusted</td></tr>
        </table>
        -->
        <p>Note: data quality is currently only reported in areas funded to develop or adopt ODP software.</p>
        <table>
        <thead>
            <th scope="col" align="left">Organisation</th>
            <th scope="col" align="left">Ended</th>
            <th scope="col" align="left">LPA</th>
            <th scope="col" align="left">Drupal</th>
            <th scope="col" align="left">LLC</th>
            <th scope="col" align="left">PropTech</th>
            <th scope="col" align="left">ODP</th>
    """)

    for col, datasets in odp_cols.items():
        colspan = len(datasets)
        print(
            f'<th class="odp-col" scope="col" align="left" colspan={colspan}>{col}</th>'
        )

    print(f"""
            <th scope="col" align="left">Data ready</th>
            <th scope="col" align="left">PlanX</th>
        </thead>
    </tbody>
    """)

    for organisation, row in sorted(
        rows.items(), key=lambda x: x[1]["score"], reverse=True
    ):
        if not "interventions" in row:
            print(f"<!-- skipping {organisation} {row['name']} -->")
            continue

        print(f"<tr>")
        print(
            f'<td><a href="{entity_url}{row["entity"]}">{escape(row["name"])}</a></td>'
        )
        print(f'<td>{row.get("end-date", "")}</td>')

        # roles
        dot = "●" if organisation in sets["local-planning-authority"] else ""
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
                status = quality.get(organisation, {}).get(dataset, "")
                if status in ["", "none"]:
                    print(f'<td class="dot"></a></td>')
                else:
                    print(
                        f'<td class="dot {status}"><a href="{data_url}" title="{dataset} : {status}">█</a></td>'
                    )

        # data
        if organisation in sets["data-ready"]:
            print(f'<td class="dot"><a href="{data_url}">●</a></td>')
        else:
            print(f'<td class="dot"></td>')

        # adoption
        print(f'<td class="{row["adoption"]}">{row["adoption"]}</td>')

        print("</tr>")

    print("</tbody>")
    print("</table>")
    print(
        """
        <h1>Data sources</h1>
        <ul>
          <li><a href="https://www.planning.data.gov.uk/organisation/">Organisations</a> (<a href="https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv">CSV</a>)
          <li><a href="https://github.com/digital-land/specification/blob/main/content/award.csv">Funding awards</a>
          <li><a href="https://github.com/digital-land/performance/blob/main/data/adoption.csv">Product adoption</a>
          <li><a href="https://github.com/digital-land/performance/blob/main/data/quality.csv">Data quality</a>
        </ul>
    """
    )

    print("</body>")
