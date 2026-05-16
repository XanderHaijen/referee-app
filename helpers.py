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


def read_referee_lists():
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
        display_name = normalize_schedule_value(group["naam"].iloc[0])
        conflict_fields = group["veld_norm"].drop_duplicates().tolist()
        conflict_roles = group["rol"].drop_duplicates().tolist()
        conflicts.append(
            {
                "name": display_name,
                "date": date_norm,
                "time": time_norm,
                "fields": conflict_fields,
                "roles": conflict_roles,
                "count": len(group),
            }
        )

    return conflicts


def render_schedule_conflicts(conflicts):
    if not conflicts:
        st.success("✅ Geen planningsconflicten gedetecteerd - opslaan is ingeschakeld.")
        return

    st.error("⚠️ **PLANNINGSCONFLICTEN GEDETECTEERD!** Het opslaan is gedeactiveerd.")
    st.write("De volgende personen zijn meerdere keren ingepland op dezelfde datum en tijd:")

    for conflict in conflicts:
        fields = ", ".join(conflict["fields"])
        roles = ", ".join(conflict["roles"])
        st.warning(
            f"**{conflict['name']}** is op **{conflict['date']}** om **{conflict['time']}** "
            f"meerdere keren ingepland (Velden: {fields}; Rollen: {roles}; Aantal: {conflict['count']})"
        )


def prepare_sheet_update(dataframe):
    return dataframe.copy().reset_index(drop=True)