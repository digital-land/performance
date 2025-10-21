import os
import sys
import csv
from jinja2 import Environment, FileSystemLoader


tables = {}


def load(path, key, opt=None):
    d = {}
    for row in csv.DictReader(open(path, newline="")):
        if (not opt) or opt(row):
            d[row[key]] = row
    return d


def load_table(name, path, key=None, opt=None):
    key = key or name
    tables[name] = load(path, key, opt)


def render(path, template, docs="docs", **kwargs):
    path = os.path.join(docs, path)
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, "w") as f:
        print(f"creating {path}", file=sys.stderr)
        f.write(template.render(**kwargs))



if __name__ == "__main__":
    environment = Environment(loader=FileSystemLoader("templates/"))

    template = environment.get_template("index.html")
    render("index.html", template)

    load_table("organisation", "var/cache/organisation.csv")

    for specification in ["intervention", "fund", "award"]:
        load_table(specification, f"specification/{specification}.csv")
