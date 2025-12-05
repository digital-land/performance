#!/usr/bin/env python3

"""
Load performance data into SQLite database.
Extracts data processing logic from various bin scripts.
"""

import sys
import csv
import sqlite3
from datetime import datetime

csv.field_size_limit(sys.maxsize)

# Configuration
entity_url = "https://www.planning.data.gov.uk/entity/"
DATABASE_PATH = "dataset/performance.sqlite3"

# Quality status mapping
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


def load_csv(path, key, opt=None):
    """Load CSV file into dictionary keyed by specified column."""
    d = {}
    for row in csv.DictReader(open(path, newline="")):
        if (not opt) or opt(row):
            d[row[key]] = row
    return d


def create_schema(conn):
    """Create database schema."""
    cursor = conn.cursor()

    # Organisations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organisations (
            organisation TEXT PRIMARY KEY,
            entity TEXT,
            name TEXT,
            role TEXT,
            end_date TEXT,
            local_planning_authority TEXT,
            area_name TEXT,
            score INTEGER DEFAULT 0,
            data_score INTEGER DEFAULT 0,
            adoption_status TEXT,
            amount INTEGER DEFAULT 0,
            proptech_amount INTEGER DEFAULT 0,
            software_amount INTEGER DEFAULT 0,
            bucket TEXT,
            data_ready INTEGER DEFAULT 0,
            volume TEXT,
            percentage TEXT
        )
    """)

    # Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project TEXT PRIMARY KEY,
            name TEXT,
            description TEXT
        )
    """)

    # Products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product TEXT PRIMARY KEY,
            name TEXT,
            description TEXT
        )
    """)

    # Adoptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adoptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT,
            organisation TEXT,
            product TEXT,
            adoption_status TEXT,
            documentation_url TEXT,
            FOREIGN KEY (organisation) REFERENCES organisations(organisation),
            FOREIGN KEY (product) REFERENCES products(product)
        )
    """)

    # Awards table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS awards (
            award TEXT PRIMARY KEY,
            start_date TEXT,
            end_date TEXT,
            organisation TEXT,
            intervention TEXT,
            fund TEXT,
            amount INTEGER,
            organisations_list TEXT,
            notes TEXT,
            FOREIGN KEY (organisation) REFERENCES organisations(organisation)
        )
    """)

    # Interventions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interventions (
            intervention TEXT PRIMARY KEY,
            name TEXT,
            description TEXT
        )
    """)

    # Funds table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funds (
            fund TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            start_date TEXT,
            documentation_url TEXT
        )
    """)

    # Project organisations (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_organisations (
            project TEXT,
            organisation TEXT,
            start_date TEXT,
            end_date TEXT,
            PRIMARY KEY (project, organisation),
            FOREIGN KEY (project) REFERENCES projects(project),
            FOREIGN KEY (organisation) REFERENCES organisations(organisation)
        )
    """)

    # Quality data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality (
            organisation TEXT,
            dataset TEXT,
            status TEXT,
            ready_for_odp_adoption TEXT,
            PRIMARY KEY (organisation, dataset),
            FOREIGN KEY (organisation) REFERENCES organisations(organisation)
        )
    """)

    conn.commit()


def load_data(conn):
    """Load all data from CSV files into database."""
    cursor = conn.cursor()

    # Load reference data
    print("Loading organisations...", file=sys.stderr)
    organisations = load_csv("var/cache/organisation.csv", "organisation")

    print("Loading local planning authorities...", file=sys.stderr)
    lpas = load_csv("var/cache/local-planning-authority.csv", "reference")

    print("Loading interventions...", file=sys.stderr)
    interventions = load_csv("specification/intervention.csv", "intervention")
    for intervention, row in interventions.items():
        cursor.execute("""
            INSERT OR REPLACE INTO interventions (intervention, name, description)
            VALUES (?, ?, ?)
        """, (intervention, row.get("name", ""), row.get("description", "")))

    print("Loading funds...", file=sys.stderr)
    funds = load_csv("specification/fund.csv", "fund")
    for fund, row in funds.items():
        cursor.execute("""
            INSERT OR REPLACE INTO funds (fund, name, description, start_date, documentation_url)
            VALUES (?, ?, ?, ?, ?)
        """, (fund, row.get("name", ""), row.get("description", ""), row.get("start-date", ""), row.get("documentation-url", "")))

    print("Loading awards...", file=sys.stderr)
    awards = load_csv("specification/award.csv", "award")
    # Remove awards before the programme
    awards = {k: v for k, v in awards.items() if v["start-date"] >= "2021-06-01"}

    for award, row in awards.items():
        cursor.execute("""
            INSERT OR REPLACE INTO awards
            (award, start_date, end_date, organisation, intervention, fund, amount, organisations_list, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            award,
            row.get("start-date", ""),
            row.get("end-date", ""),
            row.get("organisation", ""),
            row.get("intervention", ""),
            row.get("fund", ""),
            int(row.get("amount", 0)),
            row.get("organisations", ""),
            row.get("notes", "")
        ))

    print("Loading quality data...", file=sys.stderr)
    quality_data = load_csv("data/quality.csv", "organisation")

    # Fixup quality status
    for organisation, row in quality_data.items():
        for dataset in odp_datasets:
            original_value = row.get(dataset, "")
            row[dataset] = quality_lookup.get(original_value, "")

            cursor.execute("""
                INSERT OR REPLACE INTO quality (organisation, dataset, status, ready_for_odp_adoption)
                VALUES (?, ?, ?, ?)
            """, (
                organisation,
                dataset,
                row[dataset],
                row.get("ready_for_ODP_adoption", "")
            ))

    print("Loading organisation roles...", file=sys.stderr)
    organisation_roles = {}
    for row in csv.DictReader(open("specification/role-organisation.csv", newline="")):
        organisation = row["organisation"]
        organisation_roles.setdefault(organisation, [])
        organisation_roles[organisation].append(row["role"])

    print("Loading projects...", file=sys.stderr)
    projects = {
        "open-digital-planning": "Open Digital Planning",
        "local-land-charges": "Local Land Charges",
        "localgov-drupal": "LocalGov Drupal",
        "proptech": "PropTech",
        "software": "Software"
    }

    for project, name in projects.items():
        cursor.execute("""
            INSERT OR REPLACE INTO projects (project, name, description)
            VALUES (?, ?, ?)
        """, (project, name, ""))

    print("Loading products...", file=sys.stderr)
    products_list = {
        "planx": "PlanX",
        "bops": "BOPS",
        "dsn/dpr": "Digital Site Notice / Digital Planning Register"
    }

    for product, name in products_list.items():
        cursor.execute("""
            INSERT OR REPLACE INTO products (product, name, description)
            VALUES (?, ?, ?)
        """, (product, name, ""))

    # Build organisation data with sets for tracking
    print("Processing organisations...", file=sys.stderr)
    rows = {}
    sets = {}

    adoption_status_values = ["interested", "adopting", "live"]
    for status in adoption_status_values:
        sets.setdefault(status, set())

    def add_organisation(organisation, role):
        if organisation not in rows:
            rows[organisation] = {
                "organisation": organisation,
                "role": role,
                "score": 0,
                "data-score": 0,
                "adoption": "",
                "amount": 0,
                "PropTech": 0,
                "Software": 0,
                "bucket": ""
            }

    def set_add(name, organisation):
        sets.setdefault(name, set())
        sets[name].add(organisation)

    # Add LPAs
    for organisation, roles in organisation_roles.items():
        if "local-planning-authority" in roles and not organisations[organisation]["end-date"]:
            add_organisation(organisation, role="local-planning-authority")

    # Load project organisations
    print("Loading project organisations...", file=sys.stderr)
    for row in csv.DictReader(open("specification/project-organisation.csv", newline="")):
        if row["end-date"]:
            continue

        organisation = row["organisation"]
        project = row["project"]

        if organisation not in rows:
            if "local-planning-authority" in organisation_roles.get(organisation, []):
                role = "local-planning-authority"
            else:
                role = "other"
            add_organisation(organisation, role=role)

        set_add(project, organisation)
        rows[organisation]["score"] = rows[organisation]["score"] + 1

        cursor.execute("""
            INSERT OR REPLACE INTO project_organisations (project, organisation, start_date, end_date)
            VALUES (?, ?, ?, ?)
        """, (project, organisation, row.get("start-date", ""), row.get("end-date", "")))

    # Process funding awards
    print("Processing funding awards...", file=sys.stderr)
    for award, row in awards.items():
        organisation = row["organisation"]
        intervention = row["intervention"]
        partners = filter(None, row.get("organisations", "").split(";"))

        # ODP membership
        if intervention in ["engagement", "innovation", "software", "integration", "improvement"]:
            set_add("open-digital-planning", organisation)
            for partner in partners:
                set_add("open-digital-planning", partner)

        if organisation not in rows:
            add_organisation(organisation, "")

        set_add(intervention, organisation)

        if intervention in ["software", "integration", "improvement"]:
            bucket = "Software"
        elif intervention in ["engagement", "innovation"]:
            bucket = "PropTech"
        else:
            continue

        amount = int(row["amount"])

        set_add(bucket, organisation)
        set_add("funded", organisation)

        o = rows[organisation]
        o.setdefault("PropTech", 0)
        o.setdefault("Software", 0)

        if bucket == "PropTech":
            o["PropTech"] += amount
        else:
            o["Software"] += amount

        o["amount"] += amount

    # Determine bucket classification
    for organisation, row in rows.items():
        row.setdefault("Software", 0)
        row.setdefault("PropTech", 0)
        if organisation in sets.get("PropTech", set()) and organisation in sets.get("Software", set()):
            row["bucket"] = "Both"
        elif organisation in sets.get("Software", set()):
            row["bucket"] = "Software"
        elif organisation in sets.get("PropTech", set()):
            row["bucket"] = "PropTech"
        else:
            row["bucket"] = ""

    # Add data quality flags
    print("Processing data quality...", file=sys.stderr)
    for organisation, row_data in quality_data.items():
        if row_data.get("ready_for_ODP_adoption") == "yes":
            set_add("data-ready", organisation)

    # Add adoption data
    print("Loading adoptions...", file=sys.stderr)
    for row in csv.DictReader(open("data/adoption.csv", newline="")):
        organisation = row["organisation"]

        cursor.execute("""
            INSERT INTO adoptions (start_date, organisation, product, adoption_status, documentation_url)
            VALUES (?, ?, ?, ?, ?)
        """, (
            row.get("start-date", ""),
            organisation,
            row.get("product", ""),
            row.get("adoption-status", ""),
            row.get("documentation-url", "")
        ))

        set_add(row["adoption-status"], organisation)
        if organisation in rows:
            rows[organisation]["adoption"] = row["adoption-status"]

    # Load P153 statistics
    print("Loading P153 statistics...", file=sys.stderr)
    try:
        p153 = load_csv("data/p153.csv", "organisation")
        for organisation, row_data in p153.items():
            if organisation in rows:
                rows[organisation]["volume"] = row_data.get("volume", "")
                rows[organisation]["percentage"] = row_data.get("percentage", "")
    except FileNotFoundError:
        print("Warning: p153.csv not found, skipping...", file=sys.stderr)

    # Calculate scores
    print("Calculating scores...", file=sys.stderr)
    sets["providing"] = set()
    for organisation, row in rows.items():
        shift = 10
        for project in ["localgov-drupal", "local-land-charges", "proptech", "open-digital-planning"]:
            if organisation in sets.get(project, set()):
                row["score"] += shift
            shift *= 10

        if row["amount"]:
            row["score"] += shift
        shift *= 10

        if organisation in quality_data:
            for dataset in odp_datasets:
                n = quality_scores[quality_data[organisation].get(dataset, "")]
                row["data-score"] += n
            if row["data-score"] >= 4:
                set_add("providing", organisation)
            if organisation in sets.get("data-ready", set()):
                row["data-score"] += 100
            row["score"] += row["data-score"] * shift

        shift *= 1000

        for status in adoption_status_values:
            if organisation in sets.get(status, set()):
                row["score"] += shift
            shift *= 10

    # Add area names and insert organisations
    print("Inserting organisations...", file=sys.stderr)
    for organisation, row in rows.items():
        org_data = organisations[organisation]
        lpa = org_data.get("local-planning-authority", "")
        if lpa:
            area_name = lpas.get(lpa, row).get("name", "").replace(" LPA", "")
        else:
            area_name = org_data.get("name", "")

        data_ready = 1 if organisation in sets.get("data-ready", set()) else 0

        cursor.execute("""
            INSERT OR REPLACE INTO organisations
            (organisation, entity, name, role, end_date, local_planning_authority,
             area_name, score, data_score, adoption_status, amount,
             proptech_amount, software_amount, bucket, data_ready, volume, percentage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            organisation,
            org_data.get("entity", ""),
            org_data.get("name", ""),
            row.get("role", ""),
            org_data.get("end-date", ""),
            lpa,
            area_name,
            row.get("score", 0),
            row.get("data-score", 0),
            row.get("adoption", ""),
            row.get("amount", 0),
            row.get("PropTech", 0),
            row.get("Software", 0),
            row.get("bucket", ""),
            data_ready,
            row.get("volume", ""),
            row.get("percentage", "")
        ))

    conn.commit()
    print("Data loading complete!", file=sys.stderr)


def main():
    """Main entry point."""
    import os

    # Ensure dataset directory exists
    os.makedirs("dataset", exist_ok=True)

    # Remove existing database
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)

    # Create new database
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        create_schema(conn)
        load_data(conn)
    except Exception as e:
        print(f"Error loading data: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()

    print(f"Database created successfully at {DATABASE_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
