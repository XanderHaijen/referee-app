import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from helpers import *

# Page Configuration
st.set_page_config(page_title="RefPlan 2026", layout="wide")

st.title("Toernooischeidsrechter Portal")

# 1. Connection to Google Sheets
# Replace 'YOUR_SHEET_URL_HERE' with the link you copied
url = "https://docs.google.com/spreadsheets/d/1ZxbRCWrZ5BVI2JjBZlj8B73v2OAHkRkUtYvjSNAp9Ec/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch data
df = conn.read(spreadsheet=url, worksheet="Games")
editor_df = df.copy()
for referee_column in ["ref1", "ref2", "begeleiding"]:
    if referee_column in editor_df.columns:
        editor_df[referee_column] = editor_df[referee_column].fillna("").astype(str)

MENTORS = ["Xander Haijen", "Marie Gubel", "James Kasapoglu"]
INTERNAL_REFEREES = ["Arthur Franckx", "Elyas Ludwig", "Ward Stevens", "Mattias Gernay",
            "Marie Gubel", "Arthur Schalm", "Axel Callebaut", "James Kasapoglu", "Xander Haijen"]
EXTERNAL_REFEREES = ["Dylan Marcon", "Dzan Erden",
            "Yusuf Samil", "Samir Dehni", "Marcus Roels", "Emilio Verzwyvel"]

# Combined referees list for editor options
REFEREES = INTERNAL_REFEREES + EXTERNAL_REFEREES


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


# 2. Sidebar Navigation
menu = st.sidebar.radio("Navigatie", ["Mijn Schema", "Volledig Toernooioverzicht", "Plannersportal 🔒"])
if menu == "Volledig Toernooioverzicht":
    st.header("Volledig Wedstrijdschema")
    st.info("Dit beeld is alleen-lezen voor alle deelnemers.")
    st.dataframe(df, width="stretch", hide_index=True)

elif menu == "Mijn Schema":
    st.header("Persoonlijke Aanduidingen en Vergoedingen")
    
    # Changed from email to name
    user_name = st.text_input("Voer uw volledige naam in om uw wedstrijden te zien:").strip().lower()
    
    if user_name:
        # Filter logic: Convert columns to string (to avoid errors on empty cells) and lowercase them
        my_games = df[
            (df['ref1'].astype(str).str.lower() == user_name) | 
            (df['ref2'].astype(str).str.lower() == user_name) | 
            (df['begeleiding'].astype(str).str.lower() == user_name)
        ]
        
        if not my_games.empty:
            st.success(f"{len(my_games)} toewijzingen gevonden voor {user_name.title()}.")

            # Load pricing (if available) to calculate owed amounts
            try:
                pricing_df = conn.read(spreadsheet=url, worksheet="Pricing")
            except Exception:
                pricing_df = pd.DataFrame({
                    'division': ['DEFAULT', 'U12', 'U14', 'U16'],
                    'internal_rate': [30, 25, 30, 35],
                    'external_rate': [40, 35, 40, 45]
                })

            # Determine if the user is internal or external
            lower_internal = [r.lower() for r in INTERNAL_REFEREES]
            is_internal_user = user_name in lower_internal

            def _amount_for_row(row):
                amt = 0.0
                for role in ['ref1', 'ref2']:
                    if str(row.get(role, '')).strip().lower() == user_name:
                        rate = get_rate_for_game(row.get('divisie', ''), pricing_df, is_internal_user)
                        try:
                            amt += float(rate)
                        except Exception:
                            pass
                return amt

            my_games_calc = my_games.copy()
            # Numeric amount per game (mentors will get 0.0 because we only pay ref1/ref2)
            my_games_calc['Bedrag_num'] = my_games_calc.apply(_amount_for_row, axis=1).round(2)
            # Display column with euro formatting (keeps mentors visible as €0.00)
            my_games_calc['Bedrag'] = my_games_calc['Bedrag_num'].apply(lambda x: f"€{x:.2f}")
            # Show per-game and total owed
            st.table(my_games_calc[['Datum', 'uur', 'divisie', 'veld', 'wedstrijd', 'ref1', 'ref2', 'begeleiding', 'Bedrag']])
            total_owed = my_games_calc['Bedrag_num'].sum()
            st.success(f"Totaal te ontvangen wedstrijdvergoedingen: €{total_owed:.2f}")
        else:
            st.warning("Geen wedstrijden gevonden. Controleer alstublieft uw spelling en zorg dat deze overeenkomt met het schema.")
    else:
        st.write("Voer alstublieft uw naam in het vak hierboven in om het schema te filteren.")

elif menu == "Plannersportal 🔒":
    st.header("⚙️ Toernooiplannersportal")
    
    # 1. Simple Security
    password = st.text_input("Voer plannerwachtwoord in:", type="password")
    
    if password == "admin2026": # Change to a secure password
        st.cache_data.clear()  # Clear cache to ensure fresh data
        st.success("Toegang verleend. U bent nu in bewerkingsmodus.")
        st.info("Maak uw toewijzingen in de onderstaande tabel en klik op 'Wijzigingen op Server opslaan' wanneer u klaar bent.")
        
        pricing_df = conn.read(spreadsheet=url, worksheet="Pricing")

        # 2. Configure the Interactive Data Editor
        with st.form("assignment_form"):
            edited_df = st.data_editor(
                editor_df,
                width="stretch",
                hide_index=True,
                # Make Game details read-only, but allow editing of Referees
                disabled=['Datum', 'uur','divisie', 'veld', 'wedstrijd'],
                column_config={
                    "ref1": st.column_config.SelectboxColumn(
                        "Crew chief",
                        help="Selecteer de crew chief",
                        width="medium",
                        options=REFEREES
                    ),
                    "ref2": st.column_config.SelectboxColumn(
                        "Umpire",
                        help="Selecteer de umpire",
                        width="medium",
                        options=REFEREES
                    ),
                    "begeleiding": st.column_config.SelectboxColumn(
                        "Begeleider",
                        help="Selecteer de begeleider",
                        width="medium",
                        options=MENTORS
                    )
                }
            )
            st.markdown("---")
            submit_button = st.form_submit_button("💾 Wijzigingen op Server opslaan")
            
        # --- SAVE LOGIC ---
        if submit_button:
            conflicts_before_save = find_schedule_conflicts(edited_df)
            if conflicts_before_save:
                render_schedule_conflicts(conflicts_before_save)
                st.error("Kan niet op de server opslaan terwijl conflicten bestaan. Los deze eerst op en probeer opnieuw.")
            else:
                with st.spinner("Updates naar Google Sheets pushen..."):
                    try:
                        conn.update(spreadsheet=url, worksheet="Games", data=prepare_sheet_update(edited_df))
                        st.cache_data.clear()
                        st.success("Schema succesvol bijgewerkt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fout bij opslaan: {e}")

        with st.form("pricing_form"):
            st.write("**Prijsinstellingen per divisie**")
            edited_pricing = st.data_editor(
                pricing_df,
                width="stretch",
                hide_index=True,
            )
            pricing_submit = st.form_submit_button("💾 Opslaan Prijzen")

        if pricing_submit:
            try:
                conn.update(spreadsheet=url, worksheet="Pricing", data=prepare_sheet_update(edited_pricing))
                st.success("Prijzen succesvol bijgewerkt op Google Sheets.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Kon prijzen niet opslaan: {e}")

# 3. Simple Admin Access
with st.sidebar.expander("Beheer"):
    pw = st.text_input("Beheerwachtwoord", type="password")
    if pw == "referee2026": 
        st.write("Toegang verleend")
        st.download_button("Schema als CSV downloaden", df.to_csv(), "schedule.csv")