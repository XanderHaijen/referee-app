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

MENTORS = ["Xander Haijen", "Marie Gubel", "James Kasapoglu"]
INTERNAL_REFEREES = ["Arthur Franckx", "Elyas Ludwig", "Ward Stevens", "Mattias Gernay",
            "Marie Gubel", "Arthur Schalm", "Axel Callebaut", "James Kasapoglu", "Xander Haijen"]
EXTERNAL_REFEREES = ["Dylan Marcon", "Dzan Erden",
            "Yusuf Samil", "Samir Dehni", "Marcus Roels", "Emilio Verzwyvel"]

# Combined referees list for editor options
REFEREES = INTERNAL_REFEREES + EXTERNAL_REFEREES


# 2. Sidebar Navigation
menu = st.sidebar.radio("Navigatie", ["Mijn Schema", "Volledig Toernooioverzicht", "Plannersportal 🔒"])
if menu == "Volledig Toernooioverzicht":
    st.header("Volledig Wedstrijdschema")
    st.info("Dit beeld is alleen-lezen voor alle deelnemers.")
    st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "Mijn Schema":
    st.header("Persoonlijke Toewijzingszoekers")
    
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
        st.success("Toegang verleend. U bent nu in bewerkingsmodus.")
        st.info("Maak uw toewijzingen in de onderstaande tabel en klik op 'Wijzigingen op Server opslaan' wanneer u klaar bent.")
        
        # 2. Configure the Interactive Data Editor
        with st.form("assignment_form"):
            edited_df = st.data_editor(
                df,
                use_container_width=True,
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
            
            # 3. The Save Button
            submit_button = st.form_submit_button("💾 Wijzigingen op Server opslaan")
            
        # Pricing editor for planners (separate form)
        pricing_df = conn.read(spreadsheet=url, worksheet="Pricing")

        with st.form("pricing_form"):
            st.write("**Prijsinstellingen per divisie**")
            edited_pricing = st.data_editor(
                pricing_df,
                use_container_width=True,
                hide_index=True,
            )
            pricing_submit = st.form_submit_button("💾 Opslaan Prijzen")

        if pricing_submit:
            try:
                conn.update(spreadsheet=url, worksheet="Pricing", data=edited_pricing)
                st.success("Prijzen succesvol bijgewerkt op Google Sheets.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Kon prijzen niet opslaan: {e}")

# We run this check dynamically based on the current state of the editor
        can_save = True  # Initialize as True, set to False if conflicts found
        
        try:
            # 1. Reshape data to make checking easier (melt puts all names in one column)
            melted = edited_df.melt(
                id_vars=['Datum', 'uur', 'veld'], 
                value_vars=['ref1', 'ref2', 'begeleiding'], 
                value_name='naam'
            )
            
            # 2. Remove empty assignments
            melted = melted.dropna(subset=['naam'])
            melted = melted[melted['naam'].str.strip() != '']
            
            # 3. Find duplicates based on Date, Time, and Name
            conflicts = melted[melted.duplicated(subset=['Datum', 'uur', 'naam'], keep=False)]
            
            if not conflicts.empty:
                st.error("⚠️ **PLANNINGSCONFLICT GEDETECTEERD!**")
                st.write("De volgende personen zijn op dezelfde datum en tijd dubbel geboekt. Corrigeer alstublieft het schema hierboven voordat u opslaat.")
                
                # Format the output so the planner knows exactly where to look
                for name, group in conflicts.groupby('naam'):
                    times = group['uur'].unique()
                    for t in times:
                        conflict_games = group[group['uur'] == t]
                        if len(conflict_games) > 1:
                            date = conflict_games['Datum'].iloc[0]
                            pitches = ", ".join(conflict_games['veld'].astype(str).unique().tolist())
                            st.warning(f"**{name}** is ingepland voor meerdere wedstrijden op **{date}** om **{t}** (Velden: {pitches})")
                
                # Disable the save functionality if there's a conflict
                can_save = False
            else:
                st.success("✅ Geen planningsconflicten gedetecteerd.")
                can_save = True
        except Exception as e:
            st.error(f"Fout bij conflict detection: {e}")
            can_save = False  # Default to False on error to prevent accidental saves

        # --- SAVE LOGIC ---
        if submit_button:
            if can_save:
                with st.spinner("Updates naar Google Sheets pushen..."):
                    conn.update(spreadsheet=url, worksheet="Games", data=edited_df)
                    st.cache_data.clear()
                    st.success("Schema succesvol bijgewerkt!")
                    st.rerun()
            else:
                st.error("Kan niet op de server opslaan terwijl conflicten bestaan. Los deze alstublieft eerst op.")

# 3. Simple Admin Access
with st.sidebar.expander("Beheer"):
    pw = st.text_input("Beheerwachtwoord", type="password")
    if pw == "referee2026": 
        st.write("Toegang verleend")
        st.download_button("Schema als CSV downloaden", df.to_csv(), "schedule.csv")