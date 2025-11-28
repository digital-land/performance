#!/usr/bin/env python3

"""
Render performance pages from SQLite database using Jinja2 templates.
"""

import os
import sys
import re
import sqlite3
from math import pi, sqrt
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from html import escape

DATABASE_PATH = "dataset/performance.sqlite3"

# Award page legends
AWARD_LEGENDS = [
    {
        "reference": "Software",
        "name": "Software",
        "colour": "#22d0b6",
        "description": "Funded for Software",
        "interventions": [
            {"slug": "software", "name": "software"},
            {"slug": "integration", "name": "integration"},
            {"slug": "improvement", "name": "improvement"}
        ],
    },
    {
        "reference": "PropTech_Software",
        "name": "PropTech and Software",
        "colour": "#a8bd3a",
        "description": "Funded for Software and PropTech",
        "interventions": [
            {"slug": "software", "name": "software"},
            {"slug": "integration", "name": "integration"},
            {"slug": "improvement", "name": "improvement"},
            {"slug": "engagement", "name": "engagement"},
            {"slug": "innovation", "name": "innovation"}
        ],
    },
    {
        "reference": "Plan-making_Software",
        "name": "Plan-making and Software",
        "colour": "#118c7b",
        "description": "Funded for Software and Plan-making",
        "interventions": [
            {"slug": "software", "name": "software"},
            {"slug": "integration", "name": "integration"},
            {"slug": "improvement", "name": "improvement"},
            {"slug": "plan-making", "name": "plan-making"}
        ],
    },
    {
        "reference": "Plan-making_PropTech_Software",
        "name": "Plan-making and Software",
        "colour": "#746cb1",
        "description": "Funded for Software, PropTech and Plan-making",
        "interventions": [
            {"slug": "software", "name": "software"},
            {"slug": "integration", "name": "integration"},
            {"slug": "improvement", "name": "improvement"},
            {"slug": "engagement", "name": "engagement"},
            {"slug": "innovation", "name": "innovation"},
            {"slug": "plan-making", "name": "plan-making"}
        ],
    },
    {
        "reference": "PropTech",
        "name": "PropTech",
        "colour": "#27a0cc",
        "description": "Funded for PropTech",
        "interventions": [
            {"slug": "engagement", "name": "engagement"},
            {"slug": "innovation", "name": "innovation"}
        ],
    },
    {
        "reference": "Plan-making_PropTech",
        "name": "PropTech and Plan-making",
        "colour": "#206095",
        "description": "Funded for PropTech and Plan-making",
        "interventions": [
            {"slug": "engagement", "name": "engagement"},
            {"slug": "innovation", "name": "innovation"},
            {"slug": "plan-making", "name": "plan-making"}
        ],
    },
    {
        "reference": "Plan-making",
        "name": "Plan-making",
        "colour": "#eee",
        "description": "Funded for Plan-making",
        "interventions": [
            {"slug": "plan-making", "name": "plan-making"}
        ],
    },
]

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


def render(path, template, docs="docs", **kwargs):
    """Render a template to a file."""
    path = os.path.join(docs, path)
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, "w") as f:
        print(f"creating {path}", file=sys.stderr)
        f.write(template.render(**kwargs))


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def render_index(env, conn):
    """Render index page."""
    template = env.get_template("index.html")
    render("index.html", template)


def render_adoption_redirect(env, conn):
    """Render redirect page for old adoption/planx URL."""
    template = env.get_template("adoption/planx.html")
    render("adoption/planx/index.html", template)


def render_adoption_planx(env, conn):
    """Render product/planx page (adoption and planning data)."""
    cursor = conn.cursor()

    # Get counts for the chart
    counts = {}
    cursor.execute("SELECT COUNT(*) FROM organisations WHERE role = 'local-planning-authority'")
    counts['lpa'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT organisation) FROM project_organisations WHERE project = 'open-digital-planning'")
    counts['odp'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT organisation) FROM organisations WHERE amount > 0")
    counts['funded'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT organisation) FROM organisations WHERE software_amount > 0")
    counts['software'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT organisation) FROM organisations WHERE data_score >= 4 AND data_score < 100")
    counts['providing'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM organisations WHERE data_ready = 1")
    counts['data_ready'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM organisations WHERE adoption_status IN ('interested', 'adopting')")
    counts['interested_or_adopting'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM organisations WHERE adoption_status = 'live'")
    counts['live'] = cursor.fetchone()[0]

    # Get timeline data (PlanX adoptions only)
    cursor.execute("""
        SELECT a.start_date, o.area_name
        FROM adoptions a
        JOIN organisations o ON a.organisation = o.organisation
        WHERE a.product = 'planx' AND a.adoption_status = 'live'
        ORDER BY a.start_date, o.area_name
    """)

    timeline_data = []
    today = datetime.now()
    for row in cursor.fetchall():
        date_parts = row['start_date'].split('-')
        timeline_data.append({
            'area_name': escape(row['area_name']),
            'year': int(date_parts[0]),
            'month': int(date_parts[1]) - 1,  # JavaScript months are 0-indexed
            'day': int(date_parts[2])
        })

    # Get funded organisations for treemap
    cursor.execute("""
        SELECT organisation, area_name, bucket, amount, proptech_amount, software_amount,
               adoption_status, name
        FROM organisations
        WHERE amount > 0 AND bucket != ''
        ORDER BY score DESC
    """)

    funded_orgs = []
    totals = {'proptech': 0, 'software': 0, 'both': 0, 'all': 0}

    for row in cursor.fetchall():
        bucket = row['bucket']
        amount = row['amount']

        color = 0
        status = "Not yet declared interest"
        if row['adoption_status'] == 'interested':
            color = 0.5
            status = "Have expressed interest in adopting PlanX"
        elif row['adoption_status'] == 'adopting':
            color = 0.5
            status = "Adopting PlanX"
        elif row['adoption_status'] == 'live':
            color = 0.5
            status = "Have adopted PlanX"

        funded_orgs.append({
            'area_name': escape(row['area_name']),
            'bucket': bucket,
            'amount': amount,
            'color': color,
            'name': escape(row['name']),
            'status': status,
            'proptech_amount': row['proptech_amount'],
            'software_amount': row['software_amount']
        })

        totals[bucket.lower()] += amount
        totals['all'] += amount

    # Get all organisations for table
    cursor.execute("""
        SELECT o.*,
               (SELECT COUNT(*) FROM project_organisations po WHERE po.organisation = o.organisation AND po.project = 'localgov-drupal') as drupal,
               (SELECT COUNT(*) FROM project_organisations po WHERE po.organisation = o.organisation AND po.project = 'local-land-charges') as llc,
               (SELECT COUNT(*) FROM project_organisations po WHERE po.organisation = o.organisation AND po.project = 'open-digital-planning') as odp
        FROM organisations o
        ORDER BY o.score DESC
    """)

    all_orgs = []
    for row in cursor.fetchall():
        org = dict(row)

        # Format amounts
        org['proptech_display'] = f"£{org['proptech_amount']:,}" if org['proptech_amount'] else ""
        org['software_display'] = f"£{org['software_amount']:,}" if org['software_amount'] else ""
        org['amount_display'] = f"£{org['amount']:,}" if org['amount'] else ""

        # Format project indicators
        org['projects'] = {
            'localgov-drupal': '●' if org['drupal'] else '',
            'local-land-charges': '●' if org['llc'] else '',
            'open-digital-planning': '●' if org['odp'] else ''
        }

        # Format LPA indicator
        org['is_lpa'] = '●' if org['role'] == 'local-planning-authority' else ''

        # Get quality data for this organisation
        cursor.execute("""
            SELECT dataset, status
            FROM quality
            WHERE organisation = ?
        """, (org['organisation'],))

        quality_data = {}
        for q_row in cursor.fetchall():
            status = q_row['status']
            if status in ['', 'none']:
                quality_data[q_row['dataset']] = {
                    'status': '',
                    'score': 0,
                    'display': ''
                }
            else:
                quality_data[q_row['dataset']] = {
                    'status': status,
                    'score': quality_scores.get(status, 0),
                    'display': '█'
                }

        # Fill in missing datasets
        for dataset in odp_datasets:
            if dataset not in quality_data:
                quality_data[dataset] = {'status': '', 'score': 0, 'display': ''}

        org['quality'] = quality_data
        org['data_ready_display'] = '●' if org['data_ready'] else ''

        all_orgs.append(org)

    # Prepare datasets list
    datasets = [{'key': k, 'name': k, 'abbr': v} for k, v in odp_datasets.items()]

    template = env.get_template("product/planx.html")
    render("product/planx/index.html", template,
           counts=counts,
           timeline_data=timeline_data,
           today_year=today.year,
           today_month=today.month - 1,
           today_day=today.day,
           funded_orgs=funded_orgs,
           totals=totals,
           all_orgs=all_orgs,
           datasets=datasets)


def render_organisations(env, conn):
    """Render individual organisation pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM organisations")
    organisations = cursor.fetchall()

    for org_row in organisations:
        org = dict(org_row)
        organisation_id = org['organisation']

        # Get projects
        cursor.execute("""
            SELECT p.project, p.name
            FROM project_organisations po
            JOIN projects p ON po.project = p.project
            WHERE po.organisation = ?
        """, (organisation_id,))
        projects = [dict(row) for row in cursor.fetchall()]

        # Get adoptions
        cursor.execute("""
            SELECT *
            FROM adoptions
            WHERE organisation = ?
            ORDER BY start_date ASC
        """, (organisation_id,))
        adoptions = [dict(row) for row in cursor.fetchall()]

        # Get awards
        cursor.execute("""
            SELECT a.award, a.start_date, a.fund, a.intervention, a.amount,
                   i.name as intervention_name, f.name as fund_name
            FROM awards a
            JOIN interventions i ON a.intervention = i.intervention
            JOIN funds f ON a.fund = f.fund
            WHERE a.organisation = ?
            ORDER BY a.start_date ASC
        """, (organisation_id,))
        awards = [dict(row) for row in cursor.fetchall()]

        # Get quality data
        cursor.execute("""
            SELECT dataset, status
            FROM quality
            WHERE organisation = ? AND status != ''
        """, (organisation_id,))
        quality = [dict(row) for row in cursor.fetchall()]

        template = env.get_template("organisation/detail.html")
        render(f"organisation/{organisation_id}/index.html", template,
               organisation=org,
               projects=projects,
               adoptions=adoptions,
               awards=awards,
               quality=quality)


def render_projects(env, conn):
    """Render individual project pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects")
    projects = cursor.fetchall()

    for proj_row in projects:
        project = dict(proj_row)
        project_id = project['project']

        # Get organisations in this project
        cursor.execute("""
            SELECT o.*
            FROM organisations o
            JOIN project_organisations po ON o.organisation = po.organisation
            WHERE po.project = ?
            ORDER BY o.score DESC
        """, (project_id,))
        organisations = [dict(row) for row in cursor.fetchall()]

        # Get interventions for each organisation and calculate buckets
        counts = {legend['reference']: 0 for legend in AWARD_LEGENDS}
        total = 0

        for org in organisations:
            # Get interventions for this organisation
            cursor.execute("""
                SELECT DISTINCT i.intervention, i.name
                FROM awards a
                JOIN interventions i ON a.intervention = i.intervention
                JOIN project_organisations po ON a.organisation = po.organisation
                WHERE a.organisation = ? AND po.project = ?
                ORDER BY i.name
            """, (org['organisation'], project_id))
            interventions = [dict(row) for row in cursor.fetchall()]
            org['interventions'] = interventions

            # Calculate bucket if organisation has awards
            if interventions:
                intervention_ids = set(i['intervention'] for i in interventions)
                buckets = set()
                if intervention_ids & set(["innovation", "engagement"]):
                    buckets.add("PropTech")
                if intervention_ids & set(["software", "integration", "improvement"]):
                    buckets.add("Software")
                if intervention_ids & set(["plan-making"]):
                    buckets.add("Plan-making")
                bucket = "_".join(sorted(list(buckets)))
                if bucket:
                    counts[bucket] = counts.get(bucket, 0) + 1
                    total += 1

        # Generate maps for this project
        shapes_svg = process_shapes_svg(conn, filter_type='project', filter_value=project_id)
        points_svg = process_points_svg(conn, filter_type='project', filter_value=project_id)

        template = env.get_template("project/detail.html")
        render(f"project/{project_id}/index.html", template,
               project=project,
               organisations=organisations,
               shapes_svg=shapes_svg,
               points_svg=points_svg,
               legends=AWARD_LEGENDS,
               counts=counts,
               total=total)


def render_products(env, conn):
    """Render individual product pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    for prod_row in products:
        product = dict(prod_row)
        product_id = product['product']

        # Get adoptions for this product
        cursor.execute("""
            SELECT a.*, o.name as org_name
            FROM adoptions a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.product = ?
            ORDER BY a.start_date ASC
        """, (product_id,))
        adoptions = [dict(row) for row in cursor.fetchall()]

        template = env.get_template("product/detail.html")
        render(f"product/{product_id}/index.html", template,
               product=product,
               adoptions=adoptions)


def render_project_index(env, conn):
    """Render projects index page."""
    cursor = conn.cursor()

    # Get all projects with organisation counts
    cursor.execute("""
        SELECT p.project, p.name, p.description,
               COUNT(po.organisation) as org_count
        FROM projects p
        LEFT JOIN project_organisations po ON p.project = po.project
        GROUP BY p.project
        ORDER BY p.name
    """)

    projects = [dict(row) for row in cursor.fetchall()]

    template = env.get_template("project/index.html")
    render("project/index.html", template, projects=projects)


def render_intervention_index(env, conn):
    """Render interventions index page."""
    cursor = conn.cursor()

    # Get all interventions with award counts and totals
    cursor.execute("""
        SELECT i.intervention, i.name, i.description,
               COUNT(a.award) as award_count,
               COALESCE(SUM(a.amount), 0) as total_amount
        FROM interventions i
        LEFT JOIN awards a ON i.intervention = a.intervention
        GROUP BY i.intervention
        ORDER BY i.name
    """)

    interventions = [dict(row) for row in cursor.fetchall()]

    template = env.get_template("intervention/index.html")
    render("intervention/index.html", template, interventions=interventions)


def render_interventions(env, conn):
    """Render individual intervention pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM interventions")
    interventions = cursor.fetchall()

    for int_row in interventions:
        intervention = dict(int_row)
        intervention_id = intervention['intervention']

        # Get awards for this intervention
        cursor.execute("""
            SELECT a.award, a.start_date, a.organisation, a.fund, a.amount,
                   o.name as org_name,
                   f.name as fund_name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN funds f ON a.fund = f.fund
            WHERE a.intervention = ?
            ORDER BY a.start_date ASC
        """, (intervention_id,))
        awards = [dict(row) for row in cursor.fetchall()]

        # Calculate total amount
        total_amount = sum(award['amount'] for award in awards)

        # Get unique organisations
        cursor.execute("""
            SELECT DISTINCT o.organisation, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.intervention = ?
            ORDER BY o.name
        """, (intervention_id,))
        organisations = [dict(row) for row in cursor.fetchall()]

        # Generate maps for this intervention
        shapes_svg = process_shapes_svg(conn, filter_type='intervention', filter_value=intervention_id)
        points_svg = process_points_svg(conn, filter_type='intervention', filter_value=intervention_id)

        template = env.get_template("intervention/detail.html")
        render(f"intervention/{intervention_id}/index.html", template,
               intervention=intervention,
               awards=awards,
               total_amount=total_amount,
               organisations=organisations,
               shapes_svg=shapes_svg,
               points_svg=points_svg)


def render_fund_index(env, conn):
    """Render funds index page."""
    cursor = conn.cursor()

    # Get all funds with award counts and totals
    cursor.execute("""
        SELECT f.fund, f.name, f.description, f.start_date,
               COUNT(a.award) as award_count,
               COALESCE(SUM(a.amount), 0) as total_amount
        FROM funds f
        LEFT JOIN awards a ON f.fund = a.fund
        GROUP BY f.fund
        ORDER BY f.start_date ASC
    """)

    funds = [dict(row) for row in cursor.fetchall()]

    # Get interventions for each fund
    for fund in funds:
        cursor.execute("""
            SELECT DISTINCT i.intervention, i.name
            FROM awards a
            JOIN interventions i ON a.intervention = i.intervention
            WHERE a.fund = ?
            ORDER BY i.name
        """, (fund['fund'],))
        interventions = cursor.fetchall()
        fund['interventions'] = [dict(row) for row in interventions]

    template = env.get_template("fund/index.html")
    render("fund/index.html", template, funds=funds)


def render_funds(env, conn):
    """Render individual fund pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM funds")
    funds = cursor.fetchall()

    for fund_row in funds:
        fund = dict(fund_row)
        fund_id = fund['fund']

        # Get awards for this fund
        cursor.execute("""
            SELECT a.award, a.start_date, a.organisation, a.intervention, a.amount,
                   o.name as org_name,
                   i.name as intervention_name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN interventions i ON a.intervention = i.intervention
            WHERE a.fund = ?
            ORDER BY a.start_date ASC
        """, (fund_id,))
        awards = [dict(row) for row in cursor.fetchall()]

        # Calculate total amount
        total_amount = sum(award['amount'] for award in awards)

        # Get unique organisations
        cursor.execute("""
            SELECT DISTINCT o.organisation, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.fund = ?
            ORDER BY o.name
        """, (fund_id,))
        organisations = [dict(row) for row in cursor.fetchall()]

        # Generate maps for this fund
        shapes_svg = process_shapes_svg(conn, filter_type='fund', filter_value=fund_id)
        points_svg = process_points_svg(conn, filter_type='fund', filter_value=fund_id)

        template = env.get_template("fund/detail.html")
        render(f"fund/{fund_id}/index.html", template,
               fund=fund,
               awards=awards,
               total_amount=total_amount,
               organisations=organisations,
               shapes_svg=shapes_svg,
               points_svg=points_svg)


def radius(amount):
    """Calculate circle radius for award amount."""
    return sqrt(float(amount) / pi) / 25


def process_points_svg(conn, filter_type=None, filter_value=None):
    """Process point.svg to add award circles.

    Args:
        conn: Database connection
        filter_type: Optional filter type ('fund', 'intervention', 'project')
        filter_value: Optional filter value (e.g., fund ID)
    """
    cursor = conn.cursor()

    # Get awards with organisation data, optionally filtered
    if filter_type == 'fund':
        cursor.execute("""
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.fund = ?
        """, (filter_value,))
    elif filter_type == 'intervention':
        cursor.execute("""
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.intervention = ?
        """, (filter_value,))
    elif filter_type == 'project':
        cursor.execute("""
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN project_organisations po ON a.organisation = po.organisation
            WHERE po.project = ?
        """, (filter_value,))
    else:
        cursor.execute("""
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
        """)

    awards_data = cursor.fetchall()

    # Build circle lookup by area
    circles = {}
    re_id = re.compile(r"id=\"(?P<id>\w+)")

    svg_path = "var/cache/point.svg"
    if not os.path.exists(svg_path):
        return ""

    with open(svg_path) as f:
        for line in f.readlines():
            if "<circle" in line:
                match = re_id.search(line)
                if match:
                    area = match.group("id")
                    circles[area] = line

    # Get organisations to map LPA to areas
    cursor.execute("""
        SELECT organisation, local_planning_authority, entity
        FROM organisations
        WHERE local_planning_authority != ''
    """)
    org_areas = {}
    for row in cursor.fetchall():
        org_areas[row['organisation']] = {
            'lpa': row['local_planning_authority'],
            'entity': row['entity']
        }

    # Build award circles
    award_circles = []
    for award_row in awards_data:
        org = award_row['organisation']
        intervention = award_row['intervention']
        amount = award_row['amount']

        if org not in org_areas:
            continue

        lpa = org_areas[org]['lpa']
        if lpa in circles:
            line = circles[lpa]
            r = radius(amount)
            line = line.replace('r="1"', f'r="{r:.2f}"')
            line = line.replace('class="point"', f'class="{intervention}"')
            award_circles.append(line)

    # Build final SVG
    output = []
    first = True
    with open(svg_path) as f:
        for line in f.readlines():
            if "<circle" in line:
                if first:
                    for circle_line in award_circles:
                        output.append(circle_line)
                    first = False
            else:
                if "<svg" in line:
                    line = line.replace("455", "465")
                output.append(line)
                if "<svg" in line:
                    # Add scale legend
                    r100k = radius(100000)
                    r500k = radius(500000)
                    r1m = radius(1000000)
                    y100k = 100 - r100k
                    y500k = 100 - r500k
                    y1m = 100 - r1m
                    output.append(f'<circle cx="50" cy="{y1m}" r="{r1m}" /><text x="75" y="62.5" class="key" style="font-size: 11px">£1m</text>\n')
                    output.append(f'<circle cx="50" cy="{y500k}" r="{r500k}" /><text x="75" y="81" class="key" style="font-size: 11px">£500k</text>\n')
                    output.append(f'<circle cx="50" cy="{y100k}" r="{r100k}" /><text x="75" y="100" class="key" style="font-size: 11px">£100k</text>\n')

    return ''.join(output)


def process_shapes_svg(conn, filter_type=None, filter_value=None):
    """Process local-planning-authority.svg to add funding colors.

    Args:
        conn: Database connection
        filter_type: Optional filter type ('fund', 'intervention', 'project')
        filter_value: Optional filter value (e.g., fund ID)
    """
    cursor = conn.cursor()

    # Get funded organisations with their classifications, optionally filtered
    if filter_type == 'fund':
        cursor.execute("""
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != '' AND a.fund = ?
            GROUP BY a.organisation
        """, (filter_value,))
    elif filter_type == 'intervention':
        cursor.execute("""
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != '' AND a.intervention = ?
            GROUP BY a.organisation
        """, (filter_value,))
    elif filter_type == 'project':
        cursor.execute("""
            SELECT DISTINCT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN project_organisations po ON a.organisation = po.organisation
            WHERE o.local_planning_authority != '' AND po.project = ?
        """, (filter_value,))
    else:
        cursor.execute("""
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != ''
            GROUP BY a.organisation
        """)

    lpa_orgs = {}
    for row in cursor.fetchall():
        lpa_orgs[row['local_planning_authority']] = {
            'organisation': row['organisation'],
            'name': row['name']
        }

    # Get interventions per organisation to calculate bucket
    if filter_type == 'fund':
        cursor.execute("""
            SELECT organisation, intervention
            FROM awards
            WHERE fund = ?
        """, (filter_value,))
    elif filter_type == 'intervention':
        cursor.execute("""
            SELECT organisation, intervention
            FROM awards
            WHERE intervention = ?
        """, (filter_value,))
    elif filter_type == 'project':
        cursor.execute("""
            SELECT a.organisation, a.intervention
            FROM awards a
            JOIN project_organisations po ON a.organisation = po.organisation
            WHERE po.project = ?
        """, (filter_value,))
    else:
        cursor.execute("""
            SELECT organisation, intervention
            FROM awards
        """)

    org_interventions = {}
    for row in cursor.fetchall():
        org = row['organisation']
        org_interventions.setdefault(org, set())
        org_interventions[org].add(row['intervention'])

    # Calculate bucket for each organisation
    org_buckets = {}
    for org, interventions in org_interventions.items():
        buckets = set()
        if interventions & set(["innovation", "engagement"]):
            buckets.add("PropTech")
        if interventions & set(["software", "integration", "improvement"]):
            buckets.add("Software")
        if interventions & set(["plan-making"]):
            buckets.add("Plan-making")
        org_buckets[org] = "_".join(sorted(list(buckets)))

    svg_path = "var/cache/local-planning-authority.svg"
    if not os.path.exists(svg_path):
        return ""

    re_id = re.compile(r"id=\"(?P<lpa>\w+)")
    found = set()
    current_class = ""
    current_lpa = ""
    current_name = ""

    output = []
    with open(svg_path) as f:
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
                if lpa not in lpa_orgs:
                    current_class = ""
                    current_lpa = ""
                    current_name = ""
                else:
                    found.add(lpa)
                    organisation = lpa_orgs[lpa]['organisation']
                    current_name = lpa_orgs[lpa]['name']
                    current_class = org_buckets.get(organisation, "")
                    current_lpa = lpa

            if 'class="local-planning-authority"' in line:
                org_link = f"/organisation/{lpa_orgs[current_lpa]['organisation']}/" if current_lpa and current_lpa in lpa_orgs else "#"
                line = line.replace("<path", f'<a href="{org_link}"><path')
                line = line.replace(
                    'class="local-planning-authority"/>',
                    f'class="local-planning-authority {current_class}"><title>{current_name}</title></path></a>'
                )

            output.append(line)

    return ''.join(output)


def render_awards(env, conn):
    """Render awards page with maps and table."""
    cursor = conn.cursor()

    # Get all awards with organisation names
    cursor.execute("""
        SELECT a.award, a.start_date, a.organisation, a.intervention, a.fund,
               a.amount, a.organisations_list, a.notes,
               o.name as org_name,
               i.name as intervention_name,
               f.name as fund_name
        FROM awards a
        JOIN organisations o ON a.organisation = o.organisation
        JOIN interventions i ON a.intervention = i.intervention
        JOIN funds f ON a.fund = f.fund
        ORDER BY a.start_date ASC
    """)

    awards = []
    for row in cursor.fetchall():
        # Format partners
        partners_html = ""
        if row['organisations_list']:
            partner_orgs = [p for p in row['organisations_list'].split(";") if p]
            cursor.execute("""
                SELECT name FROM organisations WHERE organisation IN ({})
            """.format(','.join(['?'] * len(partner_orgs))), partner_orgs)
            partner_names = [escape(r['name']) for r in cursor.fetchall()]
            partners_html = ", ".join([f'<a href="/organisation/{row["organisation"]}/">{name}</a>' for name in partner_names])

        awards.append({
            'award': row['award'],
            'start_date': row['start_date'],
            'organisation': row['organisation'],
            'org_name': escape(row['org_name']),
            'fund': row['fund'],
            'fund_name': row['fund_name'],
            'intervention': row['intervention'],
            'intervention_name': row['intervention_name'],
            'amount': row['amount'],
            'amount_display': f"£{row['amount']:,}" if row['amount'] else "",
            'partners': partners_html,
            'notes': row['notes']
        })

    # Calculate counts for stacked chart
    counts = {item['reference']: 0 for item in AWARD_LEGENDS}

    # Get organisation buckets
    cursor.execute("""
        SELECT organisation, intervention
        FROM awards
    """)

    org_interventions = {}
    for row in cursor.fetchall():
        org = row['organisation']
        org_interventions.setdefault(org, set())
        org_interventions[org].add(row['intervention'])

    for org, interventions in org_interventions.items():
        buckets = set()
        if interventions & set(["innovation", "engagement"]):
            buckets.add("PropTech")
        if interventions & set(["software", "integration", "improvement"]):
            buckets.add("Software")
        if interventions & set(["plan-making"]):
            buckets.add("Plan-making")
        bucket_key = "_".join(sorted(list(buckets)))
        if bucket_key in counts:
            counts[bucket_key] += 1

    # Process SVG maps
    shapes_svg = process_shapes_svg(conn)
    points_svg = process_points_svg(conn)

    # Get total LPA count
    cursor.execute("SELECT COUNT(*) FROM organisations WHERE role = 'local-planning-authority'")
    total = cursor.fetchone()[0]

    template = env.get_template("award/index.html")
    render("award/index.html", template,
           awards=awards,
           legends=AWARD_LEGENDS,
           counts=counts,
           total=total,
           shapes_svg=shapes_svg,
           points_svg=points_svg)


def main():
    """Main entry point."""
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database not found at {DATABASE_PATH}", file=sys.stderr)
        print("Please run 'make dataset/performance.sqlite3' first", file=sys.stderr)
        sys.exit(1)

    conn = get_db_connection()
    env = Environment(loader=FileSystemLoader("templates/"))

    try:
        print("Rendering pages...", file=sys.stderr)
        render_index(env, conn)
        render_adoption_redirect(env, conn)
        render_adoption_planx(env, conn)
        render_awards(env, conn)
        render_intervention_index(env, conn)
        render_interventions(env, conn)
        render_fund_index(env, conn)
        render_funds(env, conn)
        render_organisations(env, conn)
        render_project_index(env, conn)
        render_projects(env, conn)
        render_products(env, conn)
        print("All pages rendered successfully!", file=sys.stderr)
    except Exception as e:
        print(f"Error rendering pages: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
