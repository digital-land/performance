#!/usr/bin/env python3

# layered diagram 

import sys
import re
import csv

color = "#C70D77"
funds = {}
funded_organisation = {}
counts = {}


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


def shapes_map(lpas):
    re_id = re.compile(r"id=\"(?P<lpa>\w+)")

    found = set()
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

    shapes_map()
