import urllib.request
import urllib.parse
import json
import csv
import os
import re
from datetime import date


# =========================================================
# SETTINGS
# =========================================================

PERMIT_API = (
    "https://data.cityofchicago.org/resource/e4xk-pud8.json"
    "?$limit=50000"
)

LICENSE_API = "https://data.cityofchicago.org/resource/r5kz-chrr.json"
OWNER_API = "https://data.cityofchicago.org/resource/ezma-pppn.json"

MEMORY_FILE = "seen_ids.txt"
TAVILY_API = "https://api.tavily.com/search"
# =========================================================
# TEST MODE
# =========================================================

TEST_MODE = (
    os.environ.get(
        "TEST_MODE",
        "false"
    ).lower()
    == "true"
)

TEST_PERMIT_COUNT = 50

# =========================================================
# HELPER: CALL A CHICAGO API
# =========================================================

def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ChicagoPermitTracker/1.0"}
    )

    response = urllib.request.urlopen(request, timeout=60)

    return json.loads(
        response.read().decode("utf-8")
    )


# =========================================================
# HELPER: CLEAN A COMPANY NAME
# =========================================================

def clean_name(name):
    if not name:
        return ""

    name = name.upper()

    # Replace punctuation with spaces
    name = re.sub(r"[^A-Z0-9 ]", " ", name)

    # Remove common business endings
    words_to_remove = {
        "INC",
        "INCORPORATED",
        "LLC",
        "LTD",
        "LIMITED",
        "CORP",
        "CORPORATION",
        "CO",
        "COMPANY"
    }

    words = [
        word
        for word in name.split()
        if word not in words_to_remove
    ]

    return " ".join(words)

# =========================================================
# HELPER: SEARCH THE WEB FOR BUSINESS CONTACT INFO
# =========================================================

def search_business_contact(business_name, business_address):

    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        print("    Tavily API key not available.")
        return {
            "website": "",
            "phone": "",
            "email": "",
            "source": ""
        }

    query = (
        '"'
        + business_name
        + '" '
        + '"'
        + business_address
        + '" '
        + '"official website"'
    )

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": 10,
        "include_answer": False,
        "exclude_domains": [
            "mapquest.com",
            "birdeye.com",
            "blackdirectory.com",
            "buildzoom.com",
            "junkyardslist.com",
            "yelp.com",
            "yellowpages.com",
            "bbb.org",
            "angi.com",
            "homeadvisor.com",
            "facebook.com",
            "linkedin.com",
            "instagram.com",
            "chamberofcommerce.com",
            "manta.com",
            "superpages.com"
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        TAVILY_API,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ChicagoPermitTracker/1.0"
        },
        method="POST"
    )

    try:

        response = urllib.request.urlopen(
            request,
            timeout=60
        )

        results = json.loads(
            response.read().decode("utf-8")
        )

    except Exception as error:

        print(
            "    Tavily search error:",
            error
        )

        return {
            "website": "",
            "phone": "",
            "email": "",
            "source": ""
        }

    website = ""
    source = ""
    best_score = -999

    bad_domains = [
        "mapquest.com",
        "blackdirectory.com",
        "buildzoom.com",
        "junkyardslist.com",
        "yelp.com",
        "yellowpages.com",
        "bbb.org",
        "angi.com",
        "homeadvisor.com",
        "facebook.com",
        "linkedin.com",
        "instagram.com",
        "chamberofcommerce.com",
        "manta.com",
        "superpages.com"
    ]

    business_words = set(
        business_name.lower()
        .replace(",", "")
        .replace(".", "")
        .replace("-", " ")
        .split()
    )
    address_words = (
        business_address
        .lower()
        .replace(",", "")
        .split()
    )

    for result in results.get("results", []):

        url = result.get("url", "")

        title = result.get(
            "title",
            ""
        )

        content = result.get(
            "content",
            ""
        )

        if not url:
            continue

        score = 0

        url_lower = url.lower()

        title_lower = title.lower()

        content_lower = content.lower()

        # -------------------------------------------------
        # Penalize known directories
        # -------------------------------------------------

        for domain in bad_domains:

            if domain in url_lower:

                score -= 20

        # -------------------------------------------------
        # Look at the business name
        # -------------------------------------------------

        for word in business_words:

            if len(word) >= 4:

                if word in title_lower:
                    score += 5

                if word in url_lower:
                    score += 4

                if word in content_lower:
                    score += 2

        # -------------------------------------------------
        # Look for the business address
        # -------------------------------------------------


        for word in address_words:

            if len(word) >= 4:

                if word in content_lower:

                    score += 3

        # -------------------------------------------------
        # Prefer normal company websites
        # -------------------------------------------------

        if (
            ".com" in url_lower
            or ".net" in url_lower
            or ".org" in url_lower
        ):

            score += 2

        # -------------------------------------------------
        # Penalize obvious directory language
        # -------------------------------------------------

        directory_words = [
            "directory",
            "listing",
            "listings",
            "reviews",
            "yellow pages",
            "mapquest",
            "contractor directory",
            "business directory"
        ]

        for word in directory_words:

            if word in title_lower:

                score -= 10

        # -------------------------------------------------
        # Keep the highest-scoring result
        # -------------------------------------------------

        if score > best_score:

            best_score = score

            website = url

            source = url

            print(
                "    Candidate website:",
                url,
                "Score:",
                score
            )
    print(
        "    Selected website:",
        website,
        "Score:",
        best_score
    )

    return {
        "website": website,
        "phone": "",
        "email": "",
        "source": source
    }
    
# =========================================================
# HELPER: FIND PUBLIC CONTACT INFO ON COMPANY WEBSITE
# =========================================================

def extract_website_contact_info(website):

    if not website:
        return {
            "phone": "",
            "email": ""
        }

    try:
        request = urllib.request.Request(
            website,
            headers={
                "User-Agent": "ChicagoPermitTracker/1.0"
            }
        )

        response = urllib.request.urlopen(
            request,
            timeout=20
        )

        html = response.read().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as error:

        print(
            "    Website lookup error:",
            error
        )

        return {
            "phone": "",
            "email": ""
        }

    # Look for a public business email address.
    email_match = re.search(
        r'[\w.+-]+@[\w-]+\.[\w.-]+',
        html
    )

    email = ""

    if email_match:
        email = email_match.group(0)

    # Look for a phone number.
    phone_match = re.search(
        r'(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}',
        html
    )

    phone = ""

    if phone_match:
        phone = phone_match.group(0)

    return {
        "phone": phone,
        "email": email
    }

# =========================================================
# HELPER: FIND BUSINESS LICENSE
# =========================================================

def find_business(contractor_name):

    if not contractor_name:
        return None

    cleaned = clean_name(contractor_name)

    if not cleaned:
        return None

    # Search Chicago's business database for the
    # most distinctive word(s) from the company name.
    words = cleaned.split()

    # Use the longest words first.
    words.sort(key=len, reverse=True)

    search_terms = words[:3]

    query = " ".join(search_terms)

    encoded_query = urllib.parse.quote(query)

    url = (
        LICENSE_API
        + "?$limit=20"
        + "&$q="
        + encoded_query
    )

    try:
        results = get_json(url)
    except Exception as error:
        print(
            "Business lookup error for",
            contractor_name,
            ":",
            error
        )
        return None

    if not results:
        return None

    # Try to find the best name match.
    best_result = None
    best_score = 0

    contractor_words = set(cleaned.split())

    for result in results:

        legal_name = clean_name(
            result.get("legal_name", "")
        )

        dba_name = clean_name(
            result.get("doing_business_as_name", "")
        )

        for business_name in [legal_name, dba_name]:

            if not business_name:
                continue

            business_words = set(
                business_name.split()
            )

            common_words = (
                contractor_words
                & business_words
            )

            score = len(common_words)

            if score > best_score:
                best_score = score
                best_result = result

    # Require at least one meaningful matching word.
    if best_result and best_score >= 1:
        return best_result

    return None


# =========================================================
# HELPER: FIND BUSINESS OWNER
# =========================================================

def find_owner(account_number):

    if not account_number:
        return []

    url = (
        OWNER_API
        + "?$limit=20"
        + "&account_number="
        + urllib.parse.quote(
            str(account_number)
        )
    )

    try:
        return get_json(url)
    except Exception as error:
        print(
            "Owner lookup error for account",
            account_number,
            ":",
            error
        )

        return []

# =========================================================
# TEMPORARY TAVILY TEST
# =========================================================

print()
print("Testing Tavily business search...")

test_contact = search_business_contact(
    "LEEWAY WRECKING INC",
    "4709 W KINZIE ST CHICAGO IL 60644"
)

print(
    "Tavily website:",
    test_contact.get("website", "")
)

print(
    "Tavily source:",
    test_contact.get("source", "")
)
website_contact = extract_website_contact_info(
    test_contact.get("website", "")
    )

print(
    "Tavily phone:",
    website_contact.get("phone", "")
    )

print(
    "Tavily email:",
    website_contact.get("email", "")
    )
print("Tavily test complete.")
print()
# =========================================================
# DOWNLOAD DEMOLITION PERMITS
# =========================================================

print("Connecting to Chicago's permit database...")

if TEST_MODE:

    test_api = (
        "https://data.cityofchicago.org/resource/e4xk-pud8.json"
        "?$limit="
        + str(TEST_PERMIT_COUNT)
        + "&$order=permit_%20DESC"
    )

    permits = get_json(test_api)

else:

    permits = get_json(PERMIT_API)

print(
    "Downloaded",
    len(permits),
    "permits"
)

# =========================================================
# LOAD MEMORY
# =========================================================

seen_ids = set()

if os.path.exists(MEMORY_FILE):

    with open(
        MEMORY_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            permit_id = line.strip()

            if permit_id:
                seen_ids.add(permit_id)


print(
    "Already seen:",
    len(seen_ids)
)


# =========================================================
# FIND NEW PERMITS
# =========================================================

# =========================================================
# SELECT PERMITS TO PROCESS
# =========================================================

if TEST_MODE:

    new_permits = permits.copy()

    print(
        "TEST MODE: Processing",
        len(new_permits),
        "permits."
    )

else:

    new_permits = []

    for permit in permits:

        permit_id = permit.get("id")

        if permit_id and permit_id not in seen_ids:

            new_permits.append(permit)

            seen_ids.add(permit_id)


print(
    "New permits:",
    len(new_permits)
)


# =========================================================
# PROCESS NEW PERMITS
# =========================================================

if new_permits:

    if TEST_MODE:

        filename = (
            "TEST_50_permits_"
            + str(date.today())
            + ".csv"
        )

    else:

        filename = (
            "new_permits_"
            + str(date.today())
            + ".csv"
        )

    output_rows = []

    for permit in new_permits:

        print()
        print(
            "Processing permit:",
            permit.get("permit_", "")
        )
        # -------------------------------------------------
        # Basic permit information
        # -------------------------------------------------

        street_parts = [
            permit.get("street_number", ""),
            permit.get("street_direction", ""),
            permit.get("street_name", "")
        ]

        address = " ".join(
            part
            for part in street_parts
            if part
        )

        # -------------------------------------------------
        # Find contractors
        # -------------------------------------------------

        contractors = []

        for number in range(1, 16):

            prefix = (
                "contact_"
                + str(number)
                + "_"
            )

            contact_type = permit.get(
                prefix + "type",
                ""
            )

            contact_name = permit.get(
                prefix + "name",
                ""
            )

            if not contact_name:
                continue

            # Only treat non-owner contacts as contractors.
            if "OWNER" not in contact_type.upper():

                contractors.append(
                    (
                        contact_name,
                        contact_type
                    )
                )

        # -------------------------------------------------
        # Find property owners
        # -------------------------------------------------

        property_owners = []

        for number in range(1, 16):

            prefix = (
                "contact_"
                + str(number)
                + "_"
            )

            contact_type = permit.get(
                prefix + "type",
                ""
            )

            contact_name = permit.get(
                prefix + "name",
                ""
            )

            if (
                contact_name
                and "OWNER"
                in contact_type.upper()
            ):

                property_owners.append(
                    contact_name
                )

        # -------------------------------------------------
        # If there are no contractors
        # -------------------------------------------------

        if not contractors:

            contractors = [
                ("", "")
            ]

        # -------------------------------------------------
        # Look up each contractor
        # -------------------------------------------------

        for contractor_name, contractor_type in contractors:

            print(
                "  Contractor:",
                contractor_name
            )

            business = find_business(
                contractor_name
            )

            business_account = ""
            business_name = ""
            business_dba = ""
            business_address = ""
            business_city = ""
            business_state = ""
            business_zip = ""
            
            business_website = ""
            business_phone = ""
            business_email = ""
            contact_source = ""

            owner_names = []
            owner_titles = []

            match_status = "NO MATCH"

            if business:

                match_status = "MATCHED"

                business_account = business.get(
                    "account_number",
                    ""
                )

                business_name = business.get(
                    "legal_name",
                    ""
                )

                business_dba = business.get(
                    "doing_business_as_name",
                    ""
                )

                business_address = business.get(
                    "address",
                    ""
                )

                business_city = business.get(
                    "city",
                    ""
                )

                business_state = business.get(
                    "state",
                    ""
                )

                business_zip = business.get(
                    "zip_code",
                    ""
                )

                print(
                    "    Business:",
                    business_name
                )

                print(
                    "    Account:",
                    business_account
                )
                contact_info = search_business_contact(
                    business_name,
                    business_address
                )

                business_website = contact_info.get(
                    "website",
                    ""
                )

                website_contact = extract_website_contact_info(
                    business_website
                )

                if website_contact.get("phone"):
                    contact_info["phone"] = website_contact["phone"]

                if website_contact.get("email"):
                    contact_info["email"] = website_contact["email"]

                business_phone = contact_info.get(
                    "phone",
                    ""
                )

                business_email = contact_info.get(
                    "email",
                    ""
                )

                contact_source = contact_info.get(
                    "source",
                    ""
                )

                if business_website:
                    print(
                        "    Website:",
                        business_website
                    )

                owners = find_owner(
                    business_account
                )

                for owner in owners:

                    first = owner.get(
                        "owner_first_name",
                        ""
                    )

                    middle = owner.get(
                        "owner_middle_initial",
                        ""
                    )

                    last = owner.get(
                        "owner_last_name",
                        ""
                    )

                    entity = owner.get(
                        "owner_name",
                        ""
                    )

                    title = owner.get(
                        "owner_title",
                        ""
                    )

                    if first or last:

                        name_parts = [
                            first,
                            middle,
                            last
                        ]

                        owner_names.append(
                            " ".join(
                                part
                                for part in name_parts
                                if part
                            )
                        )

                    elif entity:

                        owner_names.append(
                            entity
                        )

                    if title:

                        owner_titles.append(
                            title
                        )

            # -------------------------------------------------
            # Create output row
            # -------------------------------------------------

            row = {

                "permit_id":
                    permit.get("id", ""),

                "permit_number":
                    permit.get("permit_", ""),

                "permit_type":
                    permit.get("permit_type", ""),

                "address":
                    address,

                "work_description":
                    permit.get(
                        "work_description",
                        ""
                    ),

                "property_owner":
                    "; ".join(
                        property_owners
                    ),
                "lead_type":
                    "PROPERTY_OWNER"
                    if property_owners
                    else "",

                "contractor_name":
                    contractor_name,

                "contractor_type":
                    contractor_type,

                "business_match":
                    match_status,

                "business_name":
                    business_name,

                "business_dba":
                    business_dba,

                "business_account":
                    business_account,

                "business_address":
                    business_address,

                "business_city":
                    business_city,

                "business_state":
                    business_state,

                "business_zip":
                    business_zip,
                
                "business_website":
                    business_website,

                "business_phone":
                    business_phone,

                "business_email":
                    business_email,

                "contact_source":
                    contact_source,

                "business_owner":
                    "; ".join(
                        dict.fromkeys(
                            owner_names
                        )
                    ),

                "owner_title":
                    "; ".join(
                        dict.fromkeys(
                            owner_titles
                        )
                    ),

                "latitude":
                    permit.get(
                        "latitude",
                        ""
                    ),

                "longitude":
                    permit.get(
                        "longitude",
                        ""
                    )
            }

            output_rows.append(row)


    # =====================================================
    # WRITE CSV
    # =====================================================

    fields = [

        "permit_id",
        "permit_number",
        "permit_type",
        "address",
        "work_description",

        "property_owner",
        "lead_type",

        "contractor_name",
        "contractor_type",

        "business_match",
        "business_name",
        "business_dba",
        "business_account",

        "business_address",
        "business_city",
        "business_state",
        "business_zip",
        
        "business_website",
        "business_phone",
        "business_email",
        "contact_source",

        "business_owner",
        "owner_title",

        "latitude",
        "longitude"
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

        writer.writerows(
            output_rows
        )

    print()
    print(
        "Saved:",
        filename
    )

else:

    print(
        "No new permits today."
    )


# =========================================================
# SAVE MEMORY
# =========================================================

with open(
    MEMORY_FILE,
    "w",
    encoding="utf-8"
) as file:

    for permit_id in sorted(seen_ids):

        file.write(
            permit_id + "\n"
        )


print(
    "Memory updated."
)

print(
    "Done!"
)
