import re
from datetime import date, timedelta, datetime
from dateutil import parser
import calendar


# item titles 
# handles upper/lower case



def is_important(title):
    important_words = ["hold", "cancel", "ups", "next", "2-day", "2 day"
                       , "overnight", "express", "priority", "hook me up"
                       , "heat", "insulation", "cryo", "mystery"]
    return any(word in title.lower() for word in important_words)

def is_gear(title):
    title = title.lower()
    return (
        "100g" in title
        or "500 ml" in title
        or "500ml" in title
        or "1000 ml" in title
        or"1000ml" in title
    )

def is_tc(title):
    title = title.lower()
    return (
        ((bool(re.search(r'\d{3,4}', title))
        and " tc" in title
        and not is_gear(title)
        and title != "basic tc acclimation kit"))
        or (bool(re.search(r'\d{3,4}', title)) and ("5 pack" in title or "10 pack" in title))
    )

def is_plant(title):
    title = title.lower()
    return (
        bool(re.search(r'\d{3,4}', title))
        and "tc" not in title
        and not is_gear(title)
    )

def could_be_tc(title):
    title = title.lower()
    return "tc" in title and not is_gear(title)

def could_be_plant(title):
    title = title.lower()
    return "in 2” pot" in title and not is_gear(title)

def is_any_plant(title):
    title = title.lower()
    return is_tc(title) or is_plant(title) or could_be_tc(title) or could_be_plant(title)

def is_future_hold(text_in: str, purchase_date):
    """
    Extract a 'hold until' date from text relative to a purchase date.

    Returns a datetime.date if a valid hold date is found that is at least:
      - 2 days in the future if current time < 4pm
      - 1 day in the future if current time >= 4pm
    Otherwise returns None.
    """
    # --- Normalize purchase_date ---
    if isinstance(purchase_date, str):
        try:
            purchase_date = parser.parse(purchase_date).date()
        except Exception:
            return None, None
    elif isinstance(purchase_date, datetime):
        purchase_date = purchase_date.date()
    elif not isinstance(purchase_date, date):
        return None, None # invalid input type

    text = text_in.lower().strip()
    now = datetime.now()
    if "hold" not in text:
        return None, None

    # Determine what counts as "future"
    if now.hour < 16:  # before 4pm
        future_threshold = now.date() + timedelta(days=2)
    else:               # after 4pm
        future_threshold = now.date() + timedelta(days=1)

    # Patterns for explicit dates
    date_patterns = [
        r'(\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)',    # e.g. 9/29, 9-29-24, 11/3
        r'(\b\d{1,2}(?:st|nd|rd|th)?\s*[a-z]{3,9})',  # e.g. 18th feb, 5th september
    ]

    # --- Try explicit date formats first ---
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            try:
                parsed = parser.parse(
                    date_str,
                    fuzzy=True,
                    default=datetime.combine(purchase_date, datetime.min.time())
                )
                hold_date = parsed.date()

                if hold_date >= future_threshold:
                    return hold_date, text_in
            except Exception:
                continue  # try next pattern

    # --- Try weekday names (full and abbreviated) ---
    weekdays = {day.lower(): i for i, day in enumerate(calendar.day_name)}
    weekdays.update({day[:3].lower(): i for i, day in enumerate(calendar.day_name)})

    found_day = next((w for w in weekdays if w in text), None)
    if found_day:
        target_wd = weekdays[found_day]
        days_ahead = (target_wd - purchase_date.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7  # same weekday → next week
        hold_date = purchase_date + timedelta(days=days_ahead)

        if hold_date >= future_threshold:
            return hold_date, text_in

    # Nothing valid found
    return None, None
    