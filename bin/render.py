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

quality_scores = {
    "": 0,
    "none": 0,
    "some": 1,
    "authoritative": 4,
    "ready": 5,
    "trustworthy": 6,
}

odp_datasets = {
    "conservation-area": "CA",
    "conservation-area-document": "CAD",
    "article-4-direction": "A4",
    "article-4-direction-area": "A4A",
    "listed-building-outline": "LBO",
    "tree-preservation-order": "TPO",
    "tree": "Tree",
    "tree-preservation-zone": "TPZ",
}

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
            "data-ready": "",
            "data-score": 0,
            "adoption": "",
            "amount": 0,
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
    funds = load("specification/fund.csv", "fund")
    awards = load("specification/award.csv", "award")
    quality = load("data/quality.csv", "organisation")
    lpas = load("var/cache/local-planning-authority.csv", "reference")
    p153 = load("data/p153.csv", "organisation")

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

        if organisation not in rows:
            add_organisation(organisation, "")

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

        amount = int(row["amount"])

        set_add(intervention, organisation)
        set_add(bucket, organisation)
        set_add("funded", organisation)

        o = rows[organisation]
        o.setdefault(intervention, 0)
        o[intervention] += amount

        o.setdefault(bucket, 0)
        o[bucket] += amount

        o.setdefault("amount", 0)
        o["amount"] += amount

    for organisation, row in rows.items():
        row.setdefault("Software", 0)
        row.setdefault("PropTech", 0)
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

    # add minor application statistics
    for organisation, row in p153.items():
        if organisation in rows:
            rows[organisation]["volume"] = row["volume"] 
            rows[organisation]["percentage"] = row["percentage"] 

    # score rows
    sets["providing"] = set()
    for organisation, row in rows.items():
        shift = 10
        for project in ["localgov-drupal","local-land-charges", "proptech", "open-digital-planning"]:
            if project in row["projects"]:
                row["score"] += shift
            shift *= 10

        if row["amount"]:
            row["score"] += shift
        shift *= 10

        if organisation in quality:
            for dataset in odp_datasets:
                n = quality_scores[quality[organisation][dataset]]
                row["data-score"] += n
            if row["data-score"] >= 4:
                set_add("providing", organisation)
            if organisation in sets["data-ready"]:
                row["data-score"] += 100
            row["score"] += rows[organisation]["data-score"] * shift

        shift *= 1000

        for _set in ["interested", "adopting", "guidance", "submission"]:
            if organisation in sets[_set]:
                row["score"] += shift
            shift *= 10

    # area names
    for organisation, row in rows.items():
        lpa = organisations[organisation].get("local-planning-authority", "")
        if lpa:
            row['area-name'] = lpas.get(lpa, row)["name"].replace(" LPA", "")
        else:
            row['area-name'] = row["name"]
        area_names[row['area-name']] = organisation

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
</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script>google.charts.load('current', {'packages':['corechart','bar','sankey', 'treemap']});</script>
</head>
<body>
"""
    )

    print("<h1 id='funding-and-adoption'>Funding and PlanX adoption</h1>")
    print(
        f"""
    <script type="text/javascript">
      google.charts.setOnLoadCallback(draw_adoption_treemap)
      function draw_adoption_treemap() {{
        var data = new google.visualization.DataTable();
        data.addColumn('string', 'Area name');
        data.addColumn('string', 'Bucket');
        data.addColumn('number', 'Amount');
        data.addColumn('number', 'Color');
        data.addColumn('string', 'Name');
        data.addColumn('string', 'Data status');
        data.addColumn('number', 'PropTech');
        data.addColumn('number', 'Software');
        data.addRows([
""")
    total = { "Software": 0, "PropTech": 0, "Both": 0, "All": 0 }
    for organisation in sets["funded"]:
        row = rows[organisation]
        bucket = row["bucket"]
        if not bucket:
            continue

        amount = row["amount"]
        total[bucket] += amount
        total["All"] += amount

        color = 0
        status = "Not yet declared interest"
        if organisation in sets["guidance"]:
            color = 1
            status = "Adopted PlanX guidance"
        elif organisation in sets["submission"]:
            color = 1
            status = "Adopted PlanX submission"
        elif organisation in sets["interested"]:
            color = 0.5
            status = "Interested in adopting PlanX"
        elif organisation in sets["adopting"]:
            color = 0.5
            status = "Adopting PlanX"

        print(f"          ['{row['area-name']}', '{bucket}', {amount}, {color}, '{row['name']}', '{status}', {row['PropTech']}, {row['Software']}],")

    print(f"""
          ['PropTech', 'Funded organisation', {total["PropTech"]}, 0, 'Funded for PropTech', '', 0, 0,],
          ['Software', 'Funded organisation', {total["Software"]}, 0, 'Organisations funded for software', '', 0, 0,],
          ['Both', 'Funded organisation', {total["Both"]}, 0, 'Funded for Software and PropTech', '', 0, 0,],
          ['Funded organisation', null, {total["All"]}, 0, 'All funded organisations', '', 0, 0,],
    ]);

        var options = {{
            maxDepth: 2,
            maxPostDepth: 2,
            headerHeight: 15,
            showScale: false,
            minColor: '#f5f5f6', 
            midColor: '#bcbcbd',
            maxColor: '#27a0cc', 
            eventsConfig: {{
              highlight: ['click'],
              unhighlight: ['mouseout'],
              rollup: ['contextmenu'],
              drilldown: ['dblclick'],
            }},
            generateTooltip: showFullTooltip,
        }};

        function showFullTooltip(row, size, value) {{
            var s = '<div class="tooltip">' +
                '<span><h2>' + data.getValue(row, 4) + '</h2>';

            const bucket = data.getValue(row, 1);
            if (bucket == 'PropTech' || bucket == 'Both') {{
                s = s + '<p>£' + data.getValue(row, 6).toLocaleString() + ' for PropTech</p>';
            }}
            if (bucket == 'Software' || bucket == 'Both') {{
                s = s + '<p>£' + data.getValue(row, 7).toLocaleString() + ' for Software</p>';
            }}
            if (bucket == 'Both') {{
                s = s + '<p>£' + data.getValue(row, 2).toLocaleString() + ' in total.</p>';
            }}

            var status = data.getValue(row, 5);
            if (status != '') {{
                s = s + '<p>' + status + '</p>'
            }}
            s = s + '</div>'
            return s;
        }}

        var chart = new google.visualization.TreeMap(document.getElementById("adoption-treemap-chart"));
        chart.draw(data, options);
      }}
    </script>
    <div id="adoption-treemap-chart" class="chart"></div>
    """
    )

    print("<h1 id='funding-and-data'>Funding and data quality</h1>")
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
        data.addColumn('number', 'PropTech');
        data.addColumn('number', 'Software');
        data.addRows([
""")
    total = { "Software": 0, "PropTech": 0, "Both": 0, "All": 0 }
    for organisation in sets["funded"]:
        row = rows[organisation]
        bucket = row["bucket"]
        if not bucket:
            continue

        amount = row["amount"]
        total[bucket] += amount
        total["All"] += amount

        color = 0
        status = "Not yet providing data"
        if organisation in sets["data-ready"]:
            color = 1
            status = "Data is ready to adopt PlanX"
        elif organisation in sets["providing"]:
            color = 0.5
            status = "Providing some data"

        print(f"          ['{row['area-name']}', '{bucket}', {amount}, {color}, '{row['name']}', '{status}', {row['PropTech']}, {row['Software']}],")

    print(f"""
          ['PropTech', 'Funded organisation', {total["PropTech"]}, 0, 'Funded for PropTech', '', 0, 0],
          ['Software', 'Funded organisation', {total["Software"]}, 0, 'Organisations funded for software', '', 0, 0],
          ['Both', 'Funded organisation', {total["Both"]}, 0, 'Funded for Software and PropTech', '', 0, 0],
          ['Funded organisation', null, {total["All"]}, 0, 'All funded organisations', '', 0, 0],
    ]);

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
            var s = '<div class="tooltip">' +
                '<span><h2>' + data.getValue(row, 4) + '</h2>';

            const bucket = data.getValue(row, 1);
            if (bucket == 'PropTech' || bucket == 'Both') {{
                s = s + '<p>£' + data.getValue(row, 6).toLocaleString() + ' for PropTech</p>';
            }}
            if (bucket == 'Software' || bucket == 'Both') {{
                s = s + '<p>£' + data.getValue(row, 7).toLocaleString() + ' for Software</p>';
            }}
            if (bucket == 'Both') {{
                s = s + '<p>£' + data.getValue(row, 2).toLocaleString() + ' in total.</p>';
            }}

            var status = data.getValue(row, 5);
            if (status != '') {{
                s = s + '<p>' + status + '</p>'
            }}
            s = s + '</div>'
            return s;
        }}

        var chart = new google.visualization.TreeMap(document.getElementById("funding-treemap-chart"));
        chart.draw(data, options);
      }}
    </script>
    <div id="funding-treemap-chart" class="chart"></div>
    """
    )


    print("<h1 id='adoption-numbers'>Number of organisations adopting PlanX</h1>")

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

    print("<h1 id='adoption-data-needed'>Data needed to adopt PlanX</h1>")
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
            "interested": "Have expressed interest in adopting PlanX",
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

    print("<h1 id='project-overlaps'>Overlap between projects</h1>")
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
          ['ODP and Software', {overlaps("open-digital-planning", "software")}],
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


    print("<h1 id='organisations'>Organisations providing data needed to adopt PlanX</h1>")
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


    print("<h1 id='all-organisations'>All LPAs and funded organisations</h1>")
    print(f"""
        <p>Note: data quality is currently only reported in areas funded to develop or adopt ODP software.</p>
        <table id='sortable' class='sortable'>
        <thead>
            <th scope="col" align="right">#</th>
            <th scope="col" align="left">Organisation</th>
            <th scope="col" align="left">Ended</th>
            <th scope="col" align="right">Minor applications in 2024</th>
            <th scope="col" align="right">% processed in 8 weeks</th>
            <th scope="col" align="left"><abbr title="Local Planning Authority">LPA</th>
            <th scope="col" align="left">Drupal</th>
            <th scope="col" align="left"><abbr title="local-land-charges">LLC</abbr></th>
            <th scope="col" align="left"><abbr title="open-digital-planning">ODP</th>
            <th scope="col" align="right">PropTech</th>
            <th scope="col" align="right">Software</th>
            <th scope="col" align="right">Both</th>
    """)

    for dataset, col  in odp_datasets.items():
        print(f'<th class="odp-col" scope="col" align="left"><abbr title="{dataset}">{col}</abbr></th>')

    print(f"""
            <th scope="col" align="left"><abbr title="Data is good enough to adopt PlanX">Data ready</abbr></th>
            <th scope="col" align="left" data-sort-method="number">PlanX</th>
        </thead>
    </tbody>
    """)

    order = 0
    for organisation, row in sorted(
        rows.items(), key=lambda x: x[1]["score"], reverse=True
    ):
        order += 1
        if not "interventions" in row:
            print(f"<!-- skipping {organisation} {row['name']} -->")
            continue

        print(f"<tr>")
        print(f'<td>{order}</td>')

        print(
            f'<td id="{row["organisation"]}"><a href="{entity_url}{row["entity"]}">{escape(row["name"])}</a></td>'
        )
        print(f'<td>{row.get("end-date", "")}</td>')
        print(f'<td class="number">{row.get("volume", "")}</td>')
        print(f'<td class="number">{row.get("percentage", "")}</td>')

        # roles
        dot = "●" if organisation in sets["local-planning-authority"] else ""
        print(f'<td class="dot">{dot}</td>')

        # projects
        for project in ["localgov-drupal", "local-land-charges", "open-digital-planning"]:
            dot = "●" if project in row["projects"] else ""
            print(f'<td class="dot">{dot}</td>')

        n = row["PropTech"]
        amount = f'£{n:,}' if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')

        n = row["Software"]
        amount = f'£{n:,}' if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')

        n = row.get("amount", "")
        amount = f'£{n:,}' if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')

        # datasets
        dots = ""
        for dataset, col in odp_datasets.items():
            status = quality.get(organisation, {}).get(dataset, "")
            if status in ["", "none"]:
                print(f'<td class="dot" data-sort="0"></a></td>')
            else:
                score = quality_scores[quality[organisation][dataset]]
                print(
                    f'<td class="dot {status}" data-sort="{score}"><a href="{data_url}" title="{dataset} : {status}">█</a></td>'
                )

        # data
        dot = "●" if organisation in sets["data-ready"] else ""
        print(f'<td class="dot" data-sort="{row["data-score"]}">{dot}</td>')

        # adoption
        print(f'<td class="{row["adoption"]}" data-sort="{order}" data-sort-method="number">{row["adoption"]}</td>')
        print(f"</tr>")

    print("</tbody>")
    print("</table>")

    print("<h1 id='awards'>Awards</h1>")
    print(f"""
        <table id='awards-table' class='sortable'>
        <thead>
            <th scope="col" align="right">#</th>
            <th scope="col" align="left">Date</th>
            <th scope="col" align="left">Organisation</th>
            <th scope="col" align="left">Fund</th>
            <th scope="col" align="left">Intervention</th>
            <th scope="col" align="right">Amount</th>
            <th scope="col" align="left">Partners</th>
        </thead>
        <tbody>
    """)

    for award, row in awards.items():
        print(f"<tr>")
        print(f'<td>{award}</td>')
        print(f'<td>{row["start-date"]}</td>')
        print(f'<td><a href="#{row["organisation"]}">{escape(organisations[row["organisation"]]["name"])}</a></td>')
        print(f'<td>{funds[row["fund"]]["name"]}</td>')
        print(f'<td>{interventions[row["intervention"]]["name"]}</td>')
        n = int(row["amount"])
        amount = f'£{n:,}' if n else ""
        print(f'<td class="amount" data-sort="{n}">{amount}</td>')
        print(f'<td>')
        print(f'</td>')

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

    print("""
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js" integrity="sha512-F/gIMdDfda6OD2rnzt/Iyp2V9JLHlFQ+EUyixDg9+rkwjqgW1snpkpx7FD5FV1+gG2fmFj7I3r6ReQDUidHelA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js" integrity="sha512-dRD755QRxlybm0h3LXXIGrFcjNakuxW3reZqnPtUkMv6YsSWoJf+slPjY5v4lZvx2ss+wBZQFegepmA7a2W9eA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
new Tablesort(document.getElementById('sortable'), { descending: true });
new Tablesort(document.getElementById('awards-table'));
</script>
""")
    print("</body>")
