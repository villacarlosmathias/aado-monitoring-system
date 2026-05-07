import streamlit as st
import psycopg2
import pandas as pd

st.set_page_config(
    page_title="AADO Monitoring System",
    layout="wide"
)

# DATABASE CONNECTION
conn = psycopg2.connect(
    host="db.hbhyzahelupehbahjluk.supabase.co",
    port="5432",
    database="postgres",
    user="postgres",
    password="matabaako00550208"
)

# TITLE
st.title("🏅 AADO Student-Athlete Monitoring System")

st.markdown("---")

# DASHBOARD
col1, col2, col3, col4 = st.columns(4)

cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM student_athlete")
total_students = cursor.fetchone()[0]

cursor.execute("""
SELECT COUNT(*)
FROM student_athlete
WHERE status = 'Active'
""")
active_students = cursor.fetchone()[0]

cursor.execute("""
SELECT COUNT(*)
FROM student_athlete
WHERE status = 'Inactive'
""")
inactive_students = cursor.fetchone()[0]

cursor.execute("""
SELECT COUNT(DISTINCT sports_events)
FROM student_athlete
WHERE sports_events IS NOT NULL
""")
sports_count = cursor.fetchone()[0]

col1.metric("Total Students", total_students)
col2.metric("Active Athletes", active_students)
col3.metric("Inactive Athletes", inactive_students)
col4.metric("Sports Events", sports_count)

st.markdown("---")

# STUDENT TABLE
st.subheader("Student-Athlete Records")

query = """
SELECT
    student_number AS "Student ID",
    full_name AS "Name",
    grade_level AS "Grade",
    section AS "Section",
    strand AS "Strand",
    sports_events AS "Sports",
    status AS "Status"
FROM student_athlete
ORDER BY full_name;
"""

df = pd.read_sql(query, conn)

st.dataframe(df, use_container_width=True)
