import pandas as pd

from helpers import find_schedule_conflicts


if __name__ == "__main__":
    sample_rows = pd.DataFrame(
        [
            {
                "Datum": "14/05/2026",
                "uur": "09:00",
                "duur": 60,
                "veld": "Court 1",
                "ref1": "Arthur Franckx",
                "ref2": "Elyas Ludwig",
                "begeleiding": "Marie Gubel",
            },
            {
                "Datum": "14/05/2026",
                "uur": "09:30",
                "duur": 45,
                "veld": "Court 2",
                "ref1": "Arthur Franckx",
                "ref2": "Ward Stevens",
                "begeleiding": "James Kasapoglu",
            },
            {
                "Datum": "14/05/2026",
                "uur": "10:30",
                "duur": 30,
                "veld": "Court 3",
                "ref1": "Dylan Marcon",
                "ref2": "Elyas Ludwig",
                "begeleiding": "Xander Haijen",
            },
            {
                "Datum": "14/05/2026",
                "uur": "11:15",
                "duur": 30,
                "veld": "Court 4",
                "ref1": "Dylan Marcon",
                "ref2": "Samir Dehni",
                "begeleiding": "",
            },
        ]
    )

    detected_conflicts = find_schedule_conflicts(sample_rows)

    print(f"Detected {len(detected_conflicts)} conflict group(s).")
    for conflict in detected_conflicts:
        print(
            f"- {conflict['name']} on {conflict['date']} {conflict['time']} | "
            f"fields={', '.join(conflict['fields'])} | roles={', '.join(conflict['roles'])} | count={conflict['count']}"
        )