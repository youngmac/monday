from pathlib import Path
from order_utils import excel_to_dicts, group_data, sort_grouped_data
import sys
from datetime import datetime, date

def main():
    # Determine current directory based on execution context
    if getattr(sys, 'frozen', False):
        current_dir = Path(sys.executable).parent
    else:
        current_dir = Path('.')

    # Find Excel files (.xlsx and .xls) in current directory
    excel_files = list(current_dir.glob("*.xlsx")) + list(current_dir.glob("*.xls"))

    if len(excel_files) != 1:
        print("Error: Only one file allowed.")
        return

    # Single file processing
    data = excel_to_dicts(excel_files[0])
    grouped_data = group_data(data)
    sorted_grouped_data = sort_grouped_data(grouped_data)

    # ------------------- TOY/TOT REPORT -------------------
    # total = 0
    # match_total = 0
    # for key in sorted_grouped_data:
    #     for item in sorted_grouped_data[key]["items"]:
    #         if "toys" in item["title"].lower() or "tots" in item["title"].lower():
    #             print(f"{sorted_grouped_data[key]['username']}: {item['title']}: {item['price']}")
    #             total += item["price"]
    #             if "match" in item["title"].lower():
    #                 match_total += item["price"]
            
    # print(f"Match Total value of toys/tots: ${match_total:.2f}")
    # print(f"Total value of toys/tots: ${total:.2f}")
    



    # ------------------- GIVEAWAY -------------------
    target_date = date(2025, 11, 29)
    entries = []
    non_entries = []
    for key in sorted_grouped_data:
        for item in sorted_grouped_data[key]["items"]:
            dt = datetime.strptime(str(item['time']), "%Y-%m-%d %H:%M:%S")
            if dt.date() == target_date \
                and "hold" not in item["title"].lower() \
                and "heat pack" not in item["title"].lower() \
                and item["price"] > .99:
                entries.append("@" + str(sorted_grouped_data[key]["username"]))
    for entry in entries:
        print(entry)
    print("Total entries: " + str(len(entries)))

if __name__ == "__main__":
    main()