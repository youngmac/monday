import re


# item titles 
# handles upper/lower case


def is_important(title):
    important_words = ["hold", "cancel", "ups", "2-day", "2 day", "overnight", "express", "priority", "hook me up"]
    return any(word in title.lower() for word in important_words)

def is_tc(title):
    title = title.lower()
    return (bool(re.search(r'\d{4}', title)) or " tc" in title) and title != "basic tc acclimation kit"

def is_plant(title):
    title = title.lower()
    return (bool(re.search(r'\d{4}', title)) and " tc" not in title) and title != "basic tc acclimation kit"

def could_be_tc(title):
    title = title.lower()
    return "tc" in title

def could_be_plant(title):
    title = title.lower()
    return "in 2” pot" in title

def is_any_plant(title):
    title = title.lower()
    return is_tc(title) or is_plant(title) or could_be_tc(title) or could_be_plant(title) 