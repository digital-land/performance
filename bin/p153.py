#!/usr/bin/env python3

import sys
import csv
import pandas as pd


organisations = {
    # patched for now ..
    "E51000005": "development-corporation:Q115585981",
    "E51000006": "development-corporation:Q117149370",
    "E51000007": "development-corporation:Q124604981",
    "E26000008": "national-park-authority:Q27178932",
    "E26000011": "national-park-authority:Q27159704",
    "E26000012": "national-park-authority:Q27178932",
}


def add_organisation(reference, row):
    if row.get(reference, ""):
        organisations[row[reference]] = row["organisation"]


for row in csv.DictReader(open("var/cache/organisation.csv", newline="")):
    add_organisation("local-authority-district", row)
    add_organisation("local-planning-authority", row)
    add_organisation("statistical-geography", row)


# Read a specific sheet into dataframe
df=pd.read_excel(sys.argv[1], sheet_name=1, skiprows=19, skipfooter=15)

df.columns.values[0] = "name"
df.columns.values[1] = "reference"
df.columns.values[50] = "volume"
df.columns.values[57] = "percentage"

for index, row in df.iterrows():
    df.loc[index, 'organisation'] = organisations[row["reference"]]
    df.loc[index, "volume"] = str(row["volume"]).replace("~", "")
    df.loc[index, "percentage"] = str(row["percentage"]).replace("-", "")

df.to_csv(sys.argv[2], header=True, index=False, columns=["organisation", "reference", "name", "volume", "percentage"])
