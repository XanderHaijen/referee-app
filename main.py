import streamlit as st
from streamlit_gsheets import GSheetsConnection

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
REFEREES = ["Arthur Franckx", "Elyas Ludwig", "Ward Stevens", "Mattias Gernay",
            "Marie Gubel", "Arthur Schalm", "Axel Callebaut", "James Kasapoglu", "Dylan Marcon", "Dzan Erden",
            "Yusuf Samil", "Samir Dehni", "Marcus Roels", "Emilio Verzwyvel"]
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
            st.success(f"Gevonden {len(my_games)} toewijzingen voor {user_name.title()}.")
            st.table(my_games[['Datum', 'uur', 'ploeg', 'locatie', 'wedstrijd', 'ref1', 'ref2', 'begeleiding']])
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
                disabled=['Datum', 'uur','ploeg', 'locatie', 'wedstrijd'],
                column_config={
                    "ref1": st.column_config.SelectboxColumn(
                        "Scheidsrechter",
                        help="Selecteer de crew cheif",
                        width="medium",
                        options=REFEREES
                    ),
                    "ref2": st.column_config.SelectboxColumn(
                        "Assistent",
                        help="Selecteer de umpire",
                        width="medium",
                        options=REFEREES
                    ),
                    "begeleiding": st.column_config.SelectboxColumn(
                        "Waarnemer",
                        help="Selecteer de begeleider",
                        width="medium",
                        options=MENTORS
                    )
                }
            )
            
            # 3. The Save Button
            submit_button = st.form_submit_button("💾 Wijzigingen op Server opslaan")
            
# We run this check dynamically based on the current state of the editor
        
        # 1. Reshape data to make checking easier (melt puts all names in one column)
        melted = edited_df.melt(
            id_vars=['Datum', 'uur', 'locatie'], 
            value_vars=['ref1', 'ref2', 'begeleiding'], 
            value_name='naam'
        )
        
        # 2. Remove empty assignments
        melted = melted.dropna(subset=['naam'])
        melted = melted[melted['naam'].str.strip() != '']
        
        # 3. Find duplicates based on Time and Name
        conflicts = melted[melted.duplicated(subset=['uur', 'naam'], keep=False)]
        
        if not conflicts.empty:
            st.error("⚠️ **PLANNINGSCONFLICT GEDETECTEERD!**")
            st.write("De volgende personen zijn op hetzelfde moment dubbel geboekt. Corrigeer alstublieft het schema hierboven voordat u opslaat.")
            
            # Format the output so the planner knows exactly where to look
            for name, group in conflicts.groupby('naam'):
                times = group['uur'].unique()
                for t in times:
                    conflict_games = group[group['uur'] == t]
                    if len(conflict_games) > 1:
                        pitches = ", ".join(conflict_games['locatie'].astype(str).tolist())
                        st.warning(f"**{name}** is ingepland voor meerdere wedstrijden om **{t}** (Velden: {pitches})")
            
            # Disable the save functionality if there's a conflict
            can_save = False
        else:
            st.success("✅ Geen planningsconflicten gedetecteerd.")
            can_save = True

        # --- SAVE LOGIC ---
        if submit_button:
            if can_save:
                with st.spinner("Updates naar Google Sheets pushen..."):
                    conn.update(worksheet="Games", data=edited_df)
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