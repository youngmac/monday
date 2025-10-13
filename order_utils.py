from datetime import datetime
from openpyxl import load_workbook
from pathlib import Path


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


def group_data(data: list[dict]) -> dict:
    """
    Groups rows by recipient's name and address.
    Assumes prices are in USD and ignores variants/SKUs.
    """
    grouped_data = {}

    for row in data:
        key = name_address_to_key(row)

        item = {
            "title": (row.get("Item Title") or ""),
            "price": (row.get("Item Price") or 0),
            "quantity": (row.get("Quantity") or 0),
            "time": (row.get("Order Date(PDT)") or ""),
        }

        if key not in grouped_data:
            street_2 = (row.get("Street Line 2") or "")
            address = (
                (row.get("Street Line 1") or "") + ", " +
                (street_2 + ", " if street_2 else "") +
                (row.get("City") or "") + ", " +
                (row.get("State") or "") + " " +
                (row.get("Zip/Postal Code") or "")
            )

            grouped_data[key] = {
                "name": (row.get("Recipient Name") or ""),
                "username": (row.get("Palmstreet UserName") or ""),
                "address": address,
                "items": [item],
            }
        else:
            grouped_data[key]["items"].append(item)

    return grouped_data


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

    from datetime import datetime

def sort_grouped_data(grouped_data):
    def item_count(items):
        return len(items)

    def earliest_date(items):
        dates = []
        for item in items:
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

    items = list(grouped_data.items())

    # Apply sorting from lowest to highest priority (reversed)
    for key, order in reversed(list(zip(["Size", "Name"], ["Descending", "Ascending"]))):
        key_func = get_sort_key_func(key)
        if key_func:
            reverse = order == "Descending"
            items.sort(key=key_func, reverse=reverse)

    # Assign UID after sorting
    for i, (key, value) in enumerate(items):
        value["uid"] = i + 1

    return dict(items)
