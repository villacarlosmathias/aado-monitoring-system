import streamlit as st
import psycopg2
import pandas as pd

st.set_page_config(
    page_title="AADO Monitoring System",
    layout="wide"
)

# DATABASE CONNECTION
conn = psycopg2.connect(
    host="aws-1-ap-southeast-2.pooler.supabase.com",
    port="6543",
    database="postgres",
    user="postgres.hbhyzahelupehbahjluk",
    password="matabaako00550208",
    sslmode="require"
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

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import psycopg2
import pandas as pd
import math
import random

conn = psycopg2.connect(
    host="localhost",
    port="5433",
    database="aado_monitoring_db",
    user="postgres",
    password="your_new_password"
)

cursor = conn.cursor()

logged_username = None
logged_role = None
assigned_sport = None
assigned_section = None
child_student_number = None
logged_scope = None


def clean_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    value = str(value).strip()
    if value == "" or value.lower() == "nan":
        return None
    return value


def clean_numeric(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def setup_database():
    try:
        cursor.execute("""
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'coach',
    ADD COLUMN IF NOT EXISTS assigned_sport TEXT,
    ADD COLUMN IF NOT EXISTS assigned_section TEXT,
    ADD COLUMN IF NOT EXISTS child_student_number TEXT,
    ADD COLUMN IF NOT EXISTS is_temp BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS user_scope TEXT DEFAULT 'highschool';
""")

        cursor.execute("""
            ALTER TABLE student_athlete
            ALTER COLUMN course DROP NOT NULL,
            ALTER COLUMN year_level DROP NOT NULL;
        """)

        cursor.execute("""
            ALTER TABLE subject
            ADD COLUMN IF NOT EXISTS units INTEGER DEFAULT 3;
        """)

        cursor.execute("""
            UPDATE subject SET units = 3 WHERE units IS NULL;
        """)

        cursor.execute("""
            ALTER TABLE subject
            ALTER COLUMN units SET DEFAULT 3;
        """)

        cursor.execute("""
            ALTER TABLE academic_record
            ADD COLUMN IF NOT EXISTS academic_year TEXT,
            ADD COLUMN IF NOT EXISTS term TEXT,
            ADD COLUMN IF NOT EXISTS midterm_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS final_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS final_term_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS q1_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS q2_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS q3_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS q4_grade NUMERIC,
            ADD COLUMN IF NOT EXISTS teacher_name TEXT,
            ADD COLUMN IF NOT EXISTS subject_name TEXT,
            ADD COLUMN IF NOT EXISTS intervention_remarks TEXT;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT DEFAULT 'coach',
                assigned_sport TEXT,
                assigned_section TEXT,
                child_student_number TEXT
            );
        """)

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'coach',
            ADD COLUMN IF NOT EXISTS assigned_sport TEXT,
            ADD COLUMN IF NOT EXISTS assigned_section TEXT,
            ADD COLUMN IF NOT EXISTS child_student_number TEXT;
        """)

        cursor.execute("""
            INSERT INTO users (username, password, role)
            VALUES ('admin', 'admin123', 'admin')
            ON CONFLICT (username) DO NOTHING;
        """)

        cursor.execute("""
            INSERT INTO users (username, password, role, user_scope)
            VALUES ('collegeadmin', 'college123', 'admin', 'college')
            ON CONFLICT (username) DO NOTHING;
        """)

        cursor.execute("""
            UPDATE users
            SET user_scope = 'highschool'
            WHERE username = 'admin';
        """)

        cursor.execute("""
    ALTER TABLE academic_record
    ALTER COLUMN grade DROP NOT NULL,
    ALTER COLUMN remarks DROP NOT NULL;
""")

        cursor.execute("""
    CREATE TABLE IF NOT EXISTS grade_history (
        history_id SERIAL PRIMARY KEY,
        record_id INTEGER,
        athlete_id INTEGER,
        student_name TEXT,
        subject_name TEXT,
        old_grade NUMERIC,
        new_grade NUMERIC,
        old_remarks TEXT,
        new_remarks TEXT,
        updated_by TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

        conn.commit()

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Setup Error", str(e))


def get_role_filter_sql(prefix=""):
    col = lambda name: f"{prefix}.{name}" if prefix else name

    if logged_role == "admin":
        return "", []

    if logged_role == "coach":
        return f" WHERE {col('sports_events')} = %s", [assigned_sport]

    if logged_role == "teacher":
        return f" WHERE {col('section')} = %s", [assigned_section]

    if logged_role == "parent":
        return f" WHERE {col('student_number')} = %s", [child_student_number]

    return " WHERE 1=0", []


def load_students():
    for row in tree.get_children():
        tree.delete(row)

    try:
        query = """
            SELECT athlete_id, student_number, full_name,
                   grade_level, section, strand, sports_events, status
            FROM student_athlete
            WHERE status = 'Active'
        """

        params = []

        selected_sport = sport_filter.get()
        selected_level = level_filter.get()

        if selected_sport != "All Sports":
            query += " AND sports_events = %s"
            params.append(selected_sport)

        if selected_level != "All":
            query += " AND level = %s"
            params.append(selected_level)

        query += """
            ORDER BY 
                CASE 
                    WHEN level = 'SHS' THEN 1
                    WHEN level = 'JHS' THEN 2
                    ELSE 3
                END,
                full_name;
        """

        cursor.execute(query, tuple(params))

        for row in cursor.fetchall():
            tree.insert("", tk.END, values=row)

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Load Students Error", str(e))


def search_student():
    keyword = search_entry.get().strip()

    for row in tree.get_children():
        tree.delete(row)

    try:
        cursor.execute("""
            SELECT athlete_id, student_number, full_name,
                   grade_level, section, strand, sports_events, status
            FROM student_athlete
            WHERE 
                CAST(student_number AS TEXT) ILIKE %s
                OR full_name ILIKE %s
                OR grade_level ILIKE %s
                OR section ILIKE %s
                OR strand ILIKE %s
                OR sports_events ILIKE %s
                OR level ILIKE %s
            ORDER BY full_name;
        """, (
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        ))

        results = cursor.fetchall()

        for row in results:
            tree.insert("", tk.END, values=row)

        messagebox.showinfo("Search Result", f"Found {len(results)} record(s).")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Search Error", str(e))


def filter_by_sport():
    selected_sport = sport_filter.get()

    for row in tree.get_children():
        tree.delete(row)

    if selected_sport == "All Sports":
        load_students()
        return

    try:
        cursor.execute("""
            SELECT athlete_id, student_number, full_name,
                   grade_level, section, strand, sports_events, status
            FROM student_athlete
            WHERE sports_events = %s
            ORDER BY full_name;
        """, (selected_sport,))

        for row in cursor.fetchall():
            tree.insert("", tk.END, values=row)

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Filter Error", str(e))


def view_grades():
    selected = tree.focus()

    if not selected:
        messagebox.showwarning("Warning", "Select a student first")
        return

    values = tree.item(selected, "values")
    athlete_id = values[0]
    name = values[2]

    cursor.execute("SELECT level FROM student_athlete WHERE athlete_id = %s", (athlete_id,))
    level_result = cursor.fetchone()
    student_level = level_result[0] if level_result and level_result[0] else "SHS"

    win = tk.Toplevel(root)
    win.title(f"Grades - {name}")
    win.geometry("1300x560")

    top_frame = tk.Frame(win)
    top_frame.pack(fill="x", padx=10, pady=8)

    tk.Label(top_frame, text=f"Student: {name}", font=("Arial", 12, "bold")).pack(side="left", padx=5)

    cursor.execute("""
        SELECT DISTINCT academic_year
        FROM academic_record
        WHERE athlete_id = %s
          AND academic_year IS NOT NULL
        ORDER BY academic_year;
    """, (athlete_id,))

    years = ["All"] + [row[0] for row in cursor.fetchall()]

    tk.Label(top_frame, text="Academic Year:").pack(side="left", padx=(30, 5))

    year_var = tk.StringVar(value="All")
    year_combo = ttk.Combobox(top_frame, textvariable=year_var, values=years, state="readonly", width=18)
    year_combo.pack(side="left", padx=5)

    if student_level == "JHS":
        cols = ("Record ID", "Subject", "Term", "Q1", "Q2", "Q3", "Q4", "Average Grade", "Teacher")
    else:
        cols = ("Record ID", "Subject", "Term", "Midterm", "Final", "Final Term Grade", "Teacher")

    table_frame = tk.Frame(win)
    table_frame.pack(fill="both", expand=True, padx=10, pady=5)

    scroll_y = tk.Scrollbar(table_frame, orient="vertical")
    scroll_x = tk.Scrollbar(table_frame, orient="horizontal")

    table = ttk.Treeview(
        table_frame,
        columns=cols,
        show="headings",
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set
    )

    scroll_y.config(command=table.yview)
    scroll_x.config(command=table.xview)

    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    table.pack(fill="both", expand=True)

    table.tag_configure("failed", background="#f8d7da")
    table.tag_configure("passed", background="#d4edda")
    table.tag_configure("term_header", background="#cfe2ff", font=("Arial", 10, "bold"))

    for c in cols:
        table.heading(c, text=c)

        if c == "Record ID":
            table.column(c, width=0, minwidth=0, stretch=False)
        elif c == "Subject":
            table.column(c, width=300, anchor="w")
        else:
            table.column(c, width=140, anchor="center")

    def load_grade_rows():
        for item in table.get_children():
            table.delete(item)

        selected_year = year_var.get()

        query = """
            SELECT 
                ar.record_id,
                COALESCE(ar.subject_name, s.subject_name) AS subject_name,
                ar.academic_year,
                ar.term,
                ar.midterm_grade,
                ar.final_grade,
                ar.q3_grade,
                ar.q4_grade,
                ar.final_term_grade,
                ar.teacher_name
            FROM academic_record ar
            LEFT JOIN subject s ON ar.subject_id = s.subject_id
            WHERE ar.athlete_id = %s
        """

        params = [athlete_id]

        if selected_year != "All":
            query += " AND ar.academic_year = %s"
            params.append(selected_year)

        query += " ORDER BY ar.term, COALESCE(ar.subject_name, s.subject_name);"

        try:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            current_term = None

            for r in rows:
                term = r[3]

                if term != current_term:
                    current_term = term

                    if student_level == "JHS":
                        header_values = ("", f"=== {term} Term ===", "", "", "", "", "", "", "")
                    else:
                        header_values = ("", f"=== {term} Term ===", "", "", "", "", "")

                    table.insert("", tk.END, values=header_values, tags=("term_header",))

                if student_level == "JHS":
                    display_values = (
                        r[0], r[1], r[3], r[4], r[5], r[6], r[7], r[8], r[9]
                    )
                else:
                    display_values = (
                        r[0], r[1], r[3], r[4], r[5], r[8], r[9]
                    )

                final_term_grade = r[8]

                if final_term_grade is not None and float(final_term_grade) <= 74:
                    table.insert("", tk.END, values=display_values, tags=("failed",))
                else:
                    table.insert("", tk.END, values=display_values, tags=("passed",))

        except Exception as e:
            conn.rollback()
            messagebox.showerror("View Grades Error", str(e))

    def edit_grade():
        selected_item = table.focus()

        if not selected_item:
            messagebox.showwarning("Warning", "Select a grade first")
            return

        row_values = table.item(selected_item, "values")

        if not row_values or row_values[0] == "":
            messagebox.showwarning("Warning", "Select a subject row, not term header")
            return

        record_id = row_values[0]
        subject = row_values[1]

        edit_win = tk.Toplevel(win)
        edit_win.title(f"Edit Grade - {subject}")
        edit_win.geometry("420x430")

        tk.Label(edit_win, text=f"Subject: {subject}", font=("Arial", 12, "bold")).pack(pady=10)

        if student_level == "JHS":
            labels = ["Q1", "Q2", "Q3", "Q4"]
            entries = []

            for i, label in enumerate(labels, start=3):
                tk.Label(edit_win, text=label).pack()
                entry = tk.Entry(edit_win)
                entry.insert(0, "" if row_values[i] == "None" else row_values[i])
                entry.pack()
                entries.append(entry)

            e_q1, e_q2, e_q3, e_q4 = entries

        else:
            tk.Label(edit_win, text="Midterm").pack()
            e_mid = tk.Entry(edit_win)
            e_mid.insert(0, "" if row_values[3] == "None" else row_values[3])
            e_mid.pack()

            tk.Label(edit_win, text="Final").pack()
            e_final = tk.Entry(edit_win)
            e_final.insert(0, "" if row_values[4] == "None" else row_values[4])
            e_final.pack()

        def to_num(v):
            try:
                if v.strip() == "":
                    return None
                return float(v)
            except:
                return None

        def update_grade():
            try:
                if student_level == "JHS":
                    q1 = to_num(e_q1.get())
                    q2 = to_num(e_q2.get())
                    q3 = to_num(e_q3.get())
                    q4 = to_num(e_q4.get())

                    grades = [g for g in [q1, q2, q3, q4] if g is not None]

                    if not grades:
                        messagebox.showwarning("Warning", "Enter at least one quarter grade")
                        return

                    final_term = round(sum(grades) / len(grades), 2)
                    mid = q1
                    fin = q2

                else:
                    mid = to_num(e_mid.get())
                    fin = to_num(e_final.get())

                    q1 = None
                    q2 = None
                    q3 = None
                    q4 = None

                    if mid is not None and fin is not None:
                        final_term = round((mid + fin) / 2, 2)
                    elif mid is not None:
                        final_term = mid
                    elif fin is not None:
                        final_term = fin
                    else:
                        messagebox.showwarning("Warning", "Enter midterm or final grade")
                        return

                status = "PASS" if final_term >= 75 else "FAILED"

                cursor.execute("""
                    SELECT 
                        ar.athlete_id,
                        sa.full_name,
                        COALESCE(ar.subject_name, s.subject_name),
                        ar.final_term_grade,
                        ar.remarks
                    FROM academic_record ar
                    JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
                    LEFT JOIN subject s ON ar.subject_id = s.subject_id
                    WHERE ar.record_id = %s;
                """, (record_id,))

                old_data = cursor.fetchone()

                if old_data:
                    cursor.execute("""
                        INSERT INTO grade_history
                        (record_id, athlete_id, student_name, subject_name,
                         old_grade, new_grade, old_remarks, new_remarks, updated_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        record_id,
                        old_data[0],
                        old_data[1],
                        old_data[2],
                        old_data[3],
                        final_term,
                        old_data[4],
                        status,
                        logged_username
                    ))

                cursor.execute("""
                    UPDATE academic_record
                    SET midterm_grade = %s,
                        final_grade = %s,
                        q1_grade = %s,
                        q2_grade = %s,
                        q3_grade = %s,
                        q4_grade = %s,
                        final_term_grade = %s,
                        grade = %s,
                        remarks = %s
                    WHERE record_id = %s;
                """, (
                    mid, fin, q1, q2, q3, q4,
                    final_term, final_term, status, record_id
                ))

                conn.commit()
                messagebox.showinfo("Success", "Grade updated!")
                edit_win.destroy()
                load_grade_rows()

            except Exception as e:
                conn.rollback()
                messagebox.showerror("Update Error", str(e))

        tk.Button(edit_win, text="Update Grade", command=update_grade, width=20).pack(pady=15)

    button_frame = tk.Frame(win)
    button_frame.pack(pady=8)

    tk.Button(
        button_frame,
        text="Edit Selected Grade",
        command=edit_grade,
        width=18
    ).grid(row=0, column=0, padx=5)

    year_combo.bind("<<ComboboxSelected>>", lambda e: load_grade_rows())

    load_grade_rows()

def view_failed_summary():
    messagebox.showinfo("Failed Summary", "Failed Summary report is working.")


def view_grade_status_summary():
    messagebox.showinfo("Grade Status Summary", "Grade Status Summary report is working.")

def generate_pdf_report():
    file_path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")],
        title="Save PDF Report"
    )

    if not file_path:
        return

    try:
        cursor.execute("""
            SELECT 
                sa.student_number,
                sa.full_name,
                sa.sports_events,
                ROUND(AVG(ar.final_term_grade), 2) AS gwa
            FROM student_athlete sa
            LEFT JOIN academic_record ar ON sa.athlete_id = ar.athlete_id
            GROUP BY sa.student_number, sa.full_name, sa.sports_events
            ORDER BY sa.sports_events, sa.full_name;
        """)

        rows = cursor.fetchall()

        pdf = canvas.Canvas(file_path)

        y = 800
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y, "AADO Student-Athlete Report")

        y -= 30
        pdf.setFont("Helvetica", 10)

        for row in rows:
            text = f"{row[0]} | {row[1]} | {row[2]} | GWA: {row[3]}"
            pdf.drawString(50, y, text)
            y -= 20

            if y < 50:
                pdf.showPage()
                y = 800

        pdf.save()

        messagebox.showinfo("Success", "PDF Generated Successfully!")

    except Exception as e:
        messagebox.showerror("Error", str(e))

def generate_sport_term_pdf_report():
    filter_win = tk.Toplevel(root)
    filter_win.title("Generate PDF Report")
    filter_win.geometry("400x420")

    tk.Label(
        filter_win,
        text="Generate Sport / Term PDF Report",
        font=("Arial", 14, "bold")
    ).pack(pady=15)

    cursor.execute("""
        SELECT DISTINCT academic_year
        FROM academic_record
        WHERE academic_year IS NOT NULL
        ORDER BY academic_year;
    """)
    years = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT DISTINCT sports_events
        FROM student_athlete
        WHERE sports_events IS NOT NULL
          AND sports_events != ''
        ORDER BY sports_events;
    """)
    sports = ["All Sports"] + [row[0] for row in cursor.fetchall()]

    tk.Label(filter_win, text="Academic Year").pack()
    year_var = tk.StringVar(value=years[0] if years else "")
    ttk.Combobox(filter_win, textvariable=year_var, values=years, state="readonly", width=25).pack(pady=5)

    tk.Label(filter_win, text="Term").pack()
    term_var = tk.StringVar(value="All Terms")
    ttk.Combobox(
        filter_win,
        textvariable=term_var,
        values=["All Terms", "1ST", "2ND", "3RD", "4TH"],
        state="readonly",
        width=25
    ).pack(pady=5)

    tk.Label(filter_win, text="Level").pack()
    level_var = tk.StringVar(value="SHS")
    ttk.Combobox(filter_win, textvariable=level_var, values=["SHS", "JHS"], state="readonly", width=25).pack(pady=5)

    tk.Label(filter_win, text="Grade Level").pack()
    grade_var = tk.StringVar(value="All Grades")
    ttk.Combobox(
        filter_win,
        textvariable=grade_var,
        values=["All Grades", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        state="readonly",
        width=25
    ).pack(pady=5)

    tk.Label(filter_win, text="Sport").pack()
    sport_var = tk.StringVar(value="All Sports")
    ttk.Combobox(filter_win, textvariable=sport_var, values=sports, state="readonly", width=25).pack(pady=5)

    def fmt(value):
        if value is None:
            return ""
        try:
            return str(int(round(float(value))))
        except Exception:
            return str(value)

    def create_pdf():
        academic_year = year_var.get()
        term = term_var.get()
        level = level_var.get()
        grade_level = grade_var.get()
        sport = sport_var.get()

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save PDF Report"
        )

        if not file_path:
            return

        try:
            query = """
                SELECT
                    sa.full_name,
                    sa.student_number,
                    sa.grade_level,
                    sa.sports_events,
                    ar.academic_year,
                    ar.term,
                    COALESCE(ar.subject_name, s.subject_name) AS subject_name,
                    ar.midterm_grade,
                    ar.final_grade,
                    ar.q1_grade,
                    ar.q2_grade,
                    ar.q3_grade,
                    ar.q4_grade,
                    ar.final_term_grade,
                    CASE
                        WHEN ar.final_term_grade IS NULL THEN 'NO GRADE'
                        WHEN ROUND(ar.final_term_grade) >= 75 THEN 'PASS'
                        ELSE 'FAILED'
                    END AS status
                FROM academic_record ar
                JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
                LEFT JOIN subject s ON ar.subject_id = s.subject_id
                WHERE ar.academic_year = %s
                  AND sa.level = %s
                  AND sa.status = 'Active'
            """

            params = [academic_year, level]

            if term != "All Terms":
                query += " AND UPPER(ar.term) = UPPER(%s)"
                params.append(term)

            if grade_level != "All Grades":
                query += " AND sa.grade_level = %s"
                params.append(grade_level)

            if sport != "All Sports":
                query += " AND sa.sports_events = %s"
                params.append(sport)

            query += """
                ORDER BY sa.full_name, ar.term, subject_name;
            """

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            if not rows:
                messagebox.showinfo("No Data", "No records found.")
                return

            doc = SimpleDocTemplate(
                file_path,
                pagesize=landscape(A4),
                rightMargin=10,
                leftMargin=10,
                topMargin=20,
                bottomMargin=20
            )

            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                "TitleStyle",
                parent=styles["Title"],
                fontSize=12,
                leading=14,
                alignment=1
            )

            cell_style = ParagraphStyle(
                "CellStyle",
                parent=styles["Normal"],
                fontSize=6,
                leading=7
            )

            elements = []

            title_text = f"{term} {level} ASSESSMENT REPORT<br/>AY {academic_year}"
            elements.append(Paragraph(f"<b>{title_text}</b>", title_style))
            elements.append(Spacer(1, 10))

            if level == "JHS":
                headers = [
                    "Fullname", "Student ID No.", "Grade", "Sports / Events",
                    "AY", "Term", "Subject", "Q1", "Q2", "Q3", "Q4",
                    "Average", "Status"
                ]
                col_widths = [85, 60, 40, 65, 45, 35, 200, 35, 35, 35, 35, 45, 50]
            else:
                headers = [
                    "Fullname", "Student ID No.", "Grade", "Sports / Events",
                    "AY", "Term", "Subject", "Midterm", "Final",
                    "Final Term Grade", "Status"
                ]
                col_widths = [95, 65, 45, 75, 50, 35, 240, 45, 45, 65, 50]

            data = [headers]
            last_name = None

            for r in rows:
                same_student = r[0] == last_name

                base_data = [
                    "" if same_student else Paragraph(str(r[0]), cell_style),
                    "" if same_student else str(r[1]),
                    "" if same_student else str(r[2]),
                    "" if same_student else Paragraph(str(r[3]), cell_style),
                    str(r[4]),
                    str(r[5]),
                    Paragraph(str(r[6]), cell_style),
                ]

                if level == "JHS":
                    row_data = base_data + [
                        fmt(r[9]),
                        fmt(r[10]),
                        fmt(r[11]),
                        fmt(r[12]),
                        fmt(r[13]),
                        r[14]
                    ]
                else:
                    row_data = base_data + [
                        fmt(r[7]),
                        fmt(r[8]),
                        fmt(r[13]),
                        r[14]
                    ]

                data.append(row_data)
                last_name = r[0]

            table = Table(data, colWidths=col_widths, repeatRows=1)

            table_style = TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ])

            status_col = len(headers) - 1

            for i, row in enumerate(data):
                if i == 0:
                    continue

                if row[-1] == "FAILED":
                    table_style.add("BACKGROUND", (status_col, i), (status_col, i), colors.pink)
                    table_style.add("TEXTCOLOR", (status_col, i), (status_col, i), colors.red)
                    table_style.add("FONTNAME", (status_col, i), (status_col, i), "Helvetica-Bold")

                elif row[-1] == "NO GRADE":
                    table_style.add("BACKGROUND", (status_col, i), (status_col, i), colors.whitesmoke)
                    table_style.add("TEXTCOLOR", (status_col, i), (status_col, i), colors.grey)

            table.setStyle(table_style)

            elements.append(table)
            elements.append(Spacer(1, 25))

            prepared = Paragraph(
                "<b>Prepared By:</b><br/><br/><br/>_________________________<br/>"
                "Mathias Villacarlos Jr.<br/>AADO Associate",
                styles["Normal"]
            )

            noted = Paragraph(
                "<b>Noted By:</b><br/><br/><br/>_________________________<br/>"
                "Ms. Maria Ester V. Suarez<br/>Assistant Director, AADO",
                styles["Normal"]
            )

            sign_table = Table([[prepared, noted]], colWidths=[350, 350])
            sign_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]))

            elements.append(sign_table)

            doc.build(elements)

            messagebox.showinfo("Success", "PDF report generated successfully!")
            filter_win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("PDF Error", str(e))

    tk.Button(
        filter_win,
        text="Generate PDF",
        command=create_pdf,
        width=20
    ).pack(pady=20)

def generate_revision_remedial_report():
    filter_win = tk.Toplevel(root)
    filter_win.title("Revision / Remedial Report")
    filter_win.geometry("400x430")

    tk.Label(
        filter_win,
        text="Generate Revision / Remedial Report",
        font=("Arial", 14, "bold")
    ).pack(pady=15)

    cursor.execute("""
        SELECT DISTINCT academic_year
        FROM academic_record
        WHERE academic_year IS NOT NULL
        ORDER BY academic_year;
    """)
    years = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT DISTINCT sports_events
        FROM student_athlete
        WHERE sports_events IS NOT NULL
          AND sports_events != ''
        ORDER BY sports_events;
    """)
    sports = ["All Sports"] + [row[0] for row in cursor.fetchall()]

    tk.Label(filter_win, text="Academic Year").pack()
    year_var = tk.StringVar(value=years[0] if years else "")
    ttk.Combobox(filter_win, textvariable=year_var, values=years, state="readonly", width=25).pack(pady=5)

    tk.Label(filter_win, text="Term").pack()
    term_var = tk.StringVar(value="All Terms")
    ttk.Combobox(
        filter_win,
        textvariable=term_var,
        values=["All Terms", "1ST", "2ND", "3RD", "4TH"],
        state="readonly",
        width=25
    ).pack(pady=5)

    tk.Label(filter_win, text="Level").pack()
    level_var = tk.StringVar(value="SHS")
    ttk.Combobox(filter_win, textvariable=level_var, values=["SHS", "JHS"], state="readonly", width=25).pack(pady=5)

    tk.Label(filter_win, text="Grade Level").pack()
    grade_var = tk.StringVar(value="All Grades")
    ttk.Combobox(
        filter_win,
        textvariable=grade_var,
        values=["All Grades", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        state="readonly",
        width=25
    ).pack(pady=5)

    tk.Label(filter_win, text="Sport").pack()
    sport_var = tk.StringVar(value="All Sports")
    ttk.Combobox(filter_win, textvariable=sport_var, values=sports, state="readonly", width=25).pack(pady=5)

    def create_pdf():
        academic_year = year_var.get()
        term = term_var.get()
        level = level_var.get()
        grade_level = grade_var.get()
        sport = sport_var.get()

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save Revision / Remedial Report"
        )

        if not file_path:
            return

        try:
            query = """
                SELECT
                    sa.full_name,
                    sa.student_number,
                    sa.grade_level,
                    sa.sports_events,
                    ar.academic_year,
                    ar.term,
                    COALESCE(ar.subject_name, s.subject_name) AS subject_name,
                    ROUND(ar.final_term_grade) AS rounded_grade,
                    CASE
                        WHEN ROUND(ar.final_term_grade) = 70 THEN 'FOR REVISION'
                        WHEN ROUND(ar.final_term_grade) BETWEEN 71 AND 74 THEN 'FOR REMEDIAL'
                    END AS intervention
                FROM academic_record ar
                JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
                LEFT JOIN subject s ON ar.subject_id = s.subject_id
                WHERE ar.academic_year = %s
                  AND sa.level = %s
                  AND sa.status = 'Active'
                  AND ar.final_term_grade IS NOT NULL
                  AND ROUND(ar.final_term_grade) BETWEEN 70 AND 74
            """

            params = [academic_year, level]

            if term != "All Terms":
                query += " AND UPPER(ar.term) = UPPER(%s)"
                params.append(term)

            if grade_level != "All Grades":
                query += " AND sa.grade_level = %s"
                params.append(grade_level)

            if sport != "All Sports":
                query += " AND sa.sports_events = %s"
                params.append(sport)

            query += """
                ORDER BY sa.sports_events, sa.grade_level, sa.full_name, ar.term, rounded_grade, subject_name;
            """

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            if not rows:
                messagebox.showinfo("No Data", "No students found for Revision or Remedial.")
                return

            doc = SimpleDocTemplate(
                file_path,
                pagesize=landscape(A4),
                rightMargin=15,
                leftMargin=15,
                topMargin=20,
                bottomMargin=20
            )

            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                "TitleStyle",
                parent=styles["Title"],
                fontSize=12,
                leading=14,
                alignment=1
            )

            cell_style = ParagraphStyle(
                "CellStyle",
                parent=styles["Normal"],
                fontSize=7,
                leading=8
            )

            elements = []

            elements.append(Paragraph(
                f"<b>REVISION / REMEDIAL REPORT</b><br/>"
                f"AY {academic_year} | {term} | {level} | {grade_level} | {sport}",
                title_style
            ))
            elements.append(Spacer(1, 12))

            data = [[
                "Fullname",
                "Student ID No.",
                "Grade",
                "Sports / Events",
                "AY",
                "Term",
                "Subject",
                "Grade",
                "Intervention"
            ]]

            revision_count = 0
            remedial_count = 0
            last_name = None

            for r in rows:
                intervention = r[8]

                if intervention == "FOR REVISION":
                    revision_count += 1
                elif intervention == "FOR REMEDIAL":
                    remedial_count += 1

                same_student = r[0] == last_name

                data.append([
                    "" if same_student else Paragraph(str(r[0]), cell_style),
                    "" if same_student else str(r[1]),
                    "" if same_student else str(r[2]),
                    "" if same_student else Paragraph(str(r[3]), cell_style),
                    str(r[4]),
                    str(r[5]),
                    Paragraph(str(r[6]), cell_style),
                    str(int(r[7])),
                    intervention
                ])

                last_name = r[0]

            table = Table(
                data,
                colWidths=[110, 75, 55, 100, 65, 45, 230, 50, 100],
                repeatRows=1
            )

            table_style = TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (1, 1), (5, -1), "CENTER"),
                ("ALIGN", (7, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])

            intervention_col = 8

            for i, row in enumerate(data):
                if i == 0:
                    continue

                if row[-1] == "FOR REVISION":
                    table_style.add("BACKGROUND", (intervention_col, i), (intervention_col, i), colors.pink)
                    table_style.add("TEXTCOLOR", (intervention_col, i), (intervention_col, i), colors.red)
                    table_style.add("FONTNAME", (intervention_col, i), (intervention_col, i), "Helvetica-Bold")

                elif row[-1] == "FOR REMEDIAL":
                    table_style.add("BACKGROUND", (intervention_col, i), (intervention_col, i), colors.lightyellow)
                    table_style.add("TEXTCOLOR", (intervention_col, i), (intervention_col, i), colors.darkorange)
                    table_style.add("FONTNAME", (intervention_col, i), (intervention_col, i), "Helvetica-Bold")

            table.setStyle(table_style)
            elements.append(table)
            elements.append(Spacer(1, 15))

            summary_data = [
                ["FOR REVISION", "FOR REMEDIAL", "TOTAL"],
                [revision_count, remedial_count, revision_count + remedial_count]
            ]

            summary_table = Table(summary_data, colWidths=[120, 120, 100])
            summary_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 1), (-1, -1), "CENTER"),
            ]))

            elements.append(summary_table)

            doc.build(elements)

            messagebox.showinfo("Success", "Revision / Remedial PDF generated successfully!")
            filter_win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("PDF Error", str(e))

    tk.Button(
        filter_win,
        text="Generate PDF",
        command=create_pdf,
        width=20
    ).pack(pady=20)

def add_intervention_remarks():
    win = tk.Toplevel(root)
    win.title("Add Intervention Remarks")
    win.geometry("1250x650")

    tk.Label(
        win,
        text="Revision / Remedial Students - Add Remarks",
        font=("Arial", 14, "bold")
    ).pack(pady=10)

    # ===== FILTER AREA =====
    filter_frame = tk.LabelFrame(win, text=" Search & Filter ", padx=10, pady=10)
    filter_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(filter_frame, text="Search").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    search_var = tk.StringVar()
    search_entry = tk.Entry(filter_frame, textvariable=search_var, width=35)
    search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

    cursor.execute("""
        SELECT DISTINCT academic_year
        FROM academic_record
        WHERE academic_year IS NOT NULL
        ORDER BY academic_year;
    """)
    years = ["All Years"] + [row[0] for row in cursor.fetchall()]

    tk.Label(filter_frame, text="Academic Year").grid(row=0, column=2, padx=5, pady=5, sticky="w")
    year_var = tk.StringVar(value="All Years")
    year_combo = ttk.Combobox(filter_frame, textvariable=year_var, values=years, state="readonly", width=15)
    year_combo.grid(row=0, column=3, padx=5, pady=5)

    tk.Label(filter_frame, text="Term").grid(row=0, column=4, padx=5, pady=5, sticky="w")
    term_var = tk.StringVar(value="All Terms")
    term_combo = ttk.Combobox(
        filter_frame,
        textvariable=term_var,
        values=["All Terms", "1ST", "2ND", "3RD", "4TH"],
        state="readonly",
        width=12
    )
    term_combo.grid(row=0, column=5, padx=5, pady=5)

    tk.Label(filter_frame, text="Grade").grid(row=1, column=0, padx=5, pady=5, sticky="w")
    grade_var = tk.StringVar(value="All Grades")
    grade_combo = ttk.Combobox(
        filter_frame,
        textvariable=grade_var,
        values=[
            "All Grades",
            "Grade 7",
            "Grade 8",
            "Grade 9",
            "Grade 10",
            "Grade 11",
            "Grade 12"
        ],
        state="readonly",
        width=15
    )
    grade_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    cursor.execute("""
        SELECT DISTINCT sports_events
        FROM student_athlete
        WHERE sports_events IS NOT NULL
          AND sports_events != ''
        ORDER BY sports_events;
    """)
    sports = ["All Sports"] + [row[0] for row in cursor.fetchall()]

    tk.Label(filter_frame, text="Sport").grid(row=1, column=2, padx=5, pady=5, sticky="w")
    sport_var = tk.StringVar(value="All Sports")
    sport_combo = ttk.Combobox(filter_frame, textvariable=sport_var, values=sports, state="readonly", width=25)
    sport_combo.grid(row=1, column=3, padx=5, pady=5, sticky="w")

    filter_frame.grid_columnconfigure(1, weight=1)

    # ===== TABLE =====
    cols = (
        "Record ID",
        "Student ID",
        "Name",
        "Grade",
        "Sports",
        "AY",
        "Term",
        "Subject",
        "Grade Value",
        "Intervention",
        "Remarks"
    )

    table_frame = tk.Frame(win)
    table_frame.pack(fill="both", expand=True, padx=10, pady=10)

    scroll_y = tk.Scrollbar(table_frame, orient="vertical")
    scroll_x = tk.Scrollbar(table_frame, orient="horizontal")

    table = ttk.Treeview(
        table_frame,
        columns=cols,
        show="headings",
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set
    )

    scroll_y.config(command=table.yview)
    scroll_x.config(command=table.xview)

    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    table.pack(fill="both", expand=True)

    for col in cols:
        table.heading(col, text=col)
        table.column(col, width=120, anchor="w")

    table.column("Record ID", width=0, minwidth=0, stretch=False)
    table.column("Student ID", width=110)
    table.column("Name", width=190)
    table.column("Grade", width=90)
    table.column("Sports", width=150)
    table.column("AY", width=90)
    table.column("Term", width=70)
    table.column("Subject", width=260)
    table.column("Grade Value", width=90, anchor="center")
    table.column("Intervention", width=130)
    table.column("Remarks", width=300)

    def load_records():
        for item in table.get_children():
            table.delete(item)

        keyword = search_var.get().strip()
        selected_year = year_var.get()
        selected_term = term_var.get()
        selected_grade = grade_var.get()
        selected_sport = sport_var.get()

        try:
            query = """
                SELECT
                    ar.record_id,
                    sa.student_number,
                    sa.full_name,
                    sa.grade_level,
                    sa.sports_events,
                    ar.academic_year,
                    ar.term,
                    COALESCE(ar.subject_name, s.subject_name) AS subject_name,
                    ROUND(ar.final_term_grade) AS rounded_grade,
                    CASE
                        WHEN ROUND(ar.final_term_grade) = 70 THEN 'FOR REVISION'
                        WHEN ROUND(ar.final_term_grade) BETWEEN 71 AND 74 THEN 'FOR REMEDIAL'
                    END AS intervention,
                    COALESCE(ar.intervention_remarks, '') AS remarks
                FROM academic_record ar
                JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
                LEFT JOIN subject s ON ar.subject_id = s.subject_id
                WHERE sa.status = 'Active'
                  AND ar.final_term_grade IS NOT NULL
                  AND ROUND(ar.final_term_grade) BETWEEN 70 AND 74
            """

            params = []

            if keyword:
                query += """
                    AND (
                        CAST(sa.student_number AS TEXT) ILIKE %s
                        OR sa.full_name ILIKE %s
                        OR sa.grade_level ILIKE %s
                        OR sa.sports_events ILIKE %s
                        OR COALESCE(ar.subject_name, s.subject_name) ILIKE %s
                    )
                """
                like_keyword = f"%{keyword}%"
                params.extend([like_keyword, like_keyword, like_keyword, like_keyword, like_keyword])

            if selected_year != "All Years":
                query += " AND ar.academic_year = %s"
                params.append(selected_year)

            if selected_term != "All Terms":
                query += " AND UPPER(ar.term) = UPPER(%s)"
                params.append(selected_term)

            if selected_grade != "All Grades":
                query += " AND sa.grade_level = %s"
                params.append(selected_grade)

            if selected_sport != "All Sports":
                query += " AND sa.sports_events = %s"
                params.append(selected_sport)

            query += """
                ORDER BY sa.grade_level, sa.sports_events, sa.full_name, ar.term, subject_name;
            """

            cursor.execute(query, tuple(params))

            for row in cursor.fetchall():
                table.insert("", tk.END, values=row)

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Load Remarks Error", str(e))

    def clear_filters():
        search_var.set("")
        year_var.set("All Years")
        term_var.set("All Terms")
        grade_var.set("All Grades")
        sport_var.set("All Sports")
        load_records()

    def edit_remarks():
        selected = table.focus()

        if not selected:
            messagebox.showwarning("Warning", "Select a record first.")
            return

        values = table.item(selected, "values")
        record_id = values[0]
        student_name = values[2]
        subject_name = values[7]
        current_remarks = values[10]

        remark_win = tk.Toplevel(win)
        remark_win.title("Edit Remarks")
        remark_win.geometry("520x380")

        tk.Label(
            remark_win,
            text=f"{student_name}",
            font=("Arial", 12, "bold")
        ).pack(pady=(15, 5))

        tk.Label(
            remark_win,
            text=f"Subject: {subject_name}",
            font=("Arial", 10)
        ).pack(pady=(0, 10))

        remarks_text = tk.Text(remark_win, width=58, height=9, font=("Arial", 11))
        remarks_text.pack(padx=15, pady=10)
        remarks_text.insert("1.0", current_remarks)

        def save_remarks():
            remarks = remarks_text.get("1.0", tk.END).strip()

            try:
                cursor.execute("""
                    UPDATE academic_record
                    SET intervention_remarks = %s
                    WHERE record_id = %s;
                """, (remarks, record_id))

                conn.commit()
                messagebox.showinfo("Success", "Remarks saved successfully!")
                remark_win.destroy()
                load_records()

            except Exception as e:
                conn.rollback()
                messagebox.showerror("Save Remarks Error", str(e))

        tk.Button(
            remark_win,
            text="Save Remarks",
            command=save_remarks,
            width=20
        ).pack(pady=10)

    # ===== BUTTONS =====
    button_frame = tk.Frame(win)
    button_frame.pack(pady=8)

    tk.Button(
        filter_frame,
        text="Search / Apply Filter",
        command=load_records,
        width=18
    ).grid(row=1, column=4, padx=5, pady=5)

    tk.Button(
        filter_frame,
        text="Clear",
        command=clear_filters,
        width=12
    ).grid(row=1, column=5, padx=5, pady=5)

    tk.Button(
        button_frame,
        text="Edit / Add Remarks",
        command=edit_remarks,
        width=20
    ).grid(row=0, column=0, padx=5)

    tk.Button(
        button_frame,
        text="Refresh",
        command=load_records,
        width=15
    ).grid(row=0, column=1, padx=5)

    search_entry.bind("<Return>", lambda e: load_records())

    load_records()

def view_summary():
    win = tk.Toplevel(root)
    win.title("GWA Summary per Term")
    win.geometry("1000x500")

    cols = ("ID", "Subject", "Year", "Term", "Q1/Midterm", "Q2/Final", "Q3", "Q4", "Average/Final Term", "Teacher")
    table = ttk.Treeview(win, columns=cols, show="headings")

    table.tag_configure("term_header", background="#cfe2ff", font=("Arial", 10, "bold"))
    table.tag_configure("good", background="#d4edda")
    table.tag_configure("warning", background="#fff3cd")
    table.tag_configure("risk", background="#f8d7da")

    for c in cols:
        table.heading(c, text=c)
        table.column(c, width=150)

    table.pack(fill=tk.BOTH, expand=True)

    try:
        cursor.execute("""
            SELECT 
                sa.student_number,
                sa.full_name,
                ar.academic_year,
                ar.term,
                ROUND(AVG(ar.final_term_grade), 2) AS gwa,
                CASE
                    WHEN AVG(ar.final_term_grade) >= 85 THEN 'Good Standing'
                    WHEN AVG(ar.final_term_grade) >= 75 THEN 'Warning'
                    ELSE 'At Risk'
                END AS status
            FROM student_athlete sa
            JOIN academic_record ar ON sa.athlete_id = ar.athlete_id
            WHERE ar.final_term_grade IS NOT NULL
            GROUP BY sa.student_number, sa.full_name, ar.academic_year, ar.term
            ORDER BY ar.term, sa.full_name;
        """)

        rows = cursor.fetchall()
        current_term = None

        for row in rows:
            term = row[3]

            if term != current_term:
                current_term = term
                table.insert(
                    "",
                    tk.END,
                    values=("", f"=== {term} Term ===", "", "", "", ""),
                    tags=("term_header",)
                )

            status = row[5]

            if status == "Good Standing":
                tag = "good"
            elif status == "Warning":
                tag = "warning"
            else:
                tag = "risk"

            table.insert("", tk.END, values=row, tags=(tag,))

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Summary Error", str(e))


def view_sports_count():
    win = tk.Toplevel(root)
    win.title("Student-Athletes per Sports")
    win.geometry("600x400")

    tk.Label(
        win,
        text="Number of Student-Athletes per Sports",
        font=("Arial", 14, "bold")
    ).pack(pady=10)

    cols = ("Sports Event", "Total Athletes")
    table = ttk.Treeview(win, columns=cols, show="headings")



# 👉 DITO MO ILALAGAY
    table["columns"] = ("Sports Event", "Total Athletes")

    table.heading("Sports Event", text="Sports Event")
    table.column("Sports Event", width=350, anchor="w")

    table.heading("Total Athletes", text="Total Athletes", anchor="center")
    table.column("Total Athletes", width=150, anchor="center")

    table.pack(fill=tk.BOTH, expand=True) 

    table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    try:
        cursor.execute("""
            SELECT 
                sports_events,
                COUNT(*) AS total_athletes
            FROM student_athlete
            WHERE sports_events IS NOT NULL
              AND sports_events != ''
            GROUP BY sports_events
            ORDER BY total_athletes DESC, sports_events;
        """)

        rows = cursor.fetchall()

        total = 0

        for row in rows:
            table.insert("", tk.END, values=row)
            total += row[1]


        table.insert("", tk.END, values=("", ""))


        table.insert("", tk.END, values=("TOTAL", total))

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Sports Count Error", str(e))


def view_student_term_gwa():
    selected = tree.focus()

    if not selected:
        messagebox.showwarning("Warning", "Select a student first")
        return

    values = tree.item(selected, "values")
    athlete_id = values[0]
    name = values[2]

    win = tk.Toplevel(root)
    win.title(f"Term GWA - {name}")
    win.geometry("800x400")

    cols = ("Academic Year", "Term", "GWA", "Status")
    table = ttk.Treeview(win, columns=cols, show="headings")

    table.tag_configure("good", background="#d4edda")
    table.tag_configure("warning", background="#fff3cd")
    table.tag_configure("risk", background="#f8d7da")

    for c in cols:
        table.heading(c, text=c)
        table.column(c, width=180)

    table.pack(fill=tk.BOTH, expand=True)

    try:
        cursor.execute("""
            SELECT
                academic_year,
                term,
                ROUND(AVG(final_term_grade), 2) AS gwa,
                CASE
                    WHEN AVG(final_term_grade) >= 85 THEN 'Good Standing'
                    WHEN AVG(final_term_grade) >= 75 THEN 'Warning'
                    ELSE 'At Risk'
                END AS status
            FROM academic_record
            WHERE athlete_id = %s
            GROUP BY academic_year, term
            ORDER BY academic_year, term;
        """, (athlete_id,))

        rows = cursor.fetchall()

        if not rows:
            messagebox.showinfo("Info", "No GWA records found")
            return

        for row in rows:
            status = row[3]

            if status == "Good Standing":
                tag = "good"
            elif status == "Warning":
                tag = "warning"
            else:
                tag = "risk"

            table.insert("", tk.END, values=row, tags=(tag,))

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Student Term GWA Error", str(e))


def add_student():
    win = tk.Toplevel(root)
    win.title("Add Student")
    win.geometry("400x350")

    form = tk.Frame(win)
    form.pack(pady=10, padx=10, fill="both", expand=True)

    # fields
    tk.Label(form, text="Student ID").grid(row=0, column=0, sticky="w")
    entry_id = tk.Entry(form)
    entry_id.grid(row=0, column=1, sticky="ew")

    tk.Label(form, text="Full Name").grid(row=1, column=0, sticky="w")
    entry_name = tk.Entry(form)
    entry_name.grid(row=1, column=1, sticky="ew")

    tk.Label(form, text="Grade Level").grid(row=2, column=0, sticky="w")
    entry_grade = tk.Entry(form)
    entry_grade.grid(row=2, column=1, sticky="ew")

    tk.Label(form, text="Section").grid(row=3, column=0, sticky="w")
    entry_section = tk.Entry(form)
    entry_section.grid(row=3, column=1, sticky="ew")

    tk.Label(form, text="Strand").grid(row=4, column=0, sticky="w")
    entry_strand = tk.Entry(form)
    entry_strand.grid(row=4, column=1, sticky="ew")

    tk.Label(form, text="Sports Event").grid(row=5, column=0, sticky="w")
    entry_sports = tk.Entry(form)
    entry_sports.grid(row=5, column=1, sticky="ew")

    # auto stretch
    form.grid_columnconfigure(1, weight=1)

    # SAVE FUNCTION (IMPORTANT)
    def save_student():
        try:
            cursor.execute("""
                INSERT INTO student_athlete
                (student_number, full_name, course, year_level,
                 grade_level, section, strand, sports_events, level,
                 sport_id, coach_id, status)
                VALUES (%s, %s, 'Manual', 12, %s, %s, %s, %s, 'Manual', 1, 1, 'Active');
            """, (
                entry_id.get(),
                entry_name.get(),
                entry_grade.get(),
                entry_section.get(),
                entry_strand.get(),
                entry_sports.get()
            ))

            conn.commit()
            load_students()
            load_dashboard()

            messagebox.showinfo("Success", "Student added!")
            win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))

    tk.Button(win, text="Save Student", command=save_student).pack(pady=15)


def logout():
    root.withdraw()
    login_win.deiconify()
    entry_user.delete(0, tk.END)
    entry_pass.delete(0, tk.END)


def college_logout():
    college_root.withdraw()
    login_win.deiconify()
    entry_user.delete(0, tk.END)
    entry_pass.delete(0, tk.END)


def add_college_student():
    win = tk.Toplevel(college_root)
    win.title("Add College Student-Athlete")
    win.geometry("450x420")
    win.configure(bg="#eef2f7")

    form = tk.Frame(win, bg="#eef2f7")
    form.pack(padx=25, pady=25, fill="both", expand=True)

    tk.Label(
        form,
        text="Add College Student-Athlete",
        bg="#eef2f7",
        font=("Arial", 16, "bold")
    ).grid(row=0, column=0, columnspan=2, pady=15)

    labels = ["Student ID", "Full Name", "Course", "Year Level", "Sports Event"]
    entries = {}

    for i, label in enumerate(labels, start=1):
        tk.Label(
            form,
            text=label,
            bg="#eef2f7",
            font=("Arial", 11)
        ).grid(row=i, column=0, sticky="w", pady=6)

        entry = tk.Entry(form, font=("Arial", 11))
        entry.grid(row=i, column=1, sticky="ew", pady=6, ipady=4)
        entries[label] = entry

    form.grid_columnconfigure(1, weight=1)

    def save_college_student():
        student_id = entries["Student ID"].get().strip()
        full_name = entries["Full Name"].get().strip()
        course = entries["Course"].get().strip()
        year_level = entries["Year Level"].get().strip()
        sports_event = entries["Sports Event"].get().strip()

        if not student_id or not full_name or not course or not year_level:
            messagebox.showwarning("Warning", "Please fill all required fields.")
            return

        try:
            cursor.execute("""
                INSERT INTO student_athlete
                (student_number, full_name, course, year_level,
                 grade_level, section, strand, sports_events, level,
                 sport_id, coach_id, status)
                VALUES (%s, %s, %s, %s, NULL, NULL, NULL, %s, 'College', 1, 1, 'Active')
                ON CONFLICT (student_number)
                DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    course = EXCLUDED.course,
                    year_level = EXCLUDED.year_level,
                    sports_events = EXCLUDED.sports_events,
                    level = 'College',
                    status = 'Active';
            """, (
                student_id,
                full_name,
                course,
                year_level,
                sports_event
            ))

            conn.commit()
            load_college_students()
            messagebox.showinfo("Success", "College student added successfully!")
            win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Add College Student Error", str(e))

    tk.Button(
        form,
        text="Save Student",
        command=save_college_student,
        width=20
    ).grid(row=6, column=0, columnspan=2, pady=20)

def add_subject_grades():
    selected = tree.focus()

    if not selected:
        messagebox.showwarning("Warning", "Select a student first")
        return

    values = tree.item(selected, "values")
    athlete_id = values[0]
    student_name = values[2]

    win = tk.Toplevel(root)
    win.title(f"Add Subjects / Grades - {student_name}")
    win.geometry("1250x520")

    tk.Label(
        win,
        text=f"Student: {student_name}",
        font=("Arial", 14, "bold")
    ).pack(pady=10)

    table_frame = tk.Frame(win)
    table_frame.pack(pady=5)

    columns = [
        "Term", "Subject Name", "Teacher Name", "Level",
        "Midterm", "Final", "Q1", "Q2", "Q3", "Q4"
    ]

    col_width = 14

    for i, col in enumerate(columns):
        tk.Label(
            table_frame,
            text=col,
            font=("Arial", 10, "bold"),
            width=col_width,
            borderwidth=1,
            relief="solid",
            anchor="center"
        ).grid(row=0, column=i, sticky="nsew")

    entry_rows = []

    def create_entry(row, col):
        entry = tk.Entry(table_frame, width=col_width, justify="center")
        entry.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
        return entry

    def create_option(variable, options, row, col):
        menu = tk.OptionMenu(table_frame, variable, *options)
        menu.config(width=col_width - 2)
        menu.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
        return menu

    def add_row():
        row_index = len(entry_rows) + 1

        term_var = tk.StringVar(value="1st")
        level_var = tk.StringVar(value="SHS")

        row_widgets = {}

        create_option(term_var, ["1st", "2nd", "3rd", "4th"], row_index, 0)
        row_widgets["term"] = term_var

        row_widgets["subject"] = create_entry(row_index, 1)
        row_widgets["teacher"] = create_entry(row_index, 2)

        create_option(level_var, ["SHS", "JHS"], row_index, 3)
        row_widgets["level"] = level_var

        row_widgets["midterm"] = create_entry(row_index, 4)
        row_widgets["final"] = create_entry(row_index, 5)
        row_widgets["q1"] = create_entry(row_index, 6)
        row_widgets["q2"] = create_entry(row_index, 7)
        row_widgets["q3"] = create_entry(row_index, 8)
        row_widgets["q4"] = create_entry(row_index, 9)

        entry_rows.append(row_widgets)

    def to_number(value):
        try:
            if value.strip() == "":
                return None
            return float(value)
        except:
            return None

    def save_all():
        academic_year = "2025-2026"
        saved_count = 0

        try:
            for row in entry_rows:
                term = row["term"].get()
                subject_name = row["subject"].get().strip()
                teacher_name = row["teacher"].get().strip()
                level = row["level"].get()

                if not subject_name:
                    continue

                midterm_grade = to_number(row["midterm"].get())
                final_grade = to_number(row["final"].get())

                q1_grade = to_number(row["q1"].get())
                q2_grade = to_number(row["q2"].get())
                q3_grade = to_number(row["q3"].get())
                q4_grade = to_number(row["q4"].get())

                final_term_grade = None

                if level == "JHS":
                    grades = [
                        g for g in [q1_grade, q2_grade, q3_grade, q4_grade]
                        if g is not None
                    ]

                    if grades:
                        final_term_grade = round(sum(grades) / len(grades), 2)

                    midterm_grade = q1_grade
                    final_grade = q2_grade

                else:
                    if midterm_grade is not None and final_grade is not None:
                        final_term_grade = round((midterm_grade + final_grade) / 2, 2)
                    elif midterm_grade is not None:
                        final_term_grade = midterm_grade
                    elif final_grade is not None:
                        final_term_grade = final_grade

                    q1_grade = None
                    q2_grade = None
                    q3_grade = None
                    q4_grade = None

                if final_term_grade is None:
                    status = "NO GRADE"
                else:
                    status = "PASS" if final_term_grade >= 75 else "FAILED"

                cursor.execute("""
                    INSERT INTO subject (subject_code, subject_name, units)
                    VALUES (%s, %s, 3)
                    ON CONFLICT (subject_code)
                    DO UPDATE SET subject_name = EXCLUDED.subject_name, units = 3
                    RETURNING subject_id;
                """, (subject_name, subject_name))

                subject_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO academic_record
                    (athlete_id, subject_id, semester, school_year, grade, remarks,
                     academic_year, term, midterm_grade, final_grade,
                     q1_grade, q2_grade, q3_grade, q4_grade,
                     final_term_grade, teacher_name, subject_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    athlete_id,
                    subject_id,
                    term,
                    academic_year,
                    final_term_grade,
                    status,
                    academic_year,
                    term,
                    midterm_grade,
                    final_grade,
                    q1_grade,
                    q2_grade,
                    q3_grade,
                    q4_grade,
                    final_term_grade,
                    teacher_name,
                    subject_name
                ))

                saved_count += 1

            conn.commit()
            messagebox.showinfo("Success", f"{saved_count} subject(s) saved!")
            win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Save Error", str(e))

    button_frame = tk.Frame(win)
    button_frame.pack(pady=15)

    tk.Button(
        button_frame,
        text="Add Row",
        command=add_row,
        width=15
    ).grid(row=0, column=0, padx=5)

    tk.Button(
        button_frame,
        text="Save All",
        command=save_all,
        width=15
    ).grid(row=0, column=1, padx=5)

    add_row()

def edit_student():
    selected = tree.focus()

    if not selected:
        messagebox.showwarning("Warning", "Select a student first")
        return

    values = tree.item(selected, "values")
    athlete_id = values[0]

    win = tk.Toplevel(root)
    win.title("Edit Student")
    win.geometry("500x330")

    form = tk.Frame(win)
    form.pack(pady=10, padx=20, fill="x")

    for i in range(2):
        form.grid_columnconfigure(i, weight=1)

    labels = ["Student ID", "Full Name", "Grade Level", "Section", "Strand", "Sports Event"]
    current_values = [values[1], values[2], values[3], values[4], values[5], values[6]]

    entries = {}

    for i, label in enumerate(labels):
        tk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=4)
        entry = tk.Entry(form)
        entry.grid(row=i, column=1, sticky="ew", pady=4)
        entry.insert(0, current_values[i])
        entries[label] = entry

    def save_edit():
        try:
            cursor.execute("""
                UPDATE student_athlete
                SET student_number = %s,
                    full_name = %s,
                    grade_level = %s,
                    section = %s,
                    strand = %s,
                    sports_events = %s
                WHERE athlete_id = %s;
            """, (
                entries["Student ID"].get(),
                entries["Full Name"].get(),
                entries["Grade Level"].get(),
                entries["Section"].get(),
                entries["Strand"].get(),
                entries["Sports Event"].get(),
                athlete_id
            ))

            conn.commit()
            load_students()
            messagebox.showinfo("Success", "Student updated!")
            win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Edit Error", str(e))

    tk.Button(win, text="Save Changes", command=save_edit, width=20).pack(pady=15)


def delete_student():
    selected = tree.focus()

    if not selected:
        messagebox.showwarning("Warning", "Select a student first")
        return

    values = tree.item(selected, "values")
    athlete_id = values[0]
    student_name = values[2]

    confirm = messagebox.askyesno(
        "Confirm Delete",
        f"Delete {student_name} permanently?\n\nThis will also delete grades."
    )

    if not confirm:
        return

    try:
        cursor.execute("DELETE FROM academic_record WHERE athlete_id = %s;", (athlete_id,))
        cursor.execute("DELETE FROM student_athlete WHERE athlete_id = %s;", (athlete_id,))

        conn.commit()
        load_students()
        messagebox.showinfo("Success", "Student deleted!")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Delete Error", str(e))


def change_student_status():
    selected = tree.focus()

    if not selected:
        messagebox.showwarning("Warning", "Select a student first")
        return

    values = tree.item(selected, "values")
    athlete_id = values[0]
    student_name = values[2]
    current_status = values[7]

    new_status = "Inactive" if current_status == "Active" else "Active"

    confirm = messagebox.askyesno(
        "Confirm Status Change",
        f"Change {student_name} status from {current_status} to {new_status}?"
    )

    if not confirm:
        return

    try:
        cursor.execute("""
            UPDATE student_athlete
            SET status = %s
            WHERE athlete_id = %s;
        """, (new_status, athlete_id))

        conn.commit()
        load_students()
        messagebox.showinfo("Success", f"Student status changed to {new_status}!")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Status Error", str(e))

def upload_excel():
    file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
    if not file_path:
        return

    try:
        raw = pd.read_excel(file_path, header=None)

        header_row = None
        for i, row in raw.iterrows():
            values = [
                str(v).strip().lower().replace(" ", "_").replace("-", "_")
                for v in row.tolist()
            ]

            if (
                ("student_id" in values or "student_id_no" in values or "student_number" in values or "lrn" in values)
                and "full_name" in values
            ):
                header_row = i
                break

        if header_row is None:
            messagebox.showerror("Upload Error", "Cannot find header row")
            return

        df = pd.read_excel(file_path, header=header_row)

        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
            .str.replace("-", "_")
        )

        level = "JHS" if "jhs" in file_path.lower() else "SHS"

        cursor.execute("""
            DELETE FROM academic_record ar
            USING student_athlete sa
            WHERE ar.athlete_id = sa.athlete_id
              AND sa.level = %s;
        """, (level,))
        conn.commit()

        inserted_students = 0
        inserted_grades = 0

        for _, row in df.iterrows():
            student_id = clean_value(
                row.get("student_id")
                or row.get("student_id_no")
                or row.get("student_number")
                or row.get("lrn")
            )

            full_name = clean_value(
                row.get("full_name")
                or row.get("name")
                or row.get("student_name")
            )

            if not student_id or not full_name:
                continue

            subject_name = clean_value(row.get("subject_name") or row.get("subject"))
            grade_level = clean_value(row.get("grade_level") or row.get("year_level") or row.get("grade"))
            section = clean_value(row.get("section") or row.get("class_section"))
            strand = clean_value(row.get("strand") or row.get("track"))
            sports_event = clean_value(row.get("sports_event") or row.get("sports_events") or row.get("sport")) or "N/A"
            academic_year = clean_value(row.get("academic_year") or row.get("academic_ye") or row.get("school_year"))
            term = clean_value(row.get("term") or row.get("semester"))

            q1_grade = clean_numeric(row.get("q1"))
            q2_grade = clean_numeric(row.get("q2"))
            q3_grade = clean_numeric(row.get("q3"))
            q4_grade = clean_numeric(row.get("q4"))

            midterm_grade = clean_numeric(row.get("midterm_grade") or row.get("midterm"))
            final_grade = clean_numeric(row.get("final_grade") or row.get("final"))
            average_grade = clean_numeric(row.get("average_grade"))

            # ===== TAMANG COMPUTATION =====
            if level == "JHS":
                # JHS = use official average_grade from Excel
                final_term_grade = average_grade

                # display only sa View Grades
                midterm_grade = q1_grade
                final_grade = q2_grade

                # fallback kung walang average_grade
                if final_term_grade is None:
                    grades = [g for g in [q1_grade, q2_grade, q3_grade, q4_grade] if g is not None]
                    if grades:
                        final_term_grade = round(sum(grades) / len(grades), 2)

            else:
                # SHS = average of midterm and final
                if midterm_grade is not None and final_grade is not None:
                    final_term_grade = round((midterm_grade + final_grade) / 2, 2)
                elif midterm_grade is not None:
                    final_term_grade = midterm_grade
                elif final_grade is not None:
                    final_term_grade = final_grade
                else:
                    final_term_grade = None

                q1_grade = None
                q2_grade = None
                q3_grade = None
                q4_grade = None

            teacher_name = clean_value(row.get("teacher_name") or row.get("teacher"))
            status = clean_value(row.get("status") or row.get("remarks"))

            if final_term_grade is None:
                continue

            cursor.execute("""
                INSERT INTO student_athlete
                (student_number, full_name, course, year_level,
                 grade_level, section, strand, sports_events, level,
                 sport_id, coach_id, status)
                VALUES (%s, %s, %s, 12, %s, %s, %s, %s, %s, 1, 1, 'Active')
                ON CONFLICT (student_number)
                DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    grade_level = EXCLUDED.grade_level,
                    section = EXCLUDED.section,
                    strand = EXCLUDED.strand,
                    sports_events = EXCLUDED.sports_events,
                    level = EXCLUDED.level
                RETURNING athlete_id;
            """, (
                student_id,
                full_name,
                level,
                grade_level,
                section,
                strand,
                sports_event,
                level
            ))

            athlete_id = cursor.fetchone()[0]
            inserted_students += 1

            if subject_name:
                cursor.execute("""
                    INSERT INTO subject (subject_code, subject_name, units)
                    VALUES (%s, %s, 3)
                    ON CONFLICT (subject_code)
                    DO UPDATE SET subject_name = EXCLUDED.subject_name, units = 3
                    RETURNING subject_id;
                """, (subject_name, subject_name))

                subject_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO academic_record
                    (athlete_id, subject_id, semester, school_year, grade, remarks,
                     academic_year, term, midterm_grade, final_grade,
                     q1_grade, q2_grade, q3_grade, q4_grade,
                     final_term_grade, teacher_name, subject_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    athlete_id,
                    subject_id,
                    term,
                    academic_year,
                    final_term_grade,
                    status,
                    academic_year,
                    term,
                    midterm_grade,
                    final_grade,
                    q1_grade,
                    q2_grade,
                    q3_grade,
                    q4_grade,
                    final_term_grade,
                    teacher_name,
                    subject_name
                ))

                inserted_grades += 1

        conn.commit()
        load_students()

        messagebox.showinfo(
            "Success",
            f"{level} Excel uploaded successfully!\nStudents processed: {inserted_students}\nGrades inserted: {inserted_grades}"
        )

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Upload Error", str(e))

def show_dashboard():
    win = tk.Toplevel(root)
    win.title("Dashboard")
    win.geometry("900x500")

    frame = tk.Frame(win)
    frame.pack(pady=20)

    try:
        # TOTAL STUDENTS
        cursor.execute("SELECT COUNT(*) FROM student_athlete")
        total_students = cursor.fetchone()[0]

        # ACTIVE
        cursor.execute("SELECT COUNT(*) FROM student_athlete WHERE status = 'Active'")
        active_students = cursor.fetchone()[0]

        # INACTIVE
        cursor.execute("SELECT COUNT(*) FROM student_athlete WHERE status = 'Inactive'")
        inactive_students = cursor.fetchone()[0]

        # SPORTS COUNT
        cursor.execute("""
            SELECT COUNT(DISTINCT sports_events)
            FROM student_athlete
            WHERE sports_events IS NOT NULL AND sports_events != ''
        """)
        total_sports = cursor.fetchone()[0]

        # AT RISK (gwa < 75)
        cursor.execute("""
            SELECT COUNT(DISTINCT athlete_id)
            FROM academic_record
            WHERE final_term_grade < 75
        """)
        at_risk = cursor.fetchone()[0]

    except Exception as e:
        messagebox.showerror("Dashboard Error", str(e))
        return

    # 🔥 CARD FUNCTION
    def create_card(parent, title, value, color):
        card = tk.Frame(parent, bg=color, width=180, height=120)
        card.grid_propagate(False)

        tk.Label(card, text=title, bg=color, fg="white",
                 font=("Arial", 10, "bold")).pack(pady=10)

        tk.Label(card, text=value, bg=color, fg="white",
                 font=("Arial", 20, "bold")).pack()

        return card

    # ROW 1
    create_card(frame, "Total Students", total_students, "#007bff").grid(row=0, column=0, padx=10, pady=10)
    create_card(frame, "Active", active_students, "#28a745").grid(row=0, column=1, padx=10)
    create_card(frame, "Inactive", inactive_students, "#6c757d").grid(row=0, column=2, padx=10)

    # ROW 2
    create_card(frame, "Sports", total_sports, "#17a2b8").grid(row=1, column=0, padx=10, pady=10)
    create_card(frame, "At Risk", at_risk, "#dc3545").grid(row=1, column=1, padx=10)

root = tk.Tk()
root.title("AADO Student-Athlete Monitoring System")
root.geometry("1450x820")
root.configure(bg="#eef2f7")

setup_database()

# ================= GLOBAL STYLE =================
style = ttk.Style()
style.theme_use("default")

style.configure(
    "Treeview",
    background="white",
    foreground="#1f2937",
    rowheight=30,
    fieldbackground="white",
    font=("Arial", 12)
)

style.configure(
    "Treeview.Heading",
    background="#1e3a8a",
    foreground="white",
    font=("Arial", 12, "bold")
)

style.map(
    "Treeview",
    background=[("selected", "#bfdbfe")],
    foreground=[("selected", "#111827")]
)

def app_button(parent, text, command, color="#2563eb"):
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        fg="black",   # <-- DITO FIX
        relief="raised",
        font=("Arial", 10, "bold"),
        cursor="hand2",
        padx=12,
        pady=7
    )
    return btn

    def enter(e):
        btn.config(bg="#1d4ed8")

    def leave(e):
        btn.config(bg=color)

    btn.bind("<Enter>", enter)
    btn.bind("<Leave>", leave)

    return btn


# ================= HEADER =================
header = tk.Frame(root, bg="#0f172a", height=105)
header.pack(fill="x")
header.pack_propagate(False)

logo_box = tk.Frame(header, bg="white", width=75, height=60)
logo_box.pack(side="left", padx=25, pady=20)
logo_box.pack_propagate(False)

tk.Label(
    logo_box,
    text="AADO",
    bg="white",
    fg="#1e3a8a",
    font=("Arial", 12, "bold")
).pack(expand=True)

title_area = tk.Frame(header, bg="#0f172a")
title_area.pack(side="left", pady=18)

tk.Label(
    title_area,
    text="AADO Student-Athlete Monitoring System",
    bg="#0f172a",
    fg="white",
    font=("Arial", 25, "bold")
).pack(anchor="w")

tk.Label(
    title_area,
    text="Athlete’s Academic Development Office • Records • Grades • Sports Monitoring",
    bg="#0f172a",
    fg="#cbd5e1",
    font=("Arial", 12)
).pack(anchor="w", pady=(4, 0))

def clear_filters():
    search_entry.delete(0, tk.END)
    sport_filter.current(0)
    level_filter.current(0)
    load_students()

# ================= SEARCH CARD =================
search_card = tk.LabelFrame(
    root,
    text=" Search & Filter ",
    bg="#eef2f7",
    fg="#111827",
    font=("Arial", 11, "bold"),
    padx=15,
    pady=14
)
search_card.pack(fill="x", padx=25, pady=(18, 10))

search_card.grid_columnconfigure(1, weight=1)

tk.Label(
    search_card,
    text="Search Student",
    bg="#eef2f7",
    fg="#374151",
    font=("Arial", 11, "bold")
).grid(row=0, column=0, sticky="w", padx=8, pady=8)

search_entry = tk.Entry(
    search_card,
    font=("Arial", 12),
    relief="solid",
    bd=1
)
search_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=8, ipady=4)

app_button(search_card, "Search", search_student).grid(row=0, column=2, padx=6, sticky="ew")
app_button(search_card, "Clear", clear_filters, "#475569").grid(row=0, column=3, padx=6, sticky="ew")


tk.Label(
    search_card,
    text="Filter by Sport",
    bg="#eef2f7",
    fg="#374151",
    font=("Arial", 11, "bold")
).grid(row=1, column=0, sticky="w", padx=8, pady=8)

cursor.execute("""
    SELECT DISTINCT sports_events
    FROM student_athlete
    WHERE sports_events IS NOT NULL
      AND sports_events != ''
    ORDER BY sports_events;
""")

sports_list = ["All Sports"] + [row[0] for row in cursor.fetchall()]

sport_filter = ttk.Combobox(
    search_card,
    values=sports_list,
    state="readonly",
    font=("Arial", 12)
)
sport_filter.current(0)
sport_filter.grid(row=1, column=1, sticky="ew", padx=8, pady=8, ipady=4)

app_button(search_card, "Apply Filter", filter_by_sport, "#16a34a").grid(row=1, column=2, padx=6, sticky="ew")

sport_filter.grid(row=1, column=1, padx=8, pady=6, sticky="ew")

# ===== ADD MO ITO SA ILALIM =====
tk.Label(
    search_card,
    text="Filter by Level",
    bg="#f8f9fa",
    font=("Arial", 11)
).grid(row=2, column=0, padx=8, pady=6, sticky="w")

level_filter = ttk.Combobox(
    search_card,
    values=["All", "SHS", "JHS"],
    state="readonly",
    font=("Arial", 12)
)
level_filter.current(0)  # dapat 0 = All
level_filter.grid(row=2, column=1, sticky="ew", padx=8, pady=8)
level_filter.bind("<<ComboboxSelected>>", lambda e: load_students())


# ================= DASHBOARD CARDS =================
dashboard_frame = tk.Frame(root, bg="#eef2f7")
dashboard_frame.pack(fill="x", padx=25, pady=10)

for i in range(4):
    dashboard_frame.grid_columnconfigure(i, weight=1)

def get_dashboard_counts():
    try:
        cursor.execute("SELECT COUNT(*) FROM student_athlete;")
        total_students = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM student_athlete
            WHERE status = 'Active';
        """)
        active_students = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM student_athlete
            WHERE status = 'Inactive';
        """)
        inactive_students = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT sports_events)
            FROM student_athlete
            WHERE sports_events IS NOT NULL AND sports_events != '';
        """)
        total_sports = cursor.fetchone()[0]

        return total_students, active_students, inactive_students, total_sports

    except Exception:
        return 0, 0, 0, 0

def dashboard_card(parent, title, value, accent, row, col):
    shadow = tk.Frame(parent, bg="#cbd5e1")
    shadow.grid(row=row, column=col, padx=10, pady=6, sticky="ew")

    card = tk.Frame(shadow, bg="white", height=105)
    card.pack(fill="both", expand=True, padx=2, pady=2)
    card.pack_propagate(False)

    tk.Label(
        card,
        text=title,
        bg="white",
        fg="#64748b",
        font=("Arial", 11, "bold")
    ).pack(pady=(16, 3))

    tk.Label(
        card,
        text=value,
        bg="white",
        fg=accent,
        font=("Arial", 26, "bold")
    ).pack()

def load_dashboard():
    for widget in dashboard_frame.winfo_children():
        widget.destroy()

    total_students, active_students, inactive_students, total_sports = get_dashboard_counts()

    dashboard_card(dashboard_frame, "Total Students", total_students, "#2563eb", 0, 0)
    dashboard_card(dashboard_frame, "Active Athletes", active_students, "#16a34a", 0, 1)
    dashboard_card(dashboard_frame, "Inactive Athletes", inactive_students, "#dc2626", 0, 2)
    dashboard_card(dashboard_frame, "Sports Events", total_sports, "#9333ea", 0, 3)

load_dashboard()

def view_failed_summary():
    win = tk.Toplevel(root)
    win.title("Failed Grades Summary")
    win.geometry("1200x600")

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True)

    # ===== PER SPORTS =====
    sports_frame = tk.Frame(notebook)
    notebook.add(sports_frame, text="Failed per Sports")

    sports_cols = ("Sports", "Failed Subjects")
    sports_table = ttk.Treeview(sports_frame, columns=sports_cols, show="headings")

    for col in sports_cols:
        sports_table.heading(col, text=col)
        sports_table.column(col, width=250, anchor="w")

    sports_table.pack(fill="both", expand=True, padx=10, pady=10)

    # ===== PER INDIVIDUAL =====
    indiv_frame = tk.Frame(notebook)
    notebook.add(indiv_frame, text="Failed per Individual")

    indiv_cols = ("Student ID", "Name", "Sports", "Subject", "Term", "Grade", "Teacher")
    indiv_table = ttk.Treeview(indiv_frame, columns=indiv_cols, show="headings")

    for col in indiv_cols:
        indiv_table.heading(col, text=col)
        indiv_table.column(col, width=150, anchor="w")

    indiv_table.pack(fill="both", expand=True, padx=10, pady=10)

    try:
        cursor.execute("""
            SELECT 
                sa.sports_events,
                COUNT(*) AS failed_count
            FROM academic_record ar
            JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
            WHERE ar.final_term_grade < 75
              AND sa.status = 'Active'
            GROUP BY sa.sports_events
            ORDER BY failed_count DESC;
        """)

        for row in cursor.fetchall():
            sports_table.insert("", tk.END, values=row)

        cursor.execute("""
            SELECT
                sa.student_number,
                sa.full_name,
                sa.sports_events,
                COALESCE(ar.subject_name, s.subject_name) AS subject_name,
                ar.term,
                ar.final_term_grade,
                ar.teacher_name
            FROM academic_record ar
            JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
            LEFT JOIN subject s ON ar.subject_id = s.subject_id
            WHERE ar.final_term_grade < 75
              AND sa.status = 'Active'
            ORDER BY sa.sports_events, sa.full_name, ar.term;
        """)

        for row in cursor.fetchall():
            indiv_table.insert("", tk.END, values=row)

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Failed Summary Error", str(e))

        def view_grade_status_summary():
             win = tk.Toplevel(root)
             win.title("Grade Status Summary")
             win.geometry("1250x600")

             notebook = ttk.Notebook(win)
             notebook.pack(fill="both", expand=True)

    # ===== PER SPORTS =====
    sports_frame = tk.Frame(notebook)
    notebook.add(sports_frame, text="Per Sports")

    sports_cols = ("Sports", "Passed", "Failed", "No Grade", "Total Subjects")
    sports_table = ttk.Treeview(sports_frame, columns=sports_cols, show="headings")

    for col in sports_cols:
        sports_table.heading(col, text=col)
        sports_table.column(col, width=180, anchor="center")

    sports_table.column("Sports", anchor="w", width=250)
    sports_table.pack(fill="both", expand=True, padx=10, pady=10)

    # ===== PER INDIVIDUAL =====
    indiv_frame = tk.Frame(notebook)
    notebook.add(indiv_frame, text="Per Individual")

    indiv_cols = ("Student ID", "Name", "Sports", "Passed", "Failed", "No Grade", "Total Subjects")
    indiv_table = ttk.Treeview(indiv_frame, columns=indiv_cols, show="headings")

    for col in indiv_cols:
        indiv_table.heading(col, text=col)
        indiv_table.column(col, width=160, anchor="center")

    indiv_table.column("Name", anchor="w", width=260)
    indiv_table.column("Sports", anchor="w", width=220)
    indiv_table.pack(fill="both", expand=True, padx=10, pady=10)

    try:
        cursor.execute("""
            SELECT
                sa.sports_events,
                SUM(CASE WHEN ar.final_term_grade >= 75 THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN ar.final_term_grade < 75 THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN ar.final_term_grade IS NULL THEN 1 ELSE 0 END) AS no_grade,
                COUNT(*) AS total_subjects
            FROM academic_record ar
            JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
            WHERE sa.status = 'Active'
            GROUP BY sa.sports_events
            ORDER BY sa.sports_events;
        """)

        for row in cursor.fetchall():
            sports_table.insert("", tk.END, values=row)

        cursor.execute("""
            SELECT
                sa.student_number,
                sa.full_name,
                sa.sports_events,
                SUM(CASE WHEN ar.final_term_grade >= 75 THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN ar.final_term_grade < 75 THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN ar.final_term_grade IS NULL THEN 1 ELSE 0 END) AS no_grade,
                COUNT(*) AS total_subjects
            FROM academic_record ar
            JOIN student_athlete sa ON ar.athlete_id = sa.athlete_id
            WHERE sa.status = 'Active'
            GROUP BY sa.student_number, sa.full_name, sa.sports_events
            ORDER BY sa.sports_events, sa.full_name;
        """)

        for row in cursor.fetchall():
            indiv_table.insert("", tk.END, values=row)

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Grade Status Summary Error", str(e))

def view_grade_history():
    win = tk.Toplevel(root)
    win.title("Grade History / Audit Trail")
    win.geometry("1300x600")

    tk.Label(
        win,
        text="Grade History / Audit Trail",
        font=("Arial", 14, "bold")
    ).pack(pady=10)

    cols = (
        "Student",
        "Subject",
        "Old Grade",
        "New Grade",
        "Old Remarks",
        "New Remarks",
        "Updated By",
        "Updated At"
    )

    table = ttk.Treeview(win, columns=cols, show="headings")
    table.pack(fill="both", expand=True, padx=10, pady=10)

    for col in cols:
        table.heading(col, text=col)
        table.column(col, width=160, anchor="w")

    try:
        cursor.execute("""
            SELECT
                student_name,
                subject_name,
                old_grade,
                new_grade,
                old_remarks,
                new_remarks,
                updated_by,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS')
            FROM grade_history
            ORDER BY updated_at DESC;
        """)

        for row in cursor.fetchall():
            table.insert("", tk.END, values=row)

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Grade History Error", str(e))

# ================= ACTIONS =================
btn_card = tk.LabelFrame(
    root,
    text=" Actions ",
    bg="#eef2f7",
    fg="#111827",
    font=("Arial", 11, "bold"),
    padx=15,
    pady=12
)
btn_card.pack(fill="x", padx=25, pady=10)

for i in range(6):
    btn_card.grid_columnconfigure(i, weight=1)

app_button(btn_card, "Add Student", add_student, "#2563eb").grid(row=0, column=0, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Add Subject / Grades", add_subject_grades, "#2563eb").grid(row=0, column=1, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Upload Excel", upload_excel, "#0f766e").grid(row=0, column=2, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Refresh", lambda: [load_students(), load_dashboard()], "#475569").grid(row=0, column=3, padx=6, pady=6, sticky="ew")
app_button(btn_card, "View Grades", view_grades, "#7c3aed").grid(row=0, column=4, padx=6, pady=6, sticky="ew")
app_button(btn_card, "View Summary / GWA", view_summary, "#7c3aed").grid(row=0, column=5, padx=6, pady=6, sticky="ew")

app_button(btn_card, "Edit Student", edit_student, "#f59e0b").grid(row=1, column=0, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Delete Student", delete_student, "#dc2626").grid(row=1, column=1, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Change Status", lambda: [change_student_status(), load_dashboard()], "#ea580c").grid(row=1, column=2, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Student Term GWA", view_student_term_gwa, "#0891b2").grid(row=1, column=3, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Sports Count", view_sports_count, "#0891b2").grid(row=1, column=4, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Failed Summary", view_failed_summary, "#dc2626")\
    .grid(row=2, column=0, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Grade Status Summary", view_grade_status_summary, "#9333ea")\
    .grid(row=2, column=1, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Logout", logout, "#334155").grid(row=1, column=5, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Generate PDF", generate_pdf_report, "#0f766e")\
    .grid(row=2, column=2, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Sport Term PDF Report", generate_sport_term_pdf_report, "#0f766e")\
    .grid(row=2, column=2, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Revision / Remedial Report", generate_revision_remedial_report, "#dc2626")\
    .grid(row=2, column=3, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Grade History", view_grade_history, "#f59e0b")\
    .grid(row=2, column=5, padx=6, pady=6, sticky="ew")
app_button(btn_card, "Add Remarks", add_intervention_remarks, "#f59e0b")\
    .grid(row=2, column=4, padx=6, pady=6, sticky="ew")


# ================= TABLE =================
table_container = tk.Frame(root, bg="#eef2f7")
table_container.pack(fill="both", expand=True, padx=25, pady=(5, 20))

table_title = tk.Frame(table_container, bg="#1e3a8a", height=42)
table_title.pack(fill="x")
table_title.pack_propagate(False)

tk.Label(
    table_title,
    text="Student-Athlete Records",
    bg="#1e3a8a",
    fg="white",
    font=("Arial", 13, "bold")
).pack(side="left", padx=15)

tree_frame = tk.Frame(table_container, bg="white")
tree_frame.pack(fill="both", expand=True)

scroll_y = tk.Scrollbar(tree_frame, orient="vertical")
scroll_x = tk.Scrollbar(tree_frame, orient="horizontal")

columns = ("ID", "Student ID", "Name", "Grade", "Section", "Strand", "Sports", "Status")

tree = ttk.Treeview(
    tree_frame,
    columns=columns,
    show="headings",
    yscrollcommand=scroll_y.set,
    xscrollcommand=scroll_x.set
)

scroll_y.config(command=tree.yview)
scroll_x.config(command=tree.xview)

scroll_y.pack(side="right", fill="y")
scroll_x.pack(side="bottom", fill="x")
tree.pack(fill="both", expand=True)

column_widths = {
    "ID": 80,
    "Student ID": 160,
    "Name": 280,
    "Grade": 140,
    "Section": 160,
    "Strand": 240,
    "Sports": 220,
    "Status": 140
}

for col in columns:
    tree.heading(col, text=col)
    tree.column(
        col,
        width=column_widths.get(col, 150),
        minwidth=100,
        anchor="w",
        stretch=True
    )

load_students()

college_root = tk.Toplevel(root)
college_root.title("AADO College Student-Athlete Monitoring System")
college_root.geometry("1200x700")
college_root.configure(bg="#eef2f7")
college_root.withdraw()

college_header = tk.Frame(college_root, bg="#4c1d95", height=100)
college_header.pack(fill="x")
college_header.pack_propagate(False)

tk.Label(
    college_header,
    text="AADO College Student-Athlete Monitoring System",
    bg="#4c1d95",
    fg="white",
    font=("Arial", 24, "bold")
).pack(anchor="w", padx=25, pady=(20, 5))

tk.Label(
    college_header,
    text="College Records • Courses • Year Level • Sports Monitoring",
    bg="#4c1d95",
    fg="#ddd6fe",
    font=("Arial", 12)
).pack(anchor="w", padx=25)

college_body = tk.Frame(college_root, bg="#eef2f7")
college_body.pack(fill="both", expand=True, padx=25, pady=25)

# ===== TITLE =====
tk.Label(
    college_body,
    text="College Student-Athlete Records",
    bg="#eef2f7",
    fg="#111827",
    font=("Arial", 18, "bold")
).pack(anchor="w", pady=(0, 10))

# ===== TABLE =====
college_table_frame = tk.Frame(college_body, bg="white")
college_table_frame.pack(fill="both", expand=True)

scroll_y = tk.Scrollbar(college_table_frame, orient="vertical")
scroll_x = tk.Scrollbar(college_table_frame, orient="horizontal")

college_columns = (
    "ID",
    "Student ID",
    "Name",
    "Course",
    "Year Level",
    "Sports",
    "Status"
)

college_tree = ttk.Treeview(
    college_table_frame,
    columns=college_columns,
    show="headings",
    yscrollcommand=scroll_y.set,
    xscrollcommand=scroll_x.set
)

scroll_y.config(command=college_tree.yview)
scroll_x.config(command=college_tree.xview)

scroll_y.pack(side="right", fill="y")
scroll_x.pack(side="bottom", fill="x")
college_tree.pack(fill="both", expand=True)

# headings
for col in college_columns:
    college_tree.heading(col, text=col)
    college_tree.column(col, width=160, anchor="w")


# ===== LOAD FUNCTION =====
def load_college_students():
    for row in college_tree.get_children():
        college_tree.delete(row)

    try:
        cursor.execute("""
            SELECT 
                athlete_id,
                student_number,
                full_name,
                course,
                year_level,
                sports_events,
                status
            FROM student_athlete
            WHERE level = 'College'
            ORDER BY full_name;
        """)

        for row in cursor.fetchall():
            college_tree.insert("", tk.END, values=row)

    except Exception as e:
        messagebox.showerror("College Load Error", str(e))


# load data
load_college_students()


# ===== LOGOUT BUTTON =====
college_btn_frame = tk.Frame(college_body, bg="#eef2f7")
college_btn_frame.pack(fill="x", pady=15)

tk.Button(
    college_btn_frame,
    text="Add College Student",
    command=add_college_student,
    width=20
).pack(side="left", padx=5)

tk.Button(
    college_btn_frame,
    text="Refresh",
    command=load_college_students,
    width=15
).pack(side="left", padx=5)

tk.Button(
    college_btn_frame,
    text="Logout",
    command=college_logout,
    width=15
).pack(side="left", padx=5)

root.withdraw()

def change_password_window(username):
    win = tk.Toplevel(login_win)
    win.title("Change Password")
    win.geometry("600x450")
    win.configure(bg="#0f0f0f")

    card = tk.Frame(win, bg="#1c1f20")
    card.place(relx=0.5, rely=0.5, anchor="center", width=430, height=350)

    tk.Label(
        card,
        text="Change Temporary Password",
        bg="#1c1f20",
        fg="white",
        font=("Arial", 18, "bold")
    ).pack(pady=(35, 20))

    def add_password_placeholder(entry, placeholder):
        entry.insert(0, placeholder)
        entry.config(fg="gray", show="")

        def on_focus_in(event):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                entry.config(fg="black", show="*")

        def on_focus_out(event):
            if entry.get() == "":
                entry.insert(0, placeholder)
                entry.config(fg="gray", show="")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    new_pass = tk.Entry(
        card,
        width=30,
        font=("Arial", 13),
        justify="center",
        bg="white",
        fg="black"
    )
    new_pass.pack(pady=8, ipady=7)
    add_password_placeholder(new_pass, "New Password")

    confirm_pass = tk.Entry(
        card,
        width=30,
        font=("Arial", 13),
        justify="center",
        bg="white",
        fg="black"
    )
    confirm_pass.pack(pady=8, ipady=7)
    add_password_placeholder(confirm_pass, "Confirm Password")

    def save_password():
        p1 = new_pass.get().strip()
        p2 = confirm_pass.get().strip()

        if p1 == "New Password":
            p1 = ""
        if p2 == "Confirm Password":
            p2 = ""

        if not p1 or not p2:
            messagebox.showwarning("Warning", "Please fill all fields")
            return

        if p1 != p2:
            messagebox.showerror("Error", "Passwords do not match")
            return

        try:
            cursor.execute("""
                UPDATE users
                SET password = %s,
                    is_temp = FALSE
                WHERE username = %s
            """, (p1, username))

            conn.commit()
            messagebox.showinfo("Success", "Password changed successfully!")

            win.destroy()
            login_win.withdraw()
            root.deiconify()
            load_students()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))

    save_text = tk.Label(
        card,
        text="SAVE NEW PASSWORD",
        bg="#1c1f20",
        fg="#4da3ff",
        font=("Arial", 13, "bold"),
        cursor="hand2"
    )
    save_text.pack(pady=25)
    save_text.bind("<Button-1>", lambda e: save_password())

    win.grab_set()

def login():
    global logged_username, logged_role, assigned_sport, assigned_section
    global child_student_number, logged_scope

    username = entry_user.get().strip()
    password = entry_pass.get().strip()

    if username == "Username":
        username = ""
    if password == "Password":
        password = ""

    if not username or not password:
        messagebox.showwarning("Login", "Please enter username and password")
        return

    try:
        cursor.execute("""
            SELECT username, role, assigned_sport, assigned_section,
                   child_student_number, is_temp, user_scope
            FROM users
            WHERE username = %s AND password = %s
        """, (username, password))

        user = cursor.fetchone()

        if user:
            logged_username = user[0]
            logged_role = user[1]
            assigned_sport = user[2]
            assigned_section = user[3]
            child_student_number = user[4]
            is_temp = user[5]
            logged_scope = user[6]

            if is_temp == True:
                messagebox.showinfo(
                    "Temporary Password",
                    "Please change your temporary password."
                )
                change_password_window(username)
                return

            login_win.withdraw()

            if logged_scope == "college":
                root.withdraw()
                college_root.deiconify()
            else:
                college_root.withdraw()
                root.deiconify()
                load_students()

        else:
            messagebox.showerror("Login Failed", "Invalid credentials")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Login Error", str(e))

def register():
    reg_win = tk.Toplevel(login_win)
    reg_win.title("Register User")
    reg_win.geometry("650x620")
    reg_win.configure(bg="#0f0f0f")

    card = tk.Frame(reg_win, bg="#1c1f20")
    card.place(relx=0.5, rely=0.5, anchor="center", width=470, height=540)

    tk.Label(
        card,
        text="REGISTER ACCOUNT",
        bg="#1c1f20",
        fg="white",
        font=("Arial", 20, "bold")
    ).pack(pady=(30, 20))

    def make_entry(placeholder, show_password=False):
        entry = tk.Entry(card, width=32, font=("Arial", 13), justify="center", bg="white")
        entry.pack(pady=7, ipady=7)
        entry.insert(0, placeholder)
        entry.config(fg="gray", show="")

        def focus_in(e):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                entry.config(fg="black")
                if show_password:
                    entry.config(show="*")

        def focus_out(e):
            if entry.get() == "":
                entry.insert(0, placeholder)
                entry.config(fg="gray", show="")

        entry.bind("<FocusIn>", focus_in)
        entry.bind("<FocusOut>", focus_out)
        return entry

    reg_name = make_entry("Name")
    reg_username = make_entry("Username")
    reg_password = make_entry("Password", show_password=True)

    tk.Label(
        card,
        text="Designation",
        bg="#1c1f20",
        fg="#cccccc",
        font=("Arial", 12)
    ).pack(pady=(10, 3))

    reg_role = tk.StringVar(value="coach")
    role_menu = tk.OptionMenu(card, reg_role, "coach", "teacher", "parent", "admin")
    role_menu.config(width=20)
    role_menu.pack(pady=5)

    reg_assignment = make_entry("Assignment")

    tk.Label(
        card,
        text="Coach: Sports | Teacher: Section\nParent: Student Number | Admin: type admin",
        bg="#1c1f20",
        fg="#aaaaaa",
        font=("Arial", 10),
        justify="center"
    ).pack(pady=12)

    def save_user():
        username = reg_username.get().strip()
        password = reg_password.get().strip()
        role = reg_role.get()
        assignment = reg_assignment.get().strip()

        if username == "Username":
            username = ""
        if password == "Password":
            password = ""
        if assignment == "Assignment":
            assignment = ""

        if not username or not password:
            messagebox.showwarning("Warning", "Please fill username and password")
            return

        assigned_sport_value = None
        assigned_section_value = None
        child_student_number_value = None

        if role == "coach":
            assigned_sport_value = assignment
        elif role == "teacher":
            assigned_section_value = assignment
        elif role == "parent":
            child_student_number_value = assignment

        try:
            cursor.execute("""
                INSERT INTO users
                (username, password, role, assigned_sport, assigned_section, child_student_number, is_temp)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
            """, (
                username,
                password,
                role,
                assigned_sport_value,
                assigned_section_value,
                child_student_number_value
            ))

            conn.commit()
            messagebox.showinfo("Success", "User registered successfully!")
            reg_win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Register Error", str(e))

    save_text = tk.Label(
        card,
        text="CREATE ACCOUNT",
        bg="#1c1f20",
        fg="#4da3ff",
        font=("Arial", 13, "bold"),
        cursor="hand2"
    )
    save_text.pack(pady=10)
    save_text.bind("<Button-1>", lambda e: save_user())

    cancel_text = tk.Label(
        card,
        text="Cancel",
        bg="#1c1f20",
        fg="#bbbbbb",
        font=("Arial", 10, "underline"),
        cursor="hand2"
    )
    cancel_text.pack()
    cancel_text.bind("<Button-1>", lambda e: reg_win.destroy())

def forgot_password():
    reset_win = tk.Toplevel(login_win)
    reset_win.title("Forgot Password")
    reset_win.geometry("600x420")
    reset_win.configure(bg="#0f0f0f")

    card = tk.Frame(reset_win, bg="#1c1f20")
    card.place(relx=0.5, rely=0.5, anchor="center", width=420, height=320)

    tk.Label(
        card,
        text="Forgot Password",
        bg="#1c1f20",
        fg="white",
        font=("Arial", 20, "bold")
    ).pack(pady=(35, 10))

    tk.Label(
        card,
        text="Enter your username",
        bg="#1c1f20",
        fg="#cccccc",
        font=("Arial", 12)
    ).pack(pady=(0, 15))

    username_entry = tk.Entry(
        card,
        width=30,
        font=("Arial", 13),
        justify="center",
        bg="white",
        fg="black"
    )
    username_entry.pack(pady=8, ipady=7)

    def reset_password():
        username = username_entry.get().strip()

        if not username:
            messagebox.showwarning("Warning", "Please enter your username")
            return

        try:
            cursor.execute("""
                SELECT username
                FROM users
                WHERE username = %s
            """, (username,))

            user = cursor.fetchone()

            if not user:
                messagebox.showerror("Not Found", "Username not found. Please contact admin.")
                return

            temp_password = str(random.randint(100000, 999999))

            cursor.execute("""
                UPDATE users
                SET password = %s,
                    is_temp = TRUE
                WHERE username = %s
            """, (temp_password, username))

            conn.commit()

            messagebox.showinfo(
                "Password Reset",
                f"Temporary password: {temp_password}\n\nPlease login using this temporary password."
            )

            reset_win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Reset Error", str(e))

    reset_text = tk.Label(
        card,
        text="RESET PASSWORD",
        bg="#1c1f20",
        fg="#4da3ff",
        font=("Arial", 13, "bold"),
        cursor="hand2"
    )
    reset_text.pack(pady=25)
    reset_text.bind("<Button-1>", lambda e: reset_password())

# ================= LOGIN WINDOW =================
login_win = tk.Toplevel(root)
login_win.title("Login")
login_win.geometry("900x600")
login_win.configure(bg="#0f0f0f")

# center window
screen_width = login_win.winfo_screenwidth()
screen_height = login_win.winfo_screenheight()
x = (screen_width - 900) // 2
y = (screen_height - 600) // 2
login_win.geometry(f"900x600+{x}+{y}")

# CARD
card = tk.Frame(login_win, bg="#1c1f20")
card.place(relx=0.5, rely=0.5, anchor="center", width=520, height=500)

# TITLE
tk.Label(
    card,
    text="Athlete’s Academic\nDevelopment Office",
    bg="#1c1f20",
    fg="white",
    font=("Arial", 20, "bold"),
    justify="center"
).pack(pady=(35, 5))

tk.Label(
    card,
    text="WELCOME!",
    bg="#1c1f20",
    fg="white",
    font=("Arial", 24, "bold")
).pack()

tk.Label(
    card,
    text="Student-Athlete Monitoring System",
    bg="#1c1f20",
    fg="#cccccc",
    font=("Arial", 12)
).pack(pady=(0, 25))

# -------- PLACEHOLDER FUNCTION --------
def add_placeholder(entry, text, is_password=False):
    entry.insert(0, text)
    entry.config(fg="gray")

    def on_focus_in(e):
        if entry.get() == text:
            entry.delete(0, tk.END)
            entry.config(fg="black")
            if is_password:
                entry.config(show="*")

    def on_focus_out(e):
        if entry.get() == "":
            entry.insert(0, text)
            entry.config(fg="gray")
            if is_password:
                entry.config(show="")

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

# USERNAME
entry_user = tk.Entry(card, width=32, font=("Arial", 13), justify="center")
entry_user.pack(pady=8, ipady=7)
add_placeholder(entry_user, "Username")

# PASSWORD
entry_pass = tk.Entry(card, width=32, font=("Arial", 13), justify="center")
entry_pass.pack(pady=8, ipady=7)
add_placeholder(entry_pass, "Password", is_password=True)

# LOGIN CLICKABLE
login_text = tk.Label(
    card,
    text="LOGIN",
    bg="#1c1f20",
    fg="#4da3ff",
    font=("Arial", 13, "bold"),
    cursor="hand2"
)
login_text.pack(pady=(20, 10))
login_text.bind("<Button-1>", lambda e: login())

# FORGOT PASSWORD
forgot_label = tk.Label(
    card,
    text="Forgot Password?",
    bg="#1c1f20",
    fg="#bbbbbb",
    font=("Arial", 10, "underline"),
    cursor="hand2"
)
forgot_label.pack(pady=(5, 0))
forgot_label.bind("<Button-1>", lambda event: forgot_password())

# optional action
# fforgot.bind("<Button-1>", lambda e: forgot_password())

# REGISTER LINK
register_label = tk.Label(
    card,
    text="No Account yet? Click here",
    bg="#1c1f20",
    fg="#f4f542",
    font=("Arial", 11, "bold"),
    cursor="hand2"
)
register_label.pack(pady=10)
register_label.bind("<Button-1>", lambda e: register())

# ENTER KEY LOGIN
login_win.bind("<Return>", lambda e: login())



root.mainloop()

st.subheader("Add Student")

with st.form("add_student_form"):
    student_id = st.text_input("Student ID")
    name = st.text_input("Full Name")
    grade = st.text_input("Grade")
    section = st.text_input("Section")
    strand = st.text_input("Strand")
    sport = st.text_input("Sport")
    status = st.selectbox("Status", ["Active", "Inactive"])

    submitted = st.form_submit_button("Save Student")

    if submitted:
        cursor.execute("""
            INSERT INTO student_athlete
            (student_number, full_name, grade_level, section, strand, sports_events, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (student_id, name, grade, section, strand, sport, status))

        conn.commit()
        st.success("Student added successfully!")
        st.rerun()

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
