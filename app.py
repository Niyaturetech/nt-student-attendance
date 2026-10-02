```python
import streamlit as st
import pandas as pd
from datetime import date
from urllib.parse import urlencode
from io import BytesIO
import qrcode
import re

from github_storage import (
    github_configured,
    append_attendance,
    read_attendance,
    list_attendance_files
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Seminar Attendance",
    page_icon="🎓",
    layout="centered"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 34px;
    font-weight: 700;
    margin-bottom: 0;
}

.company-name {
    font-size: 18px;
    color: #555;
    margin-bottom: 25px;
}

.success-box {
    padding: 15px;
    border-radius: 10px;
    background: #e8f5e9;
    border: 1px solid #81c784;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 Seminar Attendance</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="company-name">Niyature Technologies</div>',
    unsafe_allow_html=True
)


# ============================================================
# GITHUB CONFIGURATION CHECK
# ============================================================

if not github_configured():

    st.error(
        "GitHub storage is not configured. "
        "Configure GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, "
        "GITHUB_TOKEN, ATTENDANCE_DIR and ADMIN_PASSWORD "
        "in Streamlit Cloud Secrets."
    )

    st.stop()


# ============================================================
# URL PARAMETERS
# ============================================================

params = st.query_params

seminar = params.get("seminar", "")
seminar_date = params.get("date", "")
college = params.get("college", "")
admin_mode = params.get("admin", "")


# ============================================================
# ADMIN / ORGANIZER MODE
# ============================================================

if admin_mode == "1":

    st.header("🔐 Organizer / Admin")

    password = st.text_input(
        "Admin Password",
        type="password"
    )

    admin_password = st.secrets.get(
        "ADMIN_PASSWORD",
        ""
    )

    if not password:

        st.info("Enter the admin password.")
        st.stop()

    if password != admin_password:

        st.error("Invalid admin password.")
        st.stop()

    st.success("Admin access granted.")

    st.divider()

    # ========================================================
    # CREATE SEMINAR LINK
    # ========================================================

    st.subheader(
        "Create Seminar Attendance Link"
    )

    seminar_name = st.text_input(
        "Seminar Name",
        placeholder="Big Data Analytics"
    )

    college_name = st.text_input(
        "College Name",
        placeholder="ABC College of Engineering"
    )

    seminar_dt = st.date_input(
        "Seminar Date",
        value=date.today()
    )

    if st.button(
        "Generate Attendance Link",
        type="primary",
        use_container_width=True
    ):

        if (
            not seminar_name.strip()
            or not college_name.strip()
        ):

            st.error(
                "Please enter seminar name and college name."
            )

            st.stop()

        query = urlencode({
            "seminar": seminar_name.strip(),
            "date": seminar_dt.isoformat(),
            "college": college_name.strip(),
        })

        app_url = (
            st.secrets
            .get("APP_URL", "")
            .strip()
            .rstrip("/")
        )

        if not app_url:

            st.warning(
                "APP_URL is not configured in "
                "Streamlit Secrets."
            )

            app_url = st.text_input(
                "Streamlit App URL",
                placeholder="https://your-app.streamlit.app"
            ).strip().rstrip("/")

        if app_url:

            attendance_url = (
                f"{app_url}/?{query}"
            )

            st.success(
                "Attendance link generated."
            )

            st.text_input(
                "Student Attendance URL",
                value=attendance_url
            )

            # ------------------------------------------------
            # QR CODE
            # ------------------------------------------------

            st.markdown("### QR Code")

            qr = qrcode.make(
                attendance_url
            )

            buffer = BytesIO()

            qr.save(
                buffer,
                format="PNG"
            )

            st.image(
                buffer.getvalue(),
                caption="Scan to mark attendance",
                width=300
            )

            st.download_button(
                "Download QR Code",
                data=buffer.getvalue(),
                file_name="seminar_attendance_qr.png",
                mime="image/png",
                use_container_width=True
            )

    # ========================================================
    # ATTENDANCE RECORDS
    # ========================================================

    st.divider()

    st.subheader(
        "📊 Attendance Records"
    )

    try:

        files = list_attendance_files()

        if not files:

            st.info(
                "No attendance files found yet."
            )

        else:

            selected_file = st.selectbox(
                "Select Attendance File",
                files
            )

            if selected_file:

                df = read_attendance(
                    selected_file
                )

                if (
                    df is not None
                    and not df.empty
                ):

                    st.write(
                        f"Total Attendance: "
                        f"**{len(df)}**"
                    )

                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.download_button(
                        "Download CSV",
                        data=df.to_csv(
                            index=False
                        ).encode("utf-8"),
                        file_name=(
                            selected_file
                            .split("/")[-1]
                        ),
                        mime="text/csv",
                        use_container_width=True,
                    )

                else:

                    st.warning(
                        "Attendance file is empty."
                    )

    except Exception as e:

        st.error(
            f"Unable to load attendance records: {e}"
        )

    st.stop()


# ============================================================
# VALIDATE SEMINAR LINK
# ============================================================

if (
    not seminar
    or not seminar_date
    or not college
):

    st.warning(
        "The organizer has not provided a valid "
        "seminar attendance link."
    )

    st.info(
        "A valid seminar link must contain "
        "seminar, date and college parameters."
    )

    st.code(
        "https://YOUR-APP.streamlit.app/"
        "?seminar=Big%20Data%20AI"
        "&date=2026-10-05"
        "&college=ABC%20College"
    )

    st.stop()


# ============================================================
# SEMINAR INFORMATION
# ============================================================

st.header(seminar)

st.markdown(
    f"**College:** {college}\n\n"
    f"**Seminar Date:** {seminar_date}"
)

st.divider()

st.subheader(
    "📝 Student Attendance"
)

st.write(
    "Please enter your details below to mark your attendance."
)


# ============================================================
# ATTENDANCE FORM
# ============================================================

with st.form("attendance_form"):

    # --------------------------------------------------------
    # STUDENT NAME
    # --------------------------------------------------------

    student_name = st.text_input(
        "Student Name *",
        placeholder="Enter your full name"
    )

    # --------------------------------------------------------
    # MOBILE NUMBER
    # --------------------------------------------------------

    mobile_number = st.text_input(
        "Mobile Number *",
        placeholder="10-digit mobile number"
    )

    # --------------------------------------------------------
    # EMAIL ADDRESS
    # --------------------------------------------------------

    email_address = st.text_input(
        "Email Address *",
        placeholder="student@example.com"
    )

    # --------------------------------------------------------
    # CURRENT YEAR
    # --------------------------------------------------------

    current_year = st.selectbox(
        "Current Year *",
        [
            "1st Year",
            "2nd Year",
            "3rd Year",
            "4th Year",
            "5th Year",
            "Other"
        ]
    )

    # --------------------------------------------------------
    # SEMESTER
    # --------------------------------------------------------

    semester = st.selectbox(
        "Semester *",
        [
            "Semester 1",
            "Semester 2",
            "Semester 3",
            "Semester 4",
            "Semester 5",
            "Semester 6",
            "Semester 7",
            "Semester 8",
            "Other"
        ]
    )

    # --------------------------------------------------------
    # BRANCH
    # --------------------------------------------------------

    branch = st.text_input(
        "Branch / Department *",
        placeholder="Computer Science & Engineering"
    )

    # --------------------------------------------------------
    # SUBMIT
    # --------------------------------------------------------

    submitted = st.form_submit_button(
        "Submit Attendance",
        type="primary",
        use_container_width=True
    )


# ============================================================
# PROCESS ATTENDANCE
# ============================================================

if submitted:

    # --------------------------------------------------------
    # REQUIRED FIELD VALIDATION
    # --------------------------------------------------------

    if not student_name.strip():

        st.error(
            "Please enter your name."
        )

        st.stop()

    if not mobile_number.strip():

        st.error(
            "Please enter your mobile number."
        )

        st.stop()

    if not email_address.strip():

        st.error(
            "Please enter your email address."
        )

        st.stop()

    if not branch.strip():

        st.error(
            "Please enter your branch / department."
        )

        st.stop()

    # --------------------------------------------------------
    # MOBILE VALIDATION
    # --------------------------------------------------------

    clean_mobile = re.sub(
        r"\D",
        "",
        mobile_number
    )

    if not re.fullmatch(
        r"[6-9]\d{9}",
        clean_mobile
    ):

        st.error(
            "Please enter a valid 10-digit Indian "
            "mobile number."
        )

        st.stop()

    # --------------------------------------------------------
    # EMAIL VALIDATION
    # --------------------------------------------------------

    email_pattern = (
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    if not re.match(
        email_pattern,
        email_address.strip()
    ):

        st.error(
            "Please enter a valid email address."
        )

        st.stop()

    # --------------------------------------------------------
    # SEMINAR INFORMATION
    # --------------------------------------------------------

    info = {
        "seminar": seminar,
        "date": seminar_date,
        "college": college
    }

    # --------------------------------------------------------
    # SAVE ATTENDANCE
    # --------------------------------------------------------

    result = append_attendance(
        info,
        student_name.strip(),
        clean_mobile,
        email_address.strip(),
        current_year,
        semester,
        branch.strip()
    )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    if result["status"] == "success":

        st.success(
            "Attendance successfully recorded."
        )

        st.balloons()

        st.markdown(
            """
            <div class="success-box">
                <h3>✅ Attendance Submitted</h3>
                Thank you for attending the seminar.
            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # DUPLICATE
    # --------------------------------------------------------

    elif result["status"] == "duplicate":

        st.warning(
            "Your attendance has already been recorded "
            "for this seminar."
        )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    else:

        st.error(
            "Your attendance could not be recorded."
        )

        st.caption(
            result.get(
                "message",
                "Unknown error"
            )
        )
```
