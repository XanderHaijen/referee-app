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

DEFAULT_INTERNAL_REFEREES = ["Arthur Franckx"]
DEFAULT_EXTERNAL_REFEREES = ["Dylan Marcon"]
DEFAULT_MENTORS = ["Xander Haijen"]


INTERNAL_REFEREES, EXTERNAL_REFEREES, MENTORS = \
    read_referee_lists(conn, url, DEFAULT_INTERNAL_REFEREES, DEFAULT_EXTERNAL_REFEREES, DEFAULT_MENTORS)

# Combined referees list for editor options
REFEREES = INTERNAL_REFEREES + [referee for referee in EXTERNAL_REFEREES if referee not in INTERNAL_REFEREES]
mentor_feedback_df = load_mentor_feedback(conn, url)

# 2. Sidebar Navigation
menu = st.sidebar.radio("Navigatie", ["Mijn Schema", "Mentorportal 📝", "Volledig Toernooioverzicht", "Plannersportal 🔒"])
if menu == "Volledig Toernooioverzicht":
    st.header("Volledig Wedstrijdschema")
    st.info("Dit beeld is alleen-lezen voor alle deelnemers.")
    st.dataframe(df, width="stretch", hide_index=True)

elif menu == "Mentorportal 📝":
    st.header("Mentorportal")
    st.write("Selecteer uw naam om de wedstrijden te zien waarvoor u begeleiding geeft en voeg per referee een evaluatie toe.")

    mentor_name = st.selectbox("Uw naam", MENTORS)
    mentor_games = df[df["begeleiding"].astype(str).str.lower() == mentor_name.lower()].copy()

    if mentor_games.empty:
        st.warning("Er zijn momenteel geen wedstrijden gekoppeld aan deze mentor.")
    else:
        st.success(f"{len(mentor_games)} begeleidingsopdrachten gevonden voor {mentor_name}.")

        mentor_existing_feedback = mentor_feedback_df[
            mentor_feedback_df["mentor"].astype(str).str.lower() == mentor_name.lower()
        ].copy()
        existing_feedback_map = {
            (str(row.game_key), str(row.referee_role)): str(row.comment)
            for row in mentor_existing_feedback.itertuples(index=False)
        }

        with st.form(f"mentor_feedback_form_{mentor_name}"):
            feedback_widget_map = {}

            for _, game_row in mentor_games.iterrows():
                game_key = build_game_feedback_key(game_row)
                expander_title = (
                    f"{game_row.get('Datum', '')} | {game_row.get('uur', '')} | "
                    f"{game_row.get('veld', '')} | {game_row.get('wedstrijd', '')}"
                )

                with st.expander(expander_title, expanded=False):
                    st.write(f"**Crew chief:** {normalize_schedule_value(game_row.get('ref1', ''))}")
                    st.write(f"**Umpire:** {normalize_schedule_value(game_row.get('ref2', ''))}")

                    ref1_widget_key = f"{game_key}::ref1"
                    ref2_widget_key = f"{game_key}::ref2"

                    st.text_area(
                        "Evaluatie van de crew chief",
                        value=existing_feedback_map.get((game_key, "ref1"), ""),
                        key=ref1_widget_key,
                    )
                    st.text_area(
                        "Evaluatie van de umpire",
                        value=existing_feedback_map.get((game_key, "ref2"), ""),
                        key=ref2_widget_key,
                    )

                    feedback_widget_map[(game_key, "ref1")] = ref1_widget_key
                    feedback_widget_map[(game_key, "ref2")] = ref2_widget_key

            submit_feedback = st.form_submit_button("💾 Begeleidingen opslaan")

        if submit_feedback:
            feedback_values = {
                (game_key, referee_role): st.session_state[widget_key]
                for (game_key, referee_role), widget_key in feedback_widget_map.items()
            }
            new_feedback_df = build_mentor_feedback_rows(mentor_games, mentor_name, feedback_values)
            updated_feedback_df = replace_mentor_feedback(mentor_feedback_df, mentor_name, mentor_games, new_feedback_df)

            with st.spinner("Begeleidingen opslaan naar Google Sheets..."):
                try:
                    conn.update(
                        spreadsheet=url,
                        worksheet="Begeleidingen",
                        data=prepare_mentor_feedback_update(updated_feedback_df),
                    )
                    st.cache_data.clear()
                    st.success("Begeleidingen succesvol opgeslagen.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Kon begeleidingen niet opslaan: {e}")

        if not mentor_existing_feedback.empty:
            st.subheader("Uw opgeslagen begeleidingen")
            for referee_name, referee_feedback in mentor_existing_feedback.sort_values(["referee", "Datum", "uur"]).groupby("referee", sort=False):
                st.markdown(f"**{referee_name}**")
                st.dataframe(
                    referee_feedback[["Datum", "uur", "veld", "wedstrijd", "referee_role", "comment"]],
                    width="stretch",
                    hide_index=True,
                )

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
                disabled=['Datum', 'uur', 'duur', 'divisie', 'veld', 'wedstrijd'],
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