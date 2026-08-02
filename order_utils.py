from datetime import datetime
import config
from openpyxl import load_workbook
from pathlib import Path
from collections import Counter
from est_transit_times import ShippingTransitTime
from predicates import is_important, is_tc, is_plant, could_be_tc, could_be_plant, is_any_plant, is_future_hold, is_2_day, is_next_day
from config import TWO_DAY_SHIP_COST, FIRST_ITEM_SHIP_COST, ADDITIONAL_ITEM_SHIP_COST, NEXT_DAY_SHIP_COST


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


def group_data(data: list[dict], shipping_transit_time: ShippingTransitTime) -> tuple[dict, dict]:
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

        # skip all non ready to ship orders
        order_status = row.get("Order Status") or "Ready to Ship"
        if order_status != "Ready to Ship":
            continue


        # Construct full address for conflict tracking (no normalization)
        address = f"{street_1}, " + (f"{street_2}, " if street_2 else "") + f"{city}, {state} {zip_code}"

        # Track conflicts
        address_to_usernames.setdefault(address, set()).add(username)
        username_to_addresses.setdefault(username, set()).add(address)

        # --- Group items ---
        title = row.get("Item Title") or ""
        # Mothers day line too long
        if "!!" in title and title.startswith("Mothers"):
            title = "!!" + title.split("!!", 1)[-1]
        price = float(row.get("Item Price") or 0)
        quantity = int(row.get("Quantity") or 0)
        time = row.get("Order Date(PDT)") or ""

        if key not in grouped_data:
            grouped_data[key] = {
                "name": row.get("Recipient Name") or "",
                "username": username,
                "address": address,
                # "zip": zip_code,
                # "city": city,
                "state": state,
                "items": {},
            }

        if "2day" not in grouped_data[key]:
            grouped_data[key]["2day"] = False
        if is_2_day(title):
            grouped_data[key]["2day"] = True
        if "1day" not in grouped_data[key]:
            grouped_data[key]["1day"] = False
        if is_next_day(title):
            grouped_data[key]["1day"] = True

        if "transit_times" not in grouped_data[key]:
            print(f"Fetching transit times for {username} at {zip_code}...")
            grouped_data[key]["transit_times"] = shipping_transit_time.get_all_transit_times(config.ORIGIN_ZIP, zip_code, city, state)

        items = grouped_data[key]["items"]
        if title in items:
            items[title]["quantity"] += quantity
            items[title]["price"] += price * quantity
            if time > items[title]["time"]:
                items[title]["time"] = time
        else:
            items[title] = {
                "title": title,
                "price": price,
                "quantity": quantity,
                "time": time,
            }

    # Calculate costs
    for key in grouped_data:
        subtotal = 0.0
        plant_cost = 0.0
        ship_cost = 0.0
        for item_key in grouped_data[key]["items"]:
            item = grouped_data[key]["items"][item_key]

            item["price"] /= item["quantity"]

            # plant/subtotal
            subtotal += item.get('price', 0.0) * item.get('quantity', 1)
            if is_any_plant(item["title"]):
                plant_cost += item.get('price', 0.0) * item.get('quantity', 1)

            # shipping
            if item.get('price', 0.0) > .99:
                if ship_cost <= 0.01:
                    ship_cost += FIRST_ITEM_SHIP_COST
                    if item["quantity"] > 1:
                        ship_cost += ADDITIONAL_ITEM_SHIP_COST * item["quantity"] - 1
                else:
                    ship_cost += ADDITIONAL_ITEM_SHIP_COST * item["quantity"]

        # 2-day / 1-day special case
        if grouped_data[key]["2day"]:
                ship_cost += TWO_DAY_SHIP_COST
                subtotal -= TWO_DAY_SHIP_COST
        if grouped_data[key]["1day"]:
            ship_cost += NEXT_DAY_SHIP_COST
            subtotal -= NEXT_DAY_SHIP_COST

        grouped_data[key]["costs"] = {}    
        grouped_data[key]["costs"]["subtotal"] = round(subtotal, 2)
        grouped_data[key]["costs"]["plant_cost"] = round(plant_cost, 2)
        grouped_data[key]["costs"]["ship_cost"] = round(ship_cost, 2)
        grouped_data[key]["costs"]["total_cost"] = round(subtotal + ship_cost, 2)

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
        # return len(data) (kept for compatibility legacy, don't use unless you have to)
        total = 0
        for item in data:
            total += item.get("quantity", 0)
        return total
        

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
        elif key == "Time in Transit":
            return lambda x: x[1]["transit_times"].get("ups_ground", float('inf'))
        else:
            return None

    data = list(grouped_data.items())

    # Apply sorting from lowest to highest priority (reversed)
    for key, order in reversed(list(zip(["Time in Transit","Size", "Name"], ["Descending", "Descending", "Ascending"]))):
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
    plants = {}   # plant_name -> price
    holds = {}

    for key, order in data.items():
        for item in order["items"]:
            title = item["title"].lower()
            potential_hold, hold_text = is_future_hold(title, item["time"])
            if potential_hold is not None:
                holds[key] = {
                    "date": potential_hold,
                    "text": hold_text,
                    "name": order["username"],
                    "address": order["address"],
                    "items": order["items"],
                }

            if is_any_plant(title):
                plants[title] = item["price"]
                continue

            aggregate[title] = aggregate.get(title, 0) + item["quantity"]

    # Count plant duplicates
    plant_counts = Counter(plants.keys())

    # Plants appearing more than once go into aggregate
    for plant, count in plant_counts.items():
        if count > 1:
            aggregate[plant] = count

    # Keep only unique plants in the plants dict
    plants = {
        plant: price
        for plant, price in plants.items()
        if plant_counts[plant] == 1
    }

    # Sort aggregate
    sorted_data = dict(
        sorted(
            aggregate.items(),
            key=lambda item: (-item[1], item[0].lower())
        )
    )

    # Sort plants (still a dict!)
    sorted_plants = dict(
        sorted(
            plants.items(),
            key=lambda item: (
                # is_tc(item[0]),
                # could_be_tc(item[0]),
                # is_plant(item[0]),
                # could_be_plant(item[0]),
                item[0].lower(),
            )
        )
    )

    return sorted_data, sorted_plants, holds