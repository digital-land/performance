import os
import sys
from jinja2 import Environment, FileSystemLoader


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
