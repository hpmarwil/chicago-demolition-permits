import urllib.request
import json
import csv
import os
from datetime import date


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

API_URL = (
    "https://data.cityofchicago.org/resource/e4xk-pud8.json"
    "?$limit=50000"
)

MEMORY_FILE = "seen_ids.txt"


# ---------------------------------------------------------
# DOWNLOAD PERMITS
# ---------------------------------------------------------

print("Connecting to Chicago's permit database...")

response = urllib.request.urlopen(API_URL)
data = json.loads(response.read().decode("utf-8"))

print("Downloaded", len(data), "permits")


# ---------------------------------------------------------
# LOAD OUR MEMORY
# ---------------------------------------------------------

seen_ids = set()

if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r", encoding="utf-8") as file:
        for line in file:
            permit_id = line.strip()

            if permit_id:
                seen_ids.add(permit_id)

print("Already seen:", len(seen_ids))


# ---------------------------------------------------------
# FIND NEW PERMITS
# ---------------------------------------------------------

new_permits = []

for permit in data:

    permit_id = permit.get("id")

    if permit_id and permit_id not in seen_ids:
        new_permits.append(permit)
        seen_ids.add(permit_id)


print("New permits:", len(new_permits))


# ---------------------------------------------------------
# CREATE A CLEAN DAILY FILE
# ---------------------------------------------------------

if new_permits:

    filename = "new_permits_" + str(date.today()) + ".csv"

    clean_permits = []

    for permit in new_permits:

        # Basic property information
        clean = {
            "permit_id": permit.get("id", ""),
            "permit_number": permit.get("permit_", ""),
            "permit_type": permit.get("permit_type", ""),
            "street_number": permit.get("street_number", ""),
            "street_direction": permit.get("street_direction", ""),
            "street_name": permit.get("street_name", ""),
            "work_description": permit.get("work_description", ""),
            "latitude": permit.get("latitude", ""),
            "longitude": permit.get("longitude", ""),
        }

        # -------------------------------------------------
        # Find the owner and contractor information
        # -------------------------------------------------

        owner_names = []
        contractor_names = []
        contractor_types = []
        contact_addresses = []

        # Chicago sometimes has contact_1, contact_2,
        # contact_3, etc.
        for number in range(1, 16):

            prefix = "contact_" + str(number) + "_"

            contact_type = permit.get(prefix + "type", "")
            contact_name = permit.get(prefix + "name", "")
            contact_city = permit.get(prefix + "city", "")
            contact_state = permit.get(prefix + "state", "")
            contact_zip = permit.get(prefix + "zipcode", "")

            if not contact_name:
                continue

            # Save the complete contact information
            address_parts = [
                contact_city,
                contact_state,
                contact_zip
            ]

            address = ", ".join(
                part for part in address_parts if part
            )

            contact_addresses.append(
                contact_name + " | " + address
            )

            # Separate owners from contractors
            if "OWNER" in contact_type.upper():
                owner_names.append(contact_name)

            else:
                contractor_names.append(contact_name)
                contractor_types.append(contact_type)

        clean["property_owner"] = "; ".join(owner_names)
        clean["contractor_name"] = "; ".join(contractor_names)
        clean["contractor_type"] = "; ".join(contractor_types)

        clean["all_contacts"] = " || ".join(contact_addresses)

        clean_permits.append(clean)


    # -----------------------------------------------------
    # WRITE CSV
    # -----------------------------------------------------

    fields = [
        "permit_id",
        "permit_number",
        "permit_type",
        "street_number",
        "street_direction",
        "street_name",
        "work_description",
        "property_owner",
        "contractor_name",
        "contractor_type",
        "all_contacts",
        "latitude",
        "longitude",
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(clean_permits)

    print("Saved:", filename)

else:

    print("No new permits today.")


# ---------------------------------------------------------
# SAVE OUR MEMORY
# ---------------------------------------------------------

with open(MEMORY_FILE, "w", encoding="utf-8") as file:

    for permit_id in sorted(seen_ids):
        file.write(permit_id + "\n")


print("Memory updated.")
print("Done!")
