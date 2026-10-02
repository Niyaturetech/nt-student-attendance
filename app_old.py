import streamlit as st
import pandas as pd
from datetime import date
from urllib.parse import urlencode
from io import BytesIO
import qrcode

from github_storage import github_configured, append_attendance, read_attendance, list_attendance_files

st.set_page_config(page_title="Seminar Attendance", page_icon="🎓", layout="centered")

st.markdown("""
<style>
.main-title{font-size:34px;font-weight:700;margin-bottom:0}
.company-name{font-size:18px;color:#555;margin-bottom:25px}
.success-box{padding:15px;border-radius:10px;background:#e8f5e9;border:1px solid #81c784}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🎓 Seminar Attendance</div>', unsafe_allow_html=True)
st.markdown('<div class="company-name">Niyature Technologies</div>', unsafe_allow_html=True)

if not github_configured():
    st.error("GitHub storage is not configured. Configure GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_TOKEN, ATTENDANCE_DIR and ADMIN_PASSWORD in Streamlit Cloud Secrets.")
    st.stop()

params = st.query_params
seminar = params.get("seminar", "")
seminar_date = params.get("date", "")
college = params.get("college", "")
admin_mode = params.get("admin", "")

if admin_mode == "1":
    st.header("🔐 Organizer / Admin")
    password = st.text_input("Admin Password", type="password")
    admin_password = st.secrets.get("ADMIN_PASSWORD", "")
    if not password:
        st.info("Enter the admin password.")
        st.stop()
    if password != admin_password:
        st.error("Invalid admin password.")
        st.stop()

    st.success("Admin access granted.")
    st.divider()
    st.subheader("Create Seminar Attendance Link")

    seminar_name = st.text_input("Seminar Name", placeholder="Big Data Analytics")
    college_name = st.text_input("College Name", placeholder="ABC College of Engineering")
    seminar_dt = st.date_input("Seminar Date", value=date.today())

    if st.button("Generate Attendance Link", type="primary", use_container_width=True):
        if not seminar_name.strip() or not college_name.strip():
            st.error("Please enter seminar name and college name.")
            st.stop()

        query = urlencode({
            "seminar": seminar_name.strip(),
            "date": seminar_dt.isoformat(),
            "college": college_name.strip(),
        })

        app_url = st.secrets.get("APP_URL", "").strip().rstrip("/")
        if not app_url:
            st.warning("APP_URL is not configured in Streamlit Secrets.")
            app_url = st.text_input("Streamlit App URL", placeholder="https://your-app.streamlit.app").strip().rstrip("/")

        if app_url:
            attendance_url = f"{app_url}/?{query}"
            st.success("Attendance link generated.")
            st.text_input("Student Attendance URL", value=attendance_url)

            st.markdown("### QR Code")
            qr = qrcode.make(attendance_url)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            st.image(buffer.getvalue(), caption="Scan to mark attendance", width=300)
            st.download_button("Download QR Code", data=buffer.getvalue(),
                               file_name="seminar_attendance_qr.png",
                               mime="image/png", use_container_width=True)

    st.divider()
    st.subheader("📊 Attendance Records")

    try:
        files = list_attendance_files()
        if not files:
            st.info("No attendance files found yet.")
        else:
            selected_file = st.selectbox("Select Attendance File", files)
            if selected_file:
                df = read_attendance(selected_file)
                if df is not None and not df.empty:
                    st.write(f"Total Attendance: **{len(df)}**")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button(
                        "Download CSV",
                        data=df.to_csv(index=False).encode("utf-8"),
                        file_name=selected_file.split("/")[-1],
                        mime="text/csv",
                        use_container_width=True,
                    )
                else:
                    st.warning("Attendance file is empty.")
    except Exception as e:
        st.error(f"Unable to load attendance records: {e}")
    st.stop()

if not seminar or not seminar_date or not college:
    st.warning("The organizer has not provided a valid seminar attendance link.")
    st.info("A valid seminar link must contain seminar, date and college parameters.")
    st.code("https://YOUR-APP.streamlit.app/?seminar=Big%20Data%20AI&date=2026-10-05&college=ABC%20College")
    st.stop()

st.header(seminar)
st.markdown(f"**College:** {college}\n\n**Seminar Date:** {seminar_date}")
st.divider()
st.subheader("Mark Attendance")
st.write("You can enter multiple students from the same device.")

with st.form("attendance_form"):
    number_of_students = st.number_input("Number of Students", min_value=1, max_value=20, value=1, step=1)
    entries = []

    for i in range(int(number_of_students)):
        st.markdown(f"**Student {i + 1}**")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Student Name", key=f"name_{i}", placeholder="Full Name")
        with c2:
            roll = st.text_input("Enrollment / Roll Number", key=f"roll_{i}", placeholder="Roll Number")
        entries.append({"student_name": name.strip(), "enrollment_number": roll.strip()})

    submitted = st.form_submit_button("Submit Attendance", type="primary", use_container_width=True)

if submitted:
    valid = [x for x in entries if x["student_name"] and x["enrollment_number"]]
    if not valid:
        st.error("Please enter at least one student's details.")
        st.stop()

    rolls = [x["enrollment_number"].lower() for x in valid]
    duplicates = {x for x in rolls if rolls.count(x) > 1}
    if duplicates:
        st.error("Duplicate enrollment / roll number found in this submission.")
        st.write(", ".join(sorted(duplicates)))
        st.stop()

    info = {"seminar": seminar, "date": seminar_date, "college": college}
    successful, duplicate, failed = [], [], []

    for student in valid:
        result = append_attendance(info, student["student_name"], student["enrollment_number"])
        if result["status"] == "success":
            successful.append(student)
        elif result["status"] == "duplicate":
            duplicate.append(student)
        else:
            failed.append({**student, "error": result.get("message", "Unknown error")})

    if successful:
        st.success(f"Attendance successfully recorded for {len(successful)} student(s).")
    if duplicate:
        st.warning(f"{len(duplicate)} student(s) were already marked present.")
        with st.expander("View duplicate students"):
            for x in duplicate:
                st.write(f"• {x['student_name']} ({x['enrollment_number']})")
    if failed:
        st.error(f"{len(failed)} student(s) could not be recorded.")
        with st.expander("View failed records"):
            for x in failed:
                st.write(f"• {x['student_name']} ({x['enrollment_number']})")
                st.caption(x["error"])
    if successful:
        st.balloons()
        st.markdown('<div class="success-box"><h3>✅ Attendance Submitted</h3>Thank you for attending the seminar.</div>', unsafe_allow_html=True)
