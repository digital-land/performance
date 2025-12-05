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
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader
from html import escape

DATABASE_PATH = "dataset/performance.sqlite3"
BASE_PATH = "/performance"

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
            {"slug": "improvement", "name": "improvement"},
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
            {"slug": "innovation", "name": "innovation"},
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
            {"slug": "plan-making", "name": "plan-making"},
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
            {"slug": "plan-making", "name": "plan-making"},
        ],
    },
    {
        "reference": "PropTech",
        "name": "PropTech",
        "colour": "#27a0cc",
        "description": "Funded for PropTech",
        "interventions": [
            {"slug": "engagement", "name": "engagement"},
            {"slug": "innovation", "name": "innovation"},
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
            {"slug": "plan-making", "name": "plan-making"},
        ],
    },
    {
        "reference": "Plan-making",
        "name": "Plan-making",
        "colour": "#eee",
        "description": "Funded for Plan-making",
        "interventions": [{"slug": "plan-making", "name": "plan-making"}],
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


def format_govuk_date(date_str):
    """Format date string to GOV.UK style: day month year."""
    if not date_str:
        return ""
    try:
        date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
        return date_obj.strftime("%-d %B %Y")
    except (ValueError, AttributeError):
        return date_str


def render(path, template, docs="docs/", **kwargs):
    """Render a template to a file."""
    path = os.path.join(docs, path)
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, "w") as f:
        print(f"creating {path}", file=sys.stderr)
        f.write(template.render(BASE_PATH=BASE_PATH, **kwargs))


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
    from datetime import datetime, timedelta

    cursor = conn.cursor()

    # Get counts for the chart
    counts = {}
    cursor.execute(
        "SELECT COUNT(*) FROM organisations WHERE role = 'local-planning-authority'"
    )
    counts["lpa"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT organisation) FROM project_organisations WHERE project = 'open-digital-planning'"
    )
    counts["odp"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT organisation) FROM organisations WHERE amount > 0"
    )
    counts["funded"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT organisation) FROM organisations WHERE software_amount > 0"
    )
    counts["software"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT organisation) FROM organisations WHERE data_score >= 4 AND data_score < 100"
    )
    counts["providing"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM organisations WHERE data_ready = 1")
    counts["data_ready"] = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM organisations WHERE adoption_status IN ('interested', 'adopting')"
    )
    counts["interested_or_adopting"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM organisations WHERE adoption_status = 'live'")
    counts["live"] = cursor.fetchone()[0]

    # Get timeline data (PlanX adoptions only)
    cursor.execute(
        """
        SELECT a.start_date, o.area_name
        FROM adoptions a
        JOIN organisations o ON a.organisation = o.organisation
        WHERE a.product = 'planx' AND a.adoption_status = 'live'
        ORDER BY a.start_date, o.area_name
    """
    )

    timeline_data = []
    timeline_years = []
    today = datetime.now()

    rows = cursor.fetchall()
    if rows:
        # Define timeline range (2022 to current date)
        start_year = 2022
        start_date = datetime(start_year, 1, 1)
        end_date = today
        total_days = (end_date - start_date).days

        # Generate year labels
        for year in range(start_year, today.year + 1):
            timeline_years.append(year)

        # Calculate bar positions and widths
        for row in rows:
            date_parts = row["start_date"].split("-")
            adoption_date = datetime(
                int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            )

            # Calculate offset from start of timeline to adoption date
            offset_days = (adoption_date - start_date).days
            offset_percent = (offset_days / total_days) * 100

            # Calculate width from adoption date to today
            duration_days = (today - adoption_date).days
            width_percent = (duration_days / total_days) * 100

            timeline_data.append(
                {
                    "area_name": escape(row["area_name"]),
                    "offset_percent": round(offset_percent, 2),
                    "width_percent": round(width_percent, 2),
                }
            )

    # Get funded organisations for treemap
    cursor.execute(
        """
        SELECT organisation, area_name, bucket, amount, proptech_amount, software_amount,
               adoption_status, name
        FROM organisations
        WHERE amount > 0 AND bucket != ''
        ORDER BY score DESC
    """
    )

    funded_orgs = []
    totals = {"proptech": 0, "software": 0, "both": 0, "all": 0}

    for row in cursor.fetchall():
        bucket = row["bucket"]
        amount = row["amount"]

        color = 0
        status = "Not yet declared interest"
        if row["adoption_status"] == "interested":
            color = 0.5
            status = "Have expressed interest in adopting PlanX"
        elif row["adoption_status"] == "adopting":
            color = 0.5
            status = "Adopting PlanX"
        elif row["adoption_status"] == "live":
            color = 0.5
            status = "Have adopted PlanX"

        funded_orgs.append(
            {
                "area_name": escape(row["area_name"]),
                "bucket": bucket,
                "amount": amount,
                "color": color,
                "name": escape(row["name"]),
                "status": status,
                "proptech_amount": row["proptech_amount"],
                "software_amount": row["software_amount"],
            }
        )

        totals[bucket.lower()] += amount
        totals["all"] += amount

    # Get all organisations for table
    cursor.execute(
        """
        SELECT o.*,
               (SELECT COUNT(*) FROM project_organisations po WHERE po.organisation = o.organisation AND po.project = 'localgov-drupal') as drupal,
               (SELECT COUNT(*) FROM project_organisations po WHERE po.organisation = o.organisation AND po.project = 'local-land-charges') as llc,
               (SELECT COUNT(*) FROM project_organisations po WHERE po.organisation = o.organisation AND po.project = 'open-digital-planning') as odp
        FROM organisations o
        ORDER BY o.score DESC
    """
    )

    all_orgs = []
    for row in cursor.fetchall():
        org = dict(row)

        # Format amounts
        org["proptech_display"] = (
            f"£{org['proptech_amount']:,}" if org["proptech_amount"] else ""
        )
        org["software_display"] = (
            f"£{org['software_amount']:,}" if org["software_amount"] else ""
        )
        org["amount_display"] = f"£{org['amount']:,}" if org["amount"] else ""

        # Format project indicators
        org["projects"] = {
            "localgov-drupal": "●" if org["drupal"] else "",
            "local-land-charges": "●" if org["llc"] else "",
            "open-digital-planning": "●" if org["odp"] else "",
        }

        # Format LPA indicator
        org["is_lpa"] = "●" if org["role"] == "local-planning-authority" else ""

        # Get quality data for this organisation
        cursor.execute(
            """
            SELECT dataset, status
            FROM quality
            WHERE organisation = ?
        """,
            (org["organisation"],),
        )

        quality_data = {}
        for q_row in cursor.fetchall():
            status = q_row["status"]
            if status in ["", "none"]:
                quality_data[q_row["dataset"]] = {
                    "status": "",
                    "score": 0,
                    "display": "",
                }
            else:
                quality_data[q_row["dataset"]] = {
                    "status": status,
                    "score": quality_scores.get(status, 0),
                    "display": "█",
                }

        # Fill in missing datasets
        for dataset in odp_datasets:
            if dataset not in quality_data:
                quality_data[dataset] = {"status": "", "score": 0, "display": ""}

        org["quality"] = quality_data
        org["data_ready_display"] = "●" if org["data_ready"] else ""

        all_orgs.append(org)

    # Prepare datasets list
    datasets = [{"key": k, "name": k, "abbr": v} for k, v in odp_datasets.items()]

    template = env.get_template("product/planx.html")
    render(
        "product/planx/index.html",
        template,
        counts=counts,
        timeline_data=timeline_data,
        timeline_years=timeline_years,
        funded_orgs=funded_orgs,
        totals=totals,
        all_orgs=all_orgs,
        datasets=datasets,
    )


def render_organisation_index(env, conn):
    """Render organisation index page."""
    cursor = conn.cursor()

    # Get all organisations with award counts and interventions
    cursor.execute(
        """
        SELECT o.organisation, o.name, o.role, o.end_date,
               COUNT(DISTINCT a.award) as award_count,
               SUM(a.amount) as total_amount,
               COUNT(DISTINCT a.intervention) as intervention_count
        FROM organisations o
        LEFT JOIN awards a ON o.organisation = a.organisation
        GROUP BY o.organisation
        ORDER BY o.name
    """
    )

    all_orgs = [dict(row) for row in cursor.fetchall()]

    # Add dissolved flag and get interventions
    from datetime import date

    today = date.today().isoformat()
    for org in all_orgs:
        org["is_dissolved"] = bool(
            org["end_date"] and org["end_date"] != "" and org["end_date"] < today
        )

        # Get interventions for this organisation
        cursor.execute(
            """
            SELECT DISTINCT i.intervention, i.name
            FROM awards a
            JOIN interventions i ON a.intervention = i.intervention
            WHERE a.organisation = ?
            ORDER BY i.name
        """,
            (org["organisation"],),
        )
        org["interventions"] = [dict(row) for row in cursor.fetchall()]

    # Split into LPAs and other organisations
    lpas = [org for org in all_orgs if org["role"] == "local-planning-authority"]
    other_orgs = [org for org in all_orgs if org["role"] != "local-planning-authority"]

    breadcrumbs = [{"text": "Organisation"}]

    template = env.get_template("organisation/index.html")
    render(
        "organisation/index.html",
        template,
        lpas=lpas,
        other_orgs=other_orgs,
        breadcrumbs=breadcrumbs,
    )


def render_organisations(env, conn):
    """Render individual organisation pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM organisations")
    organisations = cursor.fetchall()

    for org_row in organisations:
        org = dict(org_row)
        organisation_id = org["organisation"]

        # Get projects
        cursor.execute(
            """
            SELECT p.project, p.name
            FROM project_organisations po
            JOIN projects p ON po.project = p.project
            WHERE po.organisation = ?
        """,
            (organisation_id,),
        )
        projects = [dict(row) for row in cursor.fetchall()]

        # Get adoptions
        cursor.execute(
            """
            SELECT *
            FROM adoptions
            WHERE organisation = ?
            ORDER BY start_date ASC
        """,
            (organisation_id,),
        )
        adoptions = [dict(row) for row in cursor.fetchall()]

        # Get awards
        cursor.execute(
            """
            SELECT a.award, a.start_date, a.fund, a.intervention, a.amount,
                   i.name as intervention_name, f.name as fund_name
            FROM awards a
            JOIN interventions i ON a.intervention = i.intervention
            JOIN funds f ON a.fund = f.fund
            WHERE a.organisation = ?
            ORDER BY a.start_date ASC
        """,
            (organisation_id,),
        )
        awards = [dict(row) for row in cursor.fetchall()]

        # Get quality data
        cursor.execute(
            """
            SELECT dataset, status
            FROM quality
            WHERE organisation = ? AND status != ''
        """,
            (organisation_id,),
        )
        quality = [dict(row) for row in cursor.fetchall()]

        # Get partner organisations - partnerships are bidirectional
        # 1. Get awards where this org is the main recipient (has partners in organisations_list)
        # 2. Get awards where this org is in the organisations_list (partner to another org)

        cursor.execute(
            """
            SELECT award, organisation, organisations_list
            FROM awards
            WHERE organisation = ? OR organisations_list LIKE ?
        """,
            (organisation_id, f"%{organisation_id}%"),
        )
        award_rows = cursor.fetchall()

        # Parse partner organisations from awards
        partner_counts = {}
        for row in award_rows:
            # Collect all organisations in this award
            all_orgs = [row["organisation"]]
            if row["organisations_list"]:
                all_orgs.extend(
                    [
                        org.strip()
                        for org in row["organisations_list"].split(";")
                        if org.strip()
                    ]
                )

            # Add each org (except ourselves) as a partner
            for org_id in all_orgs:
                if org_id and org_id != organisation_id:
                    partner_counts[org_id] = partner_counts.get(org_id, 0) + 1

        # Get partner organisation details
        partners = []
        for partner_id, count in partner_counts.items():
            cursor.execute(
                "SELECT organisation, name FROM organisations WHERE organisation = ?",
                (partner_id,),
            )
            partner_row = cursor.fetchone()
            if partner_row:
                partners.append(
                    {
                        "organisation": partner_row["organisation"],
                        "name": partner_row["name"],
                        "shared_count": count,
                    }
                )

        # Sort by count descending, then by name
        partners.sort(key=lambda x: (-x["shared_count"], x["name"]))

        # Generate maps for this organisation if it has awards
        shapes_svg = ""
        points_svg = ""
        if awards:
            shapes_svg = process_shapes_svg(
                conn, filter_type="organisation", filter_value=organisation_id
            )
            points_svg = process_points_svg(
                conn, filter_type="organisation", filter_value=organisation_id
            )

        breadcrumbs = [
            {"text": "Organisations", "url": f"{BASE_PATH}/organisation/"},
            {"text": org["name"]},
        ]

        template = env.get_template("organisation/detail.html")
        render(
            f"organisation/{organisation_id}/index.html",
            template,
            organisation=org,
            projects=projects,
            adoptions=adoptions,
            awards=awards,
            quality=quality,
            partners=partners,
            shapes_svg=shapes_svg,
            points_svg=points_svg,
            breadcrumbs=breadcrumbs,
        )


def render_projects(env, conn):
    """Render individual project pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects")
    projects = cursor.fetchall()

    for proj_row in projects:
        project = dict(proj_row)
        project_id = project["project"]

        # Get organisations in this project
        cursor.execute(
            """
            SELECT o.*, MIN(a.start_date) as start_date
            FROM organisations o
            JOIN project_organisations po ON o.organisation = po.organisation
            LEFT JOIN awards a ON o.organisation = a.organisation
            WHERE po.project = ?
            GROUP BY o.organisation
            ORDER BY o.name
        """,
            (project_id,),
        )
        organisations = [dict(row) for row in cursor.fetchall()]

        # Get interventions for each organisation and calculate buckets
        counts = {legend["reference"]: 0 for legend in AWARD_LEGENDS}
        total = 0

        for org in organisations:
            # Get interventions for this organisation
            cursor.execute(
                """
                SELECT DISTINCT i.intervention, i.name
                FROM awards a
                JOIN interventions i ON a.intervention = i.intervention
                JOIN project_organisations po ON a.organisation = po.organisation
                WHERE a.organisation = ? AND po.project = ?
                ORDER BY i.name
            """,
                (org["organisation"], project_id),
            )
            interventions = [dict(row) for row in cursor.fetchall()]
            org["interventions"] = interventions

            # Calculate bucket if organisation has awards
            if interventions:
                intervention_ids = set(i["intervention"] for i in interventions)
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

        # Calculate summary statistics
        from datetime import datetime

        today = datetime.now().date()

        summary = {
            "total_orgs": len(organisations),
            "dissolved_orgs": 0,
            "intervention_counts": {},
        }

        # Count dissolved organisations and interventions
        for org in organisations:
            # Check if organisation is dissolved
            if org.get("end_date"):
                try:
                    end_date = datetime.strptime(org["end_date"], "%Y-%m-%d").date()
                    if end_date < today:
                        summary["dissolved_orgs"] += 1
                        org["is_dissolved"] = True
                except:
                    pass

            # Count interventions
            for intervention in org.get("interventions", []):
                int_name = intervention["name"]
                summary["intervention_counts"][int_name] = (
                    summary["intervention_counts"].get(int_name, 0) + 1
                )

        # Generate timeline data - count organisations by month
        timeline_data = {}
        for org in organisations:
            if org["start_date"]:
                year = org["start_date"][:4]
                month = org["start_date"][5:7]
                period = f"{year}-{month}"
                timeline_data[period] = timeline_data.get(period, 0) + 1

        # Get all months that have data and create complete timeline
        if timeline_data:
            all_periods = sorted(timeline_data.keys())
            start_year = int(all_periods[0][:4])
            start_month = int(all_periods[0][5:7])
            end_year = int(all_periods[-1][:4])
            end_month = int(all_periods[-1][5:7])

            # Create complete timeline with all months
            timeline_months = []
            cumulative = 0

            current_year = start_year
            current_month = start_month

            while current_year < end_year or (
                current_year == end_year and current_month <= end_month
            ):
                period = f"{current_year}-{current_month:02d}"
                increase = timeline_data.get(period, 0)
                cumulative += increase

                # Format month label
                date_obj = datetime(current_year, current_month, 1)
                month_label = date_obj.strftime("%b %Y")

                timeline_months.append(
                    {
                        "period": period,
                        "label": month_label,
                        "cumulative": cumulative,
                        "increase": increase,
                    }
                )

                # Move to next month
                current_month += 1
                if current_month > 12:
                    current_month = 1
                    current_year += 1

            max_count = cumulative
        else:
            timeline_months = []
            max_count = 0

        # Generate maps for this project
        shapes_svg = process_shapes_svg(
            conn, filter_type="project", filter_value=project_id
        )
        points_svg = process_points_svg(
            conn, filter_type="project", filter_value=project_id
        )

        breadcrumbs = [
            {"text": "Projects", "url": f"{BASE_PATH}/project/"},
            {"text": project["name"]},
        ]

        template = env.get_template("project/detail.html")
        render(
            f"project/{project_id}/index.html",
            template,
            project=project,
            organisations=organisations,
            shapes_svg=shapes_svg,
            points_svg=points_svg,
            legends=AWARD_LEGENDS,
            counts=counts,
            total=total,
            summary=summary,
            timeline_months=timeline_months,
            max_count=max_count,
            breadcrumbs=breadcrumbs,
        )


def render_products(env, conn):
    """Render individual product pages."""
    from datetime import datetime, timedelta

    cursor = conn.cursor()
    today = datetime.now()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    for prod_row in products:
        product = dict(prod_row)
        product_id = product["product"]

        # Create filesystem-safe slug (replace / with -)
        product_slug = product_id.replace("/", "-")

        # Get adoptions for this product
        cursor.execute(
            """
            SELECT a.*, o.name as org_name, o.area_name
            FROM adoptions a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.product = ?
            ORDER BY a.start_date ASC
        """,
            (product_id,),
        )
        adoptions = [dict(row) for row in cursor.fetchall()]

        # Calculate funnel counts
        counts = {}
        cursor.execute(
            "SELECT COUNT(*) FROM organisations WHERE role = 'local-planning-authority'"
        )
        counts["lpa"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM organisations
            WHERE role = 'local-planning-authority'
            AND (end_date IS NULL OR end_date = '' OR end_date > date('now'))
        """
        )
        counts["active_lpa"] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT organisation) FROM project_organisations WHERE project = 'open-digital-planning'"
        )
        counts["odp"] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT organisation) FROM organisations WHERE amount > 0"
        )
        counts["funded"] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT organisation) FROM organisations WHERE software_amount > 0"
        )
        counts["software"] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT organisation) FROM organisations WHERE data_score >= 4 AND data_score < 100"
        )
        counts["providing"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM organisations WHERE data_ready = 1")
        counts["data_ready"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(DISTINCT o.organisation)
            FROM organisations o
            JOIN adoptions a ON o.organisation = a.organisation
            WHERE a.product = ? AND a.adoption_status IN ('interested', 'adopting')
        """,
            (product_id,),
        )
        counts["interested_or_adopting"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(DISTINCT o.organisation)
            FROM organisations o
            JOIN adoptions a ON o.organisation = a.organisation
            WHERE a.product = ? AND a.adoption_status = 'live'
        """,
            (product_id,),
        )
        counts["live"] = cursor.fetchone()[0]

        # Get timeline data (live adoptions only)
        cursor.execute(
            """
            SELECT a.start_date, o.area_name
            FROM adoptions a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.product = ? AND a.adoption_status = 'live'
            ORDER BY a.start_date, o.area_name
        """,
            (product_id,),
        )

        timeline_data = []
        timeline_years = []

        rows = cursor.fetchall()
        if rows:
            # Define timeline range (2022 to current date)
            start_year = 2022
            start_date = datetime(start_year, 1, 1)
            end_date = today
            total_days = (end_date - start_date).days

            # Generate year labels
            for year in range(start_year, today.year + 1):
                timeline_years.append(year)

            # Calculate bar positions and widths
            for row in rows:
                date_parts = row["start_date"].split("-")
                adoption_date = datetime(
                    int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                )

                # Calculate offset from start of timeline to adoption date
                offset_days = (adoption_date - start_date).days
                offset_percent = (offset_days / total_days) * 100

                # Calculate width from adoption date to today
                duration_days = (today - adoption_date).days
                width_percent = (duration_days / total_days) * 100

                timeline_data.append(
                    {
                        "area_name": escape(row["area_name"]),
                        "offset_percent": round(offset_percent, 2),
                        "width_percent": round(width_percent, 2),
                    }
                )

        # Get all funded organisations and check if they've adopted this product
        cursor.execute(
            """
            SELECT DISTINCT o.organisation, o.area_name, o.bucket, o.amount,
                   o.proptech_amount, o.software_amount, o.name, a.adoption_status
            FROM organisations o
            LEFT JOIN adoptions a ON o.organisation = a.organisation AND a.product = ?
            WHERE o.amount > 0 AND o.bucket != ''
            ORDER BY o.score DESC
        """,
            (product_id,),
        )

        funded_orgs = []
        totals = {"proptech": 0, "software": 0, "both": 0, "all": 0}

        for row in cursor.fetchall():
            bucket = row["bucket"]
            amount = row["amount"]

            # Color blue only if they have adopted this specific product
            color = 0
            status = "Not yet declared interest"
            if row["adoption_status"] == "interested":
                color = 0.5
                status = f"Have expressed interest in adopting {product['name']}"
            elif row["adoption_status"] == "adopting":
                color = 0.5
                status = f"Adopting {product['name']}"
            elif row["adoption_status"] == "live":
                color = 0.5
                status = f"Have adopted {product['name']}"

            funded_orgs.append(
                {
                    "area_name": escape(row["area_name"]),
                    "bucket": bucket,
                    "amount": amount,
                    "color": color,
                    "name": escape(row["name"]),
                    "status": status,
                    "proptech_amount": row["proptech_amount"],
                    "software_amount": row["software_amount"],
                }
            )

            totals[bucket.lower()] += amount
            totals["all"] += amount

        breadcrumbs = [
            {"text": "Product", "url": f"{BASE_PATH}/product/"},
            {"text": product["name"]},
        ]

        # Generate treemap SVG if there are funded organisations
        treemap_svg = ""
        if funded_orgs:
            treemap_svg = generate_treemap_svg(funded_orgs, totals)

        template = env.get_template("product/detail.html")
        render(
            f"product/{product_slug}/index.html",
            template,
            product=product,
            adoptions=adoptions,
            counts=counts,
            timeline_data=timeline_data,
            timeline_years=timeline_years,
            funded_orgs=funded_orgs,
            totals=totals,
            product_slug=product_slug,
            breadcrumbs=breadcrumbs,
            treemap_svg=treemap_svg,
        )


def render_product_index(env, conn):
    """Render products index page."""
    cursor = conn.cursor()

    # Get all products with adoption counts
    cursor.execute(
        """
        SELECT p.product, p.name, p.description,
               COUNT(a.organisation) as adoption_count
        FROM products p
        LEFT JOIN adoptions a ON p.product = a.product
        GROUP BY p.product
        ORDER BY p.name
    """
    )

    products = []
    for row in cursor.fetchall():
        prod = dict(row)
        # Add slug for URL
        prod["slug"] = prod["product"].replace("/", "-")
        products.append(prod)

    breadcrumbs = [{"text": "Product"}]

    template = env.get_template("product/index.html")
    render("product/index.html", template, products=products, breadcrumbs=breadcrumbs)


def render_project_index(env, conn):
    """Render projects index page."""
    cursor = conn.cursor()

    # Get all projects with organisation counts
    cursor.execute(
        """
        SELECT p.project, p.name, p.description,
               COUNT(po.organisation) as org_count
        FROM projects p
        LEFT JOIN project_organisations po ON p.project = po.project
        GROUP BY p.project
        ORDER BY p.name
    """
    )

    projects = [dict(row) for row in cursor.fetchall()]

    breadcrumbs = [{"text": "Project"}]

    template = env.get_template("project/index.html")
    render("project/index.html", template, projects=projects, breadcrumbs=breadcrumbs)


def render_intervention_index(env, conn):
    """Render interventions index page."""
    cursor = conn.cursor()

    # Get all interventions with award counts, organisation counts and totals
    cursor.execute(
        """
        SELECT i.intervention, i.name, i.description,
               COUNT(a.award) as award_count,
               COUNT(DISTINCT a.organisation) as organisation_count,
               COALESCE(SUM(a.amount), 0) as total_amount
        FROM interventions i
        LEFT JOIN awards a ON i.intervention = a.intervention
        GROUP BY i.intervention
        ORDER BY i.name
    """
    )

    interventions = [dict(row) for row in cursor.fetchall()]

    breadcrumbs = [{"text": "Intervention"}]

    template = env.get_template("intervention/index.html")
    render(
        "intervention/index.html",
        template,
        interventions=interventions,
        breadcrumbs=breadcrumbs,
    )


def render_interventions(env, conn):
    """Render individual intervention pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM interventions")
    interventions = cursor.fetchall()

    for int_row in interventions:
        intervention = dict(int_row)
        intervention_id = intervention["intervention"]

        # Get awards for this intervention
        cursor.execute(
            """
            SELECT a.award, a.start_date, a.organisation, a.fund, a.amount,
                   o.name as org_name,
                   f.name as fund_name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN funds f ON a.fund = f.fund
            WHERE a.intervention = ?
            ORDER BY a.start_date ASC
        """,
            (intervention_id,),
        )
        awards = [dict(row) for row in cursor.fetchall()]

        # Calculate total amount
        total_amount = sum(award["amount"] for award in awards)

        # Get unique organisations
        cursor.execute(
            """
            SELECT DISTINCT o.organisation, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.intervention = ?
            ORDER BY o.name
        """,
            (intervention_id,),
        )
        organisations = [dict(row) for row in cursor.fetchall()]

        # Generate maps for this intervention
        shapes_svg = process_shapes_svg(
            conn, filter_type="intervention", filter_value=intervention_id
        )
        points_svg = process_points_svg(
            conn, filter_type="intervention", filter_value=intervention_id
        )

        breadcrumbs = [
            {"text": "Intervention", "url": f"{BASE_PATH}/intervention/"},
            {"text": intervention["name"]},
        ]

        template = env.get_template("intervention/detail.html")
        render(
            f"intervention/{intervention_id}/index.html",
            template,
            intervention=intervention,
            awards=awards,
            total_amount=total_amount,
            organisations=organisations,
            shapes_svg=shapes_svg,
            points_svg=points_svg,
            breadcrumbs=breadcrumbs,
        )


def render_fund_index(env, conn):
    """Render funds index page."""
    cursor = conn.cursor()

    # Get all funds with award counts and totals
    cursor.execute(
        """
        SELECT f.fund, f.name, f.description, f.start_date,
               COUNT(a.award) as award_count,
               COALESCE(SUM(a.amount), 0) as total_amount
        FROM funds f
        LEFT JOIN awards a ON f.fund = a.fund
        GROUP BY f.fund
        ORDER BY f.start_date ASC
    """
    )

    funds = [dict(row) for row in cursor.fetchall()]

    # Get interventions for each fund
    for fund in funds:
        cursor.execute(
            """
            SELECT DISTINCT i.intervention, i.name
            FROM awards a
            JOIN interventions i ON a.intervention = i.intervention
            WHERE a.fund = ?
            ORDER BY i.name
        """,
            (fund["fund"],),
        )
        interventions = cursor.fetchall()
        fund["interventions"] = [dict(row) for row in interventions]

    # Calculate summary statistics
    summary = {}

    # Number of funds
    summary["fund_count"] = len(funds)

    # Number of awards
    cursor.execute("SELECT COUNT(*) as count FROM awards")
    summary["award_count"] = cursor.fetchone()["count"]

    # Total amount awarded
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM awards")
    summary["total_amount"] = cursor.fetchone()["total"]

    # Number of organisations directly awarded funding
    cursor.execute("SELECT COUNT(DISTINCT organisation) as count FROM awards")
    summary["direct_orgs"] = cursor.fetchone()["count"]

    # Number of organisations awarded funding through partnerships
    cursor.execute(
        """
        SELECT organisations_list FROM awards
        WHERE organisations_list IS NOT NULL AND organisations_list != ''
        """
    )
    partner_orgs = set()
    for row in cursor.fetchall():
        if row["organisations_list"]:
            partners = [
                p.strip() for p in row["organisations_list"].split(";") if p.strip()
            ]
            partner_orgs.update(partners)
    summary["partner_orgs"] = len(partner_orgs)

    breadcrumbs = [{"text": "Fund"}]

    template = env.get_template("fund/index.html")
    render(
        "fund/index.html",
        template,
        funds=funds,
        summary=summary,
        breadcrumbs=breadcrumbs,
    )


def render_funds(env, conn):
    """Render individual fund pages."""
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM funds")
    funds = cursor.fetchall()

    for fund_row in funds:
        fund = dict(fund_row)
        fund_id = fund["fund"]

        # Get awards for this fund
        cursor.execute(
            """
            SELECT a.award, a.start_date, a.organisation, a.intervention, a.amount,
                   o.name as org_name,
                   i.name as intervention_name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN interventions i ON a.intervention = i.intervention
            WHERE a.fund = ?
            ORDER BY a.start_date ASC
        """,
            (fund_id,),
        )
        awards = [dict(row) for row in cursor.fetchall()]

        # Calculate total amount
        total_amount = sum(award["amount"] for award in awards)

        # Get unique organisations
        cursor.execute(
            """
            SELECT DISTINCT o.organisation, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.fund = ?
            ORDER BY o.name
        """,
            (fund_id,),
        )
        organisations = [dict(row) for row in cursor.fetchall()]

        # Generate maps for this fund
        shapes_svg = process_shapes_svg(conn, filter_type="fund", filter_value=fund_id)
        points_svg = process_points_svg(conn, filter_type="fund", filter_value=fund_id)

        breadcrumbs = [
            {"text": "Fund", "url": f"{BASE_PATH}/fund/"},
            {"text": fund["name"]},
        ]

        template = env.get_template("fund/detail.html")
        render(
            f"fund/{fund_id}/index.html",
            template,
            fund=fund,
            awards=awards,
            total_amount=total_amount,
            organisations=organisations,
            shapes_svg=shapes_svg,
            points_svg=points_svg,
            breadcrumbs=breadcrumbs,
        )


def radius(amount):
    """Calculate circle radius for award amount."""
    return sqrt(float(amount) / pi) / 25


def generate_treemap_svg(funded_orgs, totals, width=1200, height=600):
    """Generate a treemap SVG from hierarchical data.

    Args:
        funded_orgs: List of organisation dictionaries with bucket, amount, color, etc.
        totals: Dictionary with proptech, software, both, all totals
        width: SVG width in pixels
        height: SVG height in pixels

    Returns:
        SVG string
    """
    # Group organisations by bucket
    buckets = {"PropTech": [], "Software": [], "Both": []}

    for org in funded_orgs:
        bucket = org["bucket"]
        if bucket in buckets:
            buckets[bucket].append(org)

    # Calculate bucket sizes
    bucket_sizes = {
        "PropTech": totals.get("proptech", 0),
        "Software": totals.get("software", 0),
        "Both": totals.get("both", 0),
    }

    total = totals.get("all", 1)
    if total == 0:
        total = 1

    # Start SVG
    svg_parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
    ]
    svg_parts.append("<style>")
    svg_parts.append(".treemap-rect { stroke: #fff; stroke-width: 2; }")
    svg_parts.append(".treemap-rect:hover { opacity: 0.8; cursor: pointer; }")
    svg_parts.append(
        ".treemap-label { font-family: Arial, sans-serif; font-size: 10px; font-weight: normal; pointer-events: none; }"
    )
    svg_parts.append(
        ".treemap-bucket-label { fill: #0b0c0c; font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; pointer-events: none; }"
    )
    svg_parts.append("</style>")

    # Layout buckets horizontally
    x_pos = 0
    padding = 4

    for bucket_name in ["PropTech", "Software", "Both"]:
        bucket_value = bucket_sizes[bucket_name]
        if bucket_value == 0:
            continue

        bucket_width = (bucket_value / total) * width
        orgs = buckets[bucket_name]

        if orgs:
            # Create squarified treemap for this bucket
            rects = squarify_layout(
                orgs,
                x_pos + padding,
                padding,
                bucket_width - 2 * padding,
                height - 2 * padding,
            )

            # Draw rectangles
            for rect in rects:
                org = rect["data"]

                # Determine color based on adoption status
                if org["color"] > 0:
                    fill_color = "#12436d"  # Blue for adopted
                else:
                    fill_color = "#f5f5f6"  # Grey for not adopted

                # Create tooltip text
                tooltip_lines = [org["name"]]
                if org["bucket"] == "PropTech" or org["bucket"] == "Both":
                    tooltip_lines.append(f"£{org['proptech_amount']:,} for PropTech")
                if org["bucket"] == "Software" or org["bucket"] == "Both":
                    tooltip_lines.append(f"£{org['software_amount']:,} for Software")
                if org["bucket"] == "Both":
                    tooltip_lines.append(f"£{org['amount']:,} in total")
                if org["status"]:
                    tooltip_lines.append(org["status"])

                tooltip_text = "\n".join(tooltip_lines)

                svg_parts.append(
                    f'<rect class="treemap-rect" x="{rect["x"]:.2f}" y="{rect["y"]:.2f}" '
                    f'width="{rect["width"]:.2f}" height="{rect["height"]:.2f}" '
                    f'fill="{fill_color}">'
                )
                svg_parts.append(f"<title>{escape(tooltip_text)}</title>")
                svg_parts.append("</rect>")

                # Add text label only if rectangle is large enough
                # Estimate: ~6px per character width, need margin
                label = org["area_name"]
                estimated_text_width = len(label) * 6
                if rect["width"] > estimated_text_width + 10 and rect["height"] > 25:
                    text_x = rect["x"] + rect["width"] / 2
                    text_y = rect["y"] + rect["height"] / 2
                    # Use white text on dark background, dark text on light background
                    text_color = "#ffffff" if fill_color == "#12436d" else "#0b0c0c"
                    svg_parts.append(
                        f'<text class="treemap-label" fill="{text_color}" x="{text_x:.2f}" y="{text_y:.2f}" '
                        f'text-anchor="middle" dominant-baseline="middle">'
                        f"{escape(label)}</text>"
                    )

        # Add bucket label at top
        label_x = x_pos + bucket_width / 2
        label_y = 15
        svg_parts.append(
            f'<text class="treemap-bucket-label" x="{label_x:.2f}" y="{label_y:.2f}" '
            f'text-anchor="middle">{escape(bucket_name)}</text>'
        )

        x_pos += bucket_width

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def squarify_layout(items, x, y, width, height):
    """Create a squarified treemap layout.

    Args:
        items: List of items with 'amount' field
        x, y: Top-left corner position
        width, height: Available space

    Returns:
        List of rectangles with x, y, width, height, data
    """
    if not items:
        return []

    total = sum(item["amount"] for item in items)
    if total == 0:
        return []

    # Sort items by size (largest first) for better squarification
    sorted_items = sorted(items, key=lambda i: i["amount"], reverse=True)

    rectangles = []

    def layout_row(row_items, x, y, width, height):
        """Layout a row of items."""
        row_total = sum(item["amount"] for item in row_items)
        if row_total == 0:
            return []

        rects = []
        if width >= height:
            # Horizontal layout
            current_x = x
            for item in row_items:
                item_width = (item["amount"] / row_total) * width
                rects.append(
                    {
                        "x": current_x,
                        "y": y,
                        "width": item_width,
                        "height": height,
                        "data": item,
                    }
                )
                current_x += item_width
        else:
            # Vertical layout
            current_y = y
            for item in row_items:
                item_height = (item["amount"] / row_total) * height
                rects.append(
                    {
                        "x": x,
                        "y": current_y,
                        "width": width,
                        "height": item_height,
                        "data": item,
                    }
                )
                current_y += item_height

        return rects

    # Simple squarification: divide space recursively
    def squarify_recursive(items, x, y, width, height):
        if not items:
            return []

        if len(items) == 1:
            return [
                {"x": x, "y": y, "width": width, "height": height, "data": items[0]}
            ]

        # Split items to achieve better aspect ratios
        mid = len(items) // 2
        first_half = items[:mid]
        second_half = items[mid:]

        first_total = sum(item["amount"] for item in first_half)
        second_total = sum(item["amount"] for item in second_half)
        total = first_total + second_total

        if total == 0:
            return []

        rects = []

        if width >= height:
            # Split horizontally
            first_width = (first_total / total) * width
            rects.extend(squarify_recursive(first_half, x, y, first_width, height))
            rects.extend(
                squarify_recursive(
                    second_half, x + first_width, y, width - first_width, height
                )
            )
        else:
            # Split vertically
            first_height = (first_total / total) * height
            rects.extend(squarify_recursive(first_half, x, y, width, first_height))
            rects.extend(
                squarify_recursive(
                    second_half, x, y + first_height, width, height - first_height
                )
            )

        return rects

    return squarify_recursive(sorted_items, x, y, width, height)


def process_points_svg(conn, filter_type=None, filter_value=None):
    """Process point.svg to add award circles.

    Args:
        conn: Database connection
        filter_type: Optional filter type ('fund', 'intervention', 'project', 'organisation')
        filter_value: Optional filter value (e.g., fund ID)
    """
    cursor = conn.cursor()

    # Get awards with organisation data, optionally filtered
    if filter_type == "fund":
        cursor.execute(
            """
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.fund = ?
        """,
            (filter_value,),
        )
    elif filter_type == "intervention":
        cursor.execute(
            """
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.intervention = ?
        """,
            (filter_value,),
        )
    elif filter_type == "project":
        cursor.execute(
            """
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN project_organisations po ON a.organisation = po.organisation
            WHERE po.project = ?
        """,
            (filter_value,),
        )
    elif filter_type == "organisation":
        cursor.execute(
            """
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE a.organisation = ?
        """,
            (filter_value,),
        )
    else:
        cursor.execute(
            """
            SELECT a.award, a.intervention, a.amount, a.organisation,
                   o.local_planning_authority, o.entity
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
        """
        )

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
    cursor.execute(
        """
        SELECT organisation, local_planning_authority, entity
        FROM organisations
        WHERE local_planning_authority != ''
    """
    )
    org_areas = {}
    for row in cursor.fetchall():
        org_areas[row["organisation"]] = {
            "lpa": row["local_planning_authority"],
            "entity": row["entity"],
        }

    # Build award circles
    award_circles = []
    for award_row in awards_data:
        org = award_row["organisation"]
        intervention = award_row["intervention"]
        amount = award_row["amount"]

        if org not in org_areas:
            continue

        lpa = org_areas[org]["lpa"]
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
                    output.append(
                        f'<circle cx="50" cy="{y1m}" r="{r1m}" /><text x="75" y="62.5" class="key" style="font-size: 11px">£1m</text>\n'
                    )
                    output.append(
                        f'<circle cx="50" cy="{y500k}" r="{r500k}" /><text x="75" y="81" class="key" style="font-size: 11px">£500k</text>\n'
                    )
                    output.append(
                        f'<circle cx="50" cy="{y100k}" r="{r100k}" /><text x="75" y="100" class="key" style="font-size: 11px">£100k</text>\n'
                    )

    return "".join(output)


def process_shapes_svg(conn, filter_type=None, filter_value=None):
    """Process local-planning-authority.svg to add funding colors.

    Args:
        conn: Database connection
        filter_type: Optional filter type ('fund', 'intervention', 'project', 'organisation')
        filter_value: Optional filter value (e.g., fund ID)
    """
    cursor = conn.cursor()

    # Get funded organisations with their classifications, optionally filtered
    if filter_type == "fund":
        cursor.execute(
            """
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != '' AND a.fund = ?
            GROUP BY a.organisation
        """,
            (filter_value,),
        )
    elif filter_type == "intervention":
        cursor.execute(
            """
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != '' AND a.intervention = ?
            GROUP BY a.organisation
        """,
            (filter_value,),
        )
    elif filter_type == "project":
        cursor.execute(
            """
            SELECT DISTINCT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            JOIN project_organisations po ON a.organisation = po.organisation
            WHERE o.local_planning_authority != '' AND po.project = ?
        """,
            (filter_value,),
        )
    elif filter_type == "organisation":
        cursor.execute(
            """
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != '' AND a.organisation = ?
            GROUP BY a.organisation
        """,
            (filter_value,),
        )
    else:
        cursor.execute(
            """
            SELECT a.organisation, o.local_planning_authority, o.name
            FROM awards a
            JOIN organisations o ON a.organisation = o.organisation
            WHERE o.local_planning_authority != ''
            GROUP BY a.organisation
        """
        )

    lpa_orgs = {}
    for row in cursor.fetchall():
        lpa_orgs[row["local_planning_authority"]] = {
            "organisation": row["organisation"],
            "name": row["name"],
        }

    # Get ALL organisations with LPA codes for linking all shapes
    cursor.execute(
        """
        SELECT organisation, local_planning_authority, name
        FROM organisations
        WHERE local_planning_authority != ''
        """
    )
    all_lpa_orgs = {}
    for row in cursor.fetchall():
        all_lpa_orgs[row["local_planning_authority"]] = {
            "organisation": row["organisation"],
            "name": row["name"],
        }

    # Get interventions per organisation to calculate bucket
    if filter_type == "fund":
        cursor.execute(
            """
            SELECT organisation, intervention
            FROM awards
            WHERE fund = ?
        """,
            (filter_value,),
        )
    elif filter_type == "intervention":
        cursor.execute(
            """
            SELECT organisation, intervention
            FROM awards
            WHERE intervention = ?
        """,
            (filter_value,),
        )
    elif filter_type == "project":
        cursor.execute(
            """
            SELECT a.organisation, a.intervention
            FROM awards a
            JOIN project_organisations po ON a.organisation = po.organisation
            WHERE po.project = ?
        """,
            (filter_value,),
        )
    elif filter_type == "organisation":
        cursor.execute(
            """
            SELECT organisation, intervention
            FROM awards
            WHERE organisation = ?
        """,
            (filter_value,),
        )
    else:
        cursor.execute(
            """
            SELECT organisation, intervention
            FROM awards
        """
        )

    org_interventions = {}
    for row in cursor.fetchall():
        org = row["organisation"]
        org_interventions.setdefault(org, set())
        org_interventions[org].add(row["intervention"])

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
                if lpa not in all_lpa_orgs:
                    current_class = ""
                    current_lpa = ""
                    current_name = ""
                else:
                    found.add(lpa)
                    current_lpa = lpa
                    current_name = all_lpa_orgs[lpa]["name"]
                    # Only set class if this org has funding
                    if lpa in lpa_orgs:
                        organisation = lpa_orgs[lpa]["organisation"]
                        current_class = org_buckets.get(organisation, "")
                    else:
                        current_class = ""

            if 'class="local-planning-authority"' in line:
                # Only add link if we have a valid organisation
                if current_lpa and current_lpa in all_lpa_orgs:
                    org_link = (
                        f"/organisation/{all_lpa_orgs[current_lpa]['organisation']}/"
                    )
                    line = line.replace(
                        "<path", f'<a href="{BASE_PATH}{org_link}"><path'
                    )
                    line = line.replace(
                        'class="local-planning-authority"/>',
                        f'class="local-planning-authority {current_class}"><title>{current_name}</title></path></a>',
                    )
                else:
                    # No link for areas not in database
                    line = line.replace(
                        'class="local-planning-authority"/>',
                        f'class="local-planning-authority {current_class}"><title>{current_name}</title></path>',
                    )

            output.append(line)

    return "".join(output)


def render_awards(env, conn):
    """Render awards page with maps and table."""
    cursor = conn.cursor()

    # Get all awards with organisation names
    cursor.execute(
        """
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
    """
    )

    awards = []
    for row in cursor.fetchall():
        # Format partners
        partners_html = ""
        if row["organisations_list"]:
            partner_orgs = [p for p in row["organisations_list"].split(";") if p]
            cursor.execute(
                """
                SELECT organisation, name FROM organisations WHERE organisation IN ({})
            """.format(
                    ",".join(["?"] * len(partner_orgs))
                ),
                partner_orgs,
            )
            partners_html = ", ".join(
                [
                    f'<a href="{BASE_PATH}organisation/{r["organisation"]}/">{escape(r["name"])}</a>'
                    for r in cursor.fetchall()
                ]
            )

        awards.append(
            {
                "award": row["award"],
                "start_date": row["start_date"],
                "organisation": row["organisation"],
                "org_name": escape(row["org_name"]),
                "fund": row["fund"],
                "fund_name": row["fund_name"],
                "intervention": row["intervention"],
                "intervention_name": row["intervention_name"],
                "amount": row["amount"],
                "amount_display": f"£{row['amount']:,}" if row["amount"] else "",
                "partners": partners_html,
                "notes": row["notes"],
            }
        )

    # Calculate counts for stacked chart
    counts = {item["reference"]: 0 for item in AWARD_LEGENDS}

    # Get organisation buckets
    cursor.execute(
        """
        SELECT organisation, intervention
        FROM awards
    """
    )

    org_interventions = {}
    for row in cursor.fetchall():
        org = row["organisation"]
        org_interventions.setdefault(org, set())
        org_interventions[org].add(row["intervention"])

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
    cursor.execute(
        "SELECT COUNT(*) FROM organisations WHERE role = 'local-planning-authority'"
    )
    total = cursor.fetchone()[0]

    breadcrumbs = [{"text": "Award"}]

    template = env.get_template("award/index.html")
    render(
        "award/index.html",
        template,
        awards=awards,
        legends=AWARD_LEGENDS,
        counts=counts,
        total=total,
        shapes_svg=shapes_svg,
        points_svg=points_svg,
        breadcrumbs=breadcrumbs,
    )


def main():
    """Main entry point."""
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database not found at {DATABASE_PATH}", file=sys.stderr)
        print("Please run 'make dataset/performance.sqlite3' first", file=sys.stderr)
        sys.exit(1)

    conn = get_db_connection()
    env = Environment(loader=FileSystemLoader("templates/"))

    # Add custom filters
    env.filters["urlencode"] = lambda s: quote(str(s), safe="")
    env.filters["slugify"] = lambda s: str(s).replace("/", "-")
    env.filters["govuk_date"] = lambda s: format_govuk_date(s)

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
        render_organisation_index(env, conn)
        render_organisations(env, conn)
        render_project_index(env, conn)
        render_projects(env, conn)
        render_product_index(env, conn)
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
