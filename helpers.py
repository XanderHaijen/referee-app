import streamlit as st
import pandas as pd

def get_rate_for_game(divisie, pricing_df, is_internal: bool):
    """Return the rate for a given division using the pricing dataframe.

    pricing_df expected columns: ['division','internal_rate','external_rate']
    Matching is done by comparing the `divisie` value (exact, case-insensitive)
    to the `division` column in the pricing dataframe. If no exact match is
    found the function falls back to a row with division == 'DEFAULT', then
    to the first row.
    """
    if pricing_df is None or pricing_df.empty:
        return 0.0

    div_text = str(divisie or "").strip().lower()
    if div_text:
        match = pricing_df[pricing_df['division'].astype(str).str.lower() == div_text]
        if not match.empty:
            row = match.iloc[0]
            col = 'internal_rate' if is_internal else 'external_rate'
            try:
                return float(row.get(col, 0))
            except Exception:
                return 0.0

    # fallback to DEFAULT row
    default_row = pricing_df[pricing_df['division'].astype(str).str.lower() == 'default']
    if not default_row.empty:
        row = default_row.iloc[0]
        col = 'internal_rate' if is_internal else 'external_rate'
        try:
            return float(row.get(col, 0))
        except Exception:
            return 0.0

    # final fallback: first row
    try:
        row = pricing_df.iloc[0]
        col = 'internal_rate' if is_internal else 'external_rate'
        return float(row.get(col, 0))
    except Exception:
        return 0.0


def read_referee_lists(conn, url, DEFAULT_INTERNAL_REFEREES, DEFAULT_EXTERNAL_REFEREES, DEFAULT_MENTORS):
    try:
        referees_df = conn.read(spreadsheet=url, worksheet="Referees")
    except Exception:
        return DEFAULT_INTERNAL_REFEREES, DEFAULT_EXTERNAL_REFEREES, DEFAULT_MENTORS

    if referees_df.empty:
        return DEFAULT_INTERNAL_REFEREES, DEFAULT_EXTERNAL_REFEREES, DEFAULT_MENTORS

    normalized_columns = {
        str(column).strip().lower(): column
        for column in referees_df.columns
    }

    def _extract_column(*possible_names, fallback):
        for name in possible_names:
            if name in normalized_columns:
                values = (
                    referees_df[normalized_columns[name]]
                    .fillna("")
                    .astype(str)
                    .map(str.strip)
                )
                cleaned_values = [value for value in values if value]
                if cleaned_values:
                    return cleaned_values
        return fallback

    internal_refs = _extract_column("internal refs", "internal", "intern", fallback=DEFAULT_INTERNAL_REFEREES)
    external_refs = _extract_column("external refs", "external", fallback=DEFAULT_EXTERNAL_REFEREES)
    mentors = _extract_column("mentors", "mentor", fallback=DEFAULT_MENTORS)

    return internal_refs, external_refs, mentors


MENTOR_FEEDBACK_COLUMNS = [
    "game_key",
    "Datum",
    "uur",
    "duur",
    "veld",
    "wedstrijd",
    "mentor",
    "referee_role",
    "referee",
    "comment",
]


def load_mentor_feedback(conn, url):
    try:
        feedback_df = conn.read(spreadsheet=url, worksheet="Begeleidingen")
    except Exception:
        return pd.DataFrame(columns=MENTOR_FEEDBACK_COLUMNS)

    if feedback_df.empty:
        return pd.DataFrame(columns=MENTOR_FEEDBACK_COLUMNS)

    feedback_df = feedback_df.copy()
    for column in MENTOR_FEEDBACK_COLUMNS:
        if column not in feedback_df.columns:
            feedback_df[column] = ""

    return feedback_df[MENTOR_FEEDBACK_COLUMNS].copy()


def build_game_feedback_key(game_row):
    key_parts = [
        normalize_schedule_value(game_row.get("Datum", "")),
        normalize_schedule_value(game_row.get("uur", "")),
        normalize_schedule_value(game_row.get("duur", "")),
        normalize_schedule_value(game_row.get("veld", "")),
        normalize_schedule_value(game_row.get("wedstrijd", "")),
        normalize_schedule_value(game_row.get("ref1", "")),
        normalize_schedule_value(game_row.get("ref2", "")),
        normalize_schedule_value(game_row.get("begeleiding", "")),
    ]
    return " | ".join(key_parts)


def build_mentor_feedback_rows(games_df, mentor_name, feedback_values):
    rows = []
    mentor_text = normalize_schedule_value(mentor_name)

    for _, game_row in games_df.iterrows():
        game_key = build_game_feedback_key(game_row)
        for referee_role, referee_column in (("ref1", "ref1"), ("ref2", "ref2")):
            comment = normalize_schedule_value(feedback_values.get((game_key, referee_role), ""))
            referee_name = normalize_schedule_value(game_row.get(referee_column, ""))
            if not comment:
                continue

            rows.append(
                {
                    "game_key": game_key,
                    "Datum": normalize_schedule_value(game_row.get("Datum", "")),
                    "uur": normalize_schedule_value(game_row.get("uur", "")),
                    "duur": normalize_schedule_value(game_row.get("duur", "")),
                    "veld": normalize_schedule_value(game_row.get("veld", "")),
                    "wedstrijd": normalize_schedule_value(game_row.get("wedstrijd", "")),
                    "mentor": mentor_text,
                    "referee_role": referee_role,
                    "referee": referee_name,
                    "comment": comment,
                }
            )

    return pd.DataFrame(rows, columns=MENTOR_FEEDBACK_COLUMNS)


def prepare_mentor_feedback_update(dataframe):
    if dataframe is None or dataframe.empty:
        return pd.DataFrame(columns=MENTOR_FEEDBACK_COLUMNS)

    prepared_df = dataframe.copy().reset_index(drop=True)
    for column in MENTOR_FEEDBACK_COLUMNS:
        if column not in prepared_df.columns:
            prepared_df[column] = ""

    prepared_df = prepared_df[MENTOR_FEEDBACK_COLUMNS]
    return prepared_df.sort_values(["referee", "Datum", "uur", "mentor"], kind="stable").reset_index(drop=True)


def replace_mentor_feedback(existing_feedback_df, mentor_name, games_df, new_feedback_df):
    base_df = load_mentor_feedback_from_frame(existing_feedback_df)
    mentor_text = normalize_schedule_value(mentor_name).lower()
    game_keys = {build_game_feedback_key(game_row) for _, game_row in games_df.iterrows()}

    if not base_df.empty:
        mask = ~(
            base_df["mentor"].astype(str).str.strip().str.lower().eq(mentor_text)
            & base_df["game_key"].astype(str).isin(game_keys)
        )
        base_df = base_df[mask].copy()

    if new_feedback_df is None or new_feedback_df.empty:
        return prepare_mentor_feedback_update(base_df)

    combined_df = pd.concat([base_df, new_feedback_df], ignore_index=True)
    return prepare_mentor_feedback_update(combined_df)


def load_mentor_feedback_from_frame(feedback_df):
    if feedback_df is None or feedback_df.empty:
        return pd.DataFrame(columns=MENTOR_FEEDBACK_COLUMNS)

    normalized_feedback = feedback_df.copy()
    for column in MENTOR_FEEDBACK_COLUMNS:
        if column not in normalized_feedback.columns:
            normalized_feedback[column] = ""

    return normalized_feedback[MENTOR_FEEDBACK_COLUMNS].copy()


def _parse_schedule_start(date_value, time_value):
    date_text = normalize_schedule_value(date_value)
    time_text = normalize_schedule_value(time_value)
    if not date_text or not time_text:
        return pd.NaT

    combined_value = f"{date_text} {time_text}"
    start_dt = pd.to_datetime(combined_value, errors="coerce", dayfirst=True)
    if pd.isna(start_dt):
        return pd.NaT

    return start_dt


def format_time_range(date_value, time_value, duration_value):
    """Return a formatted time range 'HH:MM -- HH:MM' using date, start time and duration (minutes).

    If parsing fails or duration is missing/invalid, falls back to returning the normalized start time text.
    """
    start_dt = _parse_schedule_start(date_value, time_value)
    if pd.isna(start_dt):
        return normalize_schedule_value(time_value)

    try:
        duration = float(normalize_schedule_value(duration_value)) if normalize_schedule_value(duration_value) != "" else 0
    except Exception:
        duration = 0

    if duration <= 0:
        return start_dt.strftime("%H:%M")

    end_dt = start_dt + pd.to_timedelta(duration, unit="m")
    return f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"


def format_date_day_month(date_value):
    """Format a date value to show only day and month as 'DD/MM'.

    If parsing fails, returns the normalized original value.
    """
    date_text = normalize_schedule_value(date_value)
    if not date_text:
        return ""

    try:
        dt = pd.to_datetime(date_text, errors="coerce", dayfirst=True)
        if pd.isna(dt):
            return date_text
        return dt.strftime("%d/%m")
    except Exception:
        return date_text


def _unique_preserve_order(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result

def normalize_schedule_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def find_schedule_conflicts(schedule_df):
    required_columns = ["Datum", "uur", "duur", "veld", "ref1", "ref2", "begeleiding"]
    missing_columns = [column for column in required_columns if column not in schedule_df.columns]
    if missing_columns:
        raise KeyError(f"Ontbrekende kolommen voor conflictcontrole: {', '.join(missing_columns)}")

    assignments = schedule_df[required_columns].copy().reset_index(drop=True)
    assignments["_game_row"] = assignments.index

    melted = assignments.melt(
        id_vars=["_game_row", "Datum", "uur", "duur", "veld"],
        value_vars=["ref1", "ref2", "begeleiding"],
        var_name="rol",
        value_name="naam",
    )

    melted["naam_norm"] = melted["naam"].map(normalize_schedule_value).str.lower()
    melted["start_dt"] = melted.apply(lambda row: _parse_schedule_start(row["Datum"], row["uur"]), axis=1)
    melted["datum_norm"] = melted["start_dt"].dt.strftime("%Y-%m-%d")
    melted["datum_norm"] = melted["datum_norm"].fillna(melted["Datum"].map(normalize_schedule_value))
    melted["duur_norm"] = pd.to_numeric(melted["duur"], errors="coerce")
    melted["end_dt"] = melted["start_dt"] + pd.to_timedelta(melted["duur_norm"], unit="m")
    melted["veld_norm"] = melted["veld"].map(normalize_schedule_value)

    valid_assignments = melted[
        (melted["naam_norm"] != "")
        & melted["start_dt"].notna()
        & melted["end_dt"].notna()
        & (melted["duur_norm"] > 0)
    ].copy()
    if valid_assignments.empty:
        return []

    conflicts = []
    ordered_assignments = valid_assignments.sort_values(["datum_norm", "naam_norm", "start_dt", "end_dt", "_game_row"]) 

    for (date_norm, name_norm), group in ordered_assignments.groupby(["datum_norm", "naam_norm"], sort=False):
        current_group = []
        current_group_end = pd.NaT

        for row in group.itertuples(index=False):
            if not current_group:
                current_group = [row]
                current_group_end = row.end_dt
                continue

            if row.start_dt < current_group_end:
                current_group.append(row)
                if row.end_dt > current_group_end:
                    current_group_end = row.end_dt
                continue

            if len(current_group) > 1:
                try:
                    display_date = current_group[0].start_dt.strftime('%d/%m')
                except Exception:
                    display_date = normalize_schedule_value(current_group[0].Datum)

                conflicts.append(
                    {
                        "name": normalize_schedule_value(current_group[0].naam),
                        "date": display_date,
                        "time": f"{current_group[0].start_dt.strftime('%H:%M')} - {current_group_end.strftime('%H:%M')}",
                        "fields": _unique_preserve_order([item.veld_norm for item in current_group]),
                        "roles": _unique_preserve_order([item.rol for item in current_group]),
                        "count": len(current_group),
                    }
                )

            current_group = [row]
            current_group_end = row.end_dt

        if len(current_group) > 1:
            try:
                display_date = current_group[0].start_dt.strftime('%d/%m')
            except Exception:
                display_date = normalize_schedule_value(current_group[0].Datum)

            conflicts.append(
                {
                    "name": normalize_schedule_value(current_group[0].naam),
                    "date": display_date,
                    "time": f"{current_group[0].start_dt.strftime('%H:%M')} - {current_group_end.strftime('%H:%M')}",
                    "fields": _unique_preserve_order([item.veld_norm for item in current_group]),
                    "roles": _unique_preserve_order([item.rol for item in current_group]),
                    "count": len(current_group),
                }
            )

    return conflicts


def render_schedule_conflicts(conflicts):
    if not conflicts:
        st.success("✅ Geen planningsconflicten gedetecteerd - opslaan is ingeschakeld.")
        return

    st.error("⚠️ **PLANNINGSCONFLICTEN GEDETECTEERD!** Het opslaan is gedeactiveerd.")
    st.write("De volgende personen hebben overlappende toewijzingen op dezelfde datum:")

    for conflict in conflicts:
        fields = ", ".join(conflict["fields"])
        roles = ", ".join(conflict["roles"])
        st.warning(
            f"**{conflict['name']}** heeft overlappende toewijzingen op **{conflict['date']}** "
            f"tussen **{conflict['time']}** (Velden: {fields}; Rollen: {roles}; Aantal: {conflict['count']})"
        )


def prepare_sheet_update(dataframe):
    return dataframe.copy().reset_index(drop=True)