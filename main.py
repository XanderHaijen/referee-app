import streamlit as st
from lib.streamlit_gsheets import GSheetsConnection

# Page Configuration
st.set_page_config(page_title="RefPlan 2026", layout="wide")

st.title("Tournament Referee Portal")

# 1. Connection to Google Sheets
# Replace 'YOUR_SHEET_URL_HERE' with the link you copied
url = "https://docs.google.com/spreadsheets/d/1V4IO4YVHkWUF-IyVLM1bGlTCCCvXigJ4/edit?gid=171698999#gid=171698999"
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch data
df = conn.read(spreadsheet=url, worksheet="Games")

# 2. Sidebar Navigation
menu = st.sidebar.radio("Navigation", ["My Schedule", "Full Tournament Overview"])

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

# 3. Simple Admin Access
with st.sidebar.expander("Admin"):
    pw = st.text_input("Admin Password", type="password")
    if pw == "referee2026": 
        st.write("Access Granted")
        st.download_button("Download Schedule as CSV", df.to_csv(), "schedule.csv")