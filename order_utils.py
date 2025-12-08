from datetime import datetime
from openpyxl import load_workbook
from pathlib import Path
from collections import Counter
from predicates import is_important, is_tc, is_plant, could_be_tc, could_be_plant, is_any_plant, is_future_hold


def excel_to_dicts(file_path: Path):
    """Reads an Excel file and converts it to a list of dictionaries."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    wb = load_workbook(filename=file_path, data_only=True)
    sheet = wb.active
    headers = [cell.value for cell in sheet[1]]

    data = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        row_dict = dict(zip(headers, row))
        data.append(row_dict)

    return data


def name_address_to_key(row: dict) -> str:
    """
    Generates a unique key for each recipient based on name and address.
    Does not handle typos, abbreviations, or inconsistencies.
    """
    return (
        (row.get("Recipient Name") or "").lower().strip() + "_" +
        (row.get("Street Line 1") or "").lower().strip() + "_" +
        (row.get("Street Line 2") or "").lower().strip() + "_" +
        (row.get("State") or "").lower().strip() + "_" +
        (row.get("Country") or "").lower().strip() + "_" +
        (row.get("Zip/Postal Code") or "").lower().strip()
    )


def group_data(data: list[dict]) -> tuple[dict, dict]:
    """
    Groups rows by recipient's name and address.
    Combines items with the same title by summing quantity.
    Detects conflicts where the same username maps to multiple addresses or vice versa.
    Does NOT normalize addresses.
    
    Returns:
        grouped_data: normal grouped data
        conflicts: {
            "address_conflicts": {address: set(usernames)},
            "username_conflicts": {username: set(addresses)}
        }
    """
    grouped_data = {}

    # Track username/address relationships for conflict detection
    address_to_usernames = {}
    username_to_addresses = {}

    for row in data:
        key = name_address_to_key(row)

        username = row.get("Palmstreet UserName") or ""
        street_1 = row.get("Street Line 1") or ""
        street_2 = row.get("Street Line 2") or ""
        city = row.get("City") or ""
        state = row.get("State") or ""
        zip_code = row.get("Zip/Postal Code") or ""

        # Construct full address for conflict tracking (no normalization)
        address = f"{street_1}, " + (f"{street_2}, " if street_2 else "") + f"{city}, {state} {zip_code}"

        # Track conflicts
        address_to_usernames.setdefault(address, set()).add(username)
        username_to_addresses.setdefault(username, set()).add(address)

        # --- Group items ---
        title = row.get("Item Title") or ""
        price = float(row.get("Item Price") or 0)
        quantity = int(row.get("Quantity") or 0)
        time = row.get("Order Date(PDT)") or ""

        if key not in grouped_data:
            grouped_data[key] = {
                "name": row.get("Recipient Name") or "",
                "username": username,
                "address": address,
                "state": state,
                "items": {},
            }

        items = grouped_data[key]["items"]
        if title in items:
            items[title]["quantity"] += quantity
            items[title]["price"] += price * quantity
            if time > items[title]["time"]:
                items[title]["time"] = time
        else:
            items[title] = {
                "title": title,
                "price": price * quantity,
                "quantity": quantity,
                "time": time,
            }

    # Convert items dicts to lists
    for key in grouped_data:
        grouped_data[key]["items"] = list(grouped_data[key]["items"].values())

    # Build conflicts: only keep entries with more than one unique mapping
    address_conflicts = {addr: users for addr, users in address_to_usernames.items() if len(users) > 1}
    username_conflicts = {user: addrs for user, addrs in username_to_addresses.items() if len(addrs) > 1}

    conflicts = {
        "address_conflicts": address_conflicts,
        "username_conflicts": username_conflicts,
    }

    return grouped_data, conflicts


def get_date_range(grouped_data: dict) -> tuple[datetime | None, datetime | None]:
    """Returns the earliest and latest order dates across all grouped items."""
    min_date = None
    max_date = None

    for group in grouped_data.values():
        for item in group['items']:
            try:
                dt = datetime.strptime(str(item['time']), "%Y-%m-%d %H:%M:%S")
                if not min_date or dt < min_date:
                    min_date = dt
                if not max_date or dt > max_date:
                    max_date = dt
            except Exception:
                continue

    return min_date, max_date



def sort_grouped_data(grouped_data):
    """
    Sorts grouped order data by size (desc) and name (asc), then assigns a UID to each group.

    Args:
        grouped_data (dict): Customer groups keyed by address info.

    Returns:
        dict: Sorted data with 'uid' assigned to each group.
    """
    def item_count(data):
        return len(data)

    def earliest_date(data):
        dates = []
        for item in data:
            try:
                dates.append(datetime.strptime(str(item['time']), '%Y-%m-%d %H:%M:%S'))
            except:
                continue
        return min(dates) if dates else datetime.max

    def get_sort_key_func(key):
        if key == "Name":
            return lambda x: x[1]["name"].lower()
        elif key == "Username":
            return lambda x: x[1]["username"].lower()
        elif key == "Size":
            return lambda x: item_count(x[1]["items"])
        elif key == "Earliest Order Date":
            return lambda x: earliest_date(x[1]["items"])
        else:
            return None

    data = list(grouped_data.items())

    # Apply sorting from lowest to highest priority (reversed)
    for key, order in reversed(list(zip(["Size", "Name"], ["Descending", "Ascending"]))):
        key_func = get_sort_key_func(key)
        if key_func:
            reverse = order == "Descending"
            data.sort(key=key_func, reverse=reverse)

    # Assign UID after sorting
    for i, (key, value) in enumerate(data):
        value["uid"] = i + 1

        # Sort items: "hold" or "cancel" first, then by title
        value["items"].sort(
            key=lambda item: (
                0 if is_important(item["title"]) else
                1 if is_tc(item["title"]) else
                2 if could_be_tc(item["title"]) else
                3 if is_plant(item["title"]) else
                4 if could_be_plant(item["title"]) else
                5, item["title"].lower()
            ))

    return dict(data)

# input data sorted according to sort_grouped_data function
def aggregate_data(data):
    aggregate = {}
    plants = []
    holds = {}
    for key, order in data.items():
        for item in order["items"]:
            title = item["title"].lower()
            potential_hold, hold_text = is_future_hold(title, item["time"])
            if potential_hold != None:
                holds[key] = {"date": potential_hold, "text": hold_text, "name": order["username"], "address": order["address"]}
            if is_any_plant(title):
                plants.append(title)
                continue
            elif title in aggregate:
                aggregate[title] += item["quantity"]
            else:
                aggregate[title] = item["quantity"]


    counts = Counter(plants)
    dupl_plants = {plant: count for plant, count in counts.items() if count > 1}
    plants = [plant for plant in plants if counts[plant] == 1]

    for plant in dupl_plants:
        aggregate[plant] = dupl_plants[plant]

    sorted_data = dict(sorted(
        aggregate.items(),
        key=lambda item: (-item[1], item[0].lower())  # sort by count DESC, then name ASC
    ))

    sorted_plants = sorted(
        plants,
        key=lambda name: (
            is_tc(name),    # sort tc first (True -> 1 -> -1 for descending)
            could_be_tc(name),
            is_plant(name),
            could_be_plant(name),
            name.lower()
        )
    )

    return sorted_data, sorted_plants, holds