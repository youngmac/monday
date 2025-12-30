import re
from datetime import date, timedelta, datetime
from dateutil import parser
import calendar


# item titles 
# handles upper/lower case



def is_important(title):
    title = title.lower()
    if "heat" in title and "pack" in title:
        return True
    important_words = ["hold", "cancel", "ups", "next", "2-day", "2 day"
                       , "overnight", "express", "priority", "hook me up"
                       , "insulation", "cryo", "mystery", "ship"]
    return any(word in title.lower() for word in important_words)

def is_gear(title):
    title = title.lower()
    return (
        "100g" in title
        or "500 ml" in title
        or "500ml" in title
        or "1000 ml" in title
        or"1000ml" in title
        or "acclimation" in title
    )

def is_tc(title):
    title = title.lower()
    return (
        ((bool(re.search(r'\d{3,4}', title))
        and " tc" in title
        and not is_gear(title)
        and title != "basic tc acclimation kit"))
        and "acclimation mix" not in title
        or (bool(re.search(r'\d{3,4}', title)) and ("5 pack" in title or "10 pack" in title))
        or bool(re.fullmatch(r"0[1-9]", title))
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
    return ("in 2”" in title and not is_gear(title)) or ("monstera" in title and "pot" not in title)

def is_any_plant(title):
    title = title.lower()
    return is_tc(title) or is_plant(title) or could_be_tc(title) or could_be_plant(title)

def is_future_hold(text_in: str, purchase_date):
    # return None, None
    now = datetime.now()
    today = now.date()
    def can_hold(hold_date):
        weekday = now.weekday()  # Monday = 0, Sunday = 6

        # Determine the "comparison date" based on time and weekday
        if weekday < 5:  # Monday–Friday
            if now.hour < 17:  # Before 5 PM
                comparison_date = today
            else:  # After 5 PM
                comparison_date = today + timedelta(days=1)
        else:  # Weekend (Saturday or Sunday)
            # Days until next Monday
            days_until_monday = (7 - weekday)
            comparison_date = today + timedelta(days=days_until_monday)
        print(f"Comparison date: {comparison_date}, Hold date: {hold_date}")
        print(type(hold_date), type(comparison_date))
        return comparison_date < hold_date


    text = text_in.lower()

    # hardcoded case
    dates = re.findall(r'\b\d{1,2}[-/]\d{1,2}\b', text)
    converted_dates = []

    for d in dates:
        # Normalize separator to "/"
        d_clean = d.replace('-', '/')
        month, day = map(int, d_clean.split("/"))

        year = today.year
        candidate = date(year, month, day)

        # Only roll forward for December → January cases
        if (
            today.month == 12 and    # we're in December
            month == 1 and           # parsed month is January
            candidate < today        # this year's Jan date has passed
        ):
            candidate = date(year + 1, month, day)

        converted_dates.append(candidate)

    print(f"Text: {text}")
    print(f"Converted dates: {converted_dates}")
    for d in converted_dates:
        print(f"Checking can_hold({d}) = {can_hold(d)}")

    if "hold" in text and converted_dates and can_hold(converted_dates[0]):
        print("Returning:", converted_dates[0], text_in)
        return converted_dates[0], text_in
    else:
        print("No match, returning None, None")
        return None, None

    