import urllib.request
import json
import csv
import os
from datetime import date

# Ask Chicago for the permits
url = "https://data.cityofchicago.org/resource/e4xk-pud8.json?$limit=50000"

response = urllib.request.urlopen(url)
data = json.loads(response.read().decode("utf-8"))

print("Downloaded", len(data), "permits")

# Load permits we've already seen
seen_ids = set()

if os.path.exists("seen_ids.txt"):
    with open("seen_ids.txt", "r") as file:
        for line in file:
            seen_ids.add(line.strip())

# Find permits we haven't seen before
new_permits = []

for permit in data:
    permit_id = permit.get("id")

    if permit_id and permit_id not in seen_ids:
        new_permits.append(permit)
        seen_ids.add(permit_id)

print("New permits:", len(new_permits))

# Save new permits
if new_permits:

    filename = "new_permits_" + str(date.today()) + ".csv"

    # Find EVERY field used by ANY permit
    all_fields = set()

    for permit in new_permits:
        all_fields.update(permit.keys())

    # Put the columns in alphabetical order
    fields = sorted(all_fields)

    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(new_permits)

    print("Saved new permits to", filename)

# Remember all permits we've seen
with open("seen_ids.txt", "w") as file:
    for permit_id in seen_ids:
        file.write(permit_id + "\n")

print("Memory updated.")