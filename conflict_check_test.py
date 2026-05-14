import pandas as pd


def normalize_schedule_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def find_schedule_conflicts(schedule_df):
    required_columns = ["Datum", "uur", "veld", "ref1", "ref2", "begeleiding"]
    missing_columns = [column for column in required_columns if column not in schedule_df.columns]
    if missing_columns:
        raise KeyError(f"Ontbrekende kolommen voor conflictcontrole: {', '.join(missing_columns)}")

    assignments = schedule_df[required_columns].copy().reset_index(drop=True)
    assignments["_game_row"] = assignments.index

    melted = assignments.melt(
        id_vars=["_game_row", "Datum", "uur", "veld"],
        value_vars=["ref1", "ref2", "begeleiding"],
        var_name="rol",
        value_name="naam",
    )

    melted["naam_norm"] = melted["naam"].map(normalize_schedule_value).str.lower()
    melted["datum_norm"] = pd.to_datetime(melted["Datum"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
    melted["datum_norm"] = melted["datum_norm"].fillna(melted["Datum"].map(normalize_schedule_value))
    melted["uur_norm"] = melted["uur"].map(normalize_schedule_value).str.lower()
    melted["veld_norm"] = melted["veld"].map(normalize_schedule_value)

    valid_assignments = melted[melted["naam_norm"] != ""].copy()
    if valid_assignments.empty:
        return []

    conflict_rows = valid_assignments[
        valid_assignments.duplicated(subset=["datum_norm", "uur_norm", "naam_norm"], keep=False)
    ].copy()

    if conflict_rows.empty:
        return []

    conflicts = []
    for (_, date_norm, time_norm), group in conflict_rows.groupby(["naam_norm", "datum_norm", "uur_norm"], sort=False):
        conflicts.append(
            {
                "name": normalize_schedule_value(group["naam"].iloc[0]),
                "date": date_norm,
                "time": time_norm,
                "fields": group["veld_norm"].drop_duplicates().tolist(),
                "roles": group["rol"].drop_duplicates().tolist(),
                "count": len(group),
            }
        )

    return conflicts


if __name__ == "__main__":
    sample_rows = pd.DataFrame(
        [
            {
                "Datum": "14/05/2026",
                "uur": "09:00",
                "veld": "Court 1",
                "ref1": "Arthur Franckx",
                "ref2": "Elyas Ludwig",
                "begeleiding": "Marie Gubel",
            },
            {
                "Datum": "14/05/2026",
                "uur": "09:00",
                "veld": "Court 2",
                "ref1": "Arthur Franckx",
                "ref2": "Ward Stevens",
                "begeleiding": "James Kasapoglu",
            },
            {
                "Datum": "14/05/2026",
                "uur": "10:00",
                "veld": "Court 3",
                "ref1": "Dylan Marcon",
                "ref2": "Elyas Ludwig",
                "begeleiding": "Xander Haijen",
            },
            {
                "Datum": "14/05/2026",
                "uur": "10:00",
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
            f"- {conflict['name']} at {conflict['date']} {conflict['time']} | "
            f"fields={', '.join(conflict['fields'])} | roles={', '.join(conflict['roles'])} | count={conflict['count']}"
        )
