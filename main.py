import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Page Configuration
st.set_page_config(page_title="RefPlan 2026", layout="wide")

st.title("Tournament Referee Portal")

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
menu = st.sidebar.radio("Navigation", ["My Schedule", "Full Tournament Overview", "Planner Portal 🔒"])
if menu == "Full Tournament Overview":
    st.header("Global Game Schedule")
    st.info("This view is read-only for all participants.")
    st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "My Schedule":
    st.header("Personal Assignment Finder")
    
    # Changed from email to name
    user_name = st.text_input("Enter your full name to see your games:").strip().lower()
    
    if user_name:
        # Filter logic: Convert columns to string (to avoid errors on empty cells) and lowercase them
        my_games = df[
            (df['ref1'].astype(str).str.lower() == user_name) | 
            (df['ref2'].astype(str).str.lower() == user_name) | 
            (df['begeleiding'].astype(str).str.lower() == user_name)
        ]
        
        if not my_games.empty:
            st.success(f"Found {len(my_games)} assignments for {user_name.title()}.")
            st.table(my_games[['Datum', 'uur', 'locatie', 'wedstrijd', 'ref1', 'ref2', 'begeleiding']])
        else:
            st.warning("No games found. Please check your spelling and ensure it matches the schedule.")
    else:
        st.write("Please enter your name in the box above to filter the schedule.")

elif menu == "Planner Portal 🔒":
    st.header("⚙️ Tournament Planner Portal")
    
    # 1. Simple Security
    password = st.text_input("Enter Planner Password:", type="password")
    
    if password == "admin2026": # Change to a secure password
        st.success("Access Granted. You are now in edit mode.")
        st.info("Make your assignments in the table below and click 'Save Changes to Server' when done.")
        
        # 2. Configure the Interactive Data Editor
        with st.form("assignment_form"):
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                # Make Game details read-only, but allow editing of Referees
                disabled=['Datum', 'uur', 'locatie', 'wedstrijd'],
                column_config={
                    "ref1": st.column_config.SelectboxColumn(
                        "Crew Chief",
                        help="Select the main referee",
                        width="medium",
                        options=REFEREES
                    ),
                    "ref2": st.column_config.SelectboxColumn(
                        "Umpire",
                        help="Select the secondary referee",
                        width="medium",
                        options=REFEREES
                    ),
                    "begeleiding": st.column_config.SelectboxColumn(
                        "Observer",
                        help="Select the observing mentor",
                        width="medium",
                        options=MENTORS
                    )
                }
            )
            
            # 3. The Save Button
            submit_button = st.form_submit_button("💾 Save Changes to Server")
            
            if submit_button:
                with st.spinner("Pushing updates to Google Sheets..."):
                    # This single line pushes the edited dataframe back to your Google Sheet!
                    conn.update(worksheet="Games", data=edited_df)
                    # Clear the cache so the app immediately shows the new data
                    st.cache_data.clear()
                    st.success("Schedule successfully updated!")
                    st.rerun() # Refresh the app to show changes

# 3. Simple Admin Access
with st.sidebar.expander("Admin"):
    pw = st.text_input("Admin Password", type="password")
    if pw == "referee2026": 
        st.write("Access Granted")
        st.download_button("Download Schedule as CSV", df.to_csv(), "schedule.csv")