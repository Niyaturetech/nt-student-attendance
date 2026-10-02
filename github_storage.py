```python
import base64
import io
import re
import time

from datetime import datetime

import pandas as pd
import requests
import streamlit as st


GITHUB_API = "https://api.github.com"


# ============================================================
# GITHUB CONFIGURATION
# ============================================================

def github_configured():

    required = [
        "GITHUB_OWNER",
        "GITHUB_REPO",
        "GITHUB_BRANCH",
        "GITHUB_TOKEN"
    ]

    return all(
        bool(st.secrets.get(key, ""))
        for key in required
    )


def get_config():

    return {
        "owner": st.secrets["GITHUB_OWNER"],
        "repo": st.secrets["GITHUB_REPO"],
        "branch": st.secrets.get(
            "GITHUB_BRANCH",
            "main"
        ),
        "token": st.secrets["GITHUB_TOKEN"],
        "attendance_dir": st.secrets.get(
            "ATTENDANCE_DIR",
            "attendance"
        ),
    }


# ============================================================
# GITHUB HEADERS
# ============================================================

def get_headers():

    return {
        "Authorization": (
            f"Bearer {get_config()['token']}"
        ),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ============================================================
# FILE NAME SANITIZATION
# ============================================================

def sanitize_filename(value):

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        str(value).strip()
    )

    return re.sub(
        r"_+",
        "_",
        value
    ).strip("_")


# ============================================================
# ATTENDANCE FILE PATH
# ============================================================

def get_attendance_file_path(
    seminar_date,
    college
):

    return (
        f"{get_config()['attendance_dir'].strip('/')}/"
        f"{seminar_date}_"
        f"{sanitize_filename(college)}.csv"
    )


# ============================================================
# GITHUB FILE URL
# ============================================================

def github_file_url(path):

    config = get_config()

    return (
        f"{GITHUB_API}/repos/"
        f"{config['owner']}/"
        f"{config['repo']}/contents/"
        f"{path}?ref={config['branch']}"
    )


# ============================================================
# READ CSV FROM GITHUB
# ============================================================

def read_csv_from_github(path):

    response = requests.get(
        github_file_url(path),
        headers=get_headers(),
        timeout=20
    )

    if response.status_code == 404:

        return pd.DataFrame(), None

    response.raise_for_status()

    data = response.json()

    content = data.get(
        "content",
        ""
    ).replace("\n", "")

    if not content:

        return (
            pd.DataFrame(),
            data.get("sha")
        )

    decoded = base64.b64decode(
        content
    ).decode("utf-8")

    if not decoded.strip():

        return (
            pd.DataFrame(),
            data.get("sha")
        )

    return (
        pd.read_csv(
            io.StringIO(decoded),
            dtype=str
        ).fillna(""),
        data.get("sha")
    )


# ============================================================
# WRITE CSV TO GITHUB
# ============================================================

def write_csv_to_github(
    path,
    df,
    sha=None
):

    config = get_config()

    encoded = base64.b64encode(
        df.to_csv(
            index=False
        ).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": (
            "Update seminar attendance: "
            f"{path.split('/')[-1]}"
        ),
        "content": encoded,
        "branch": config["branch"],
    }

    if sha:

        payload["sha"] = sha

    url = (
        f"{GITHUB_API}/repos/"
        f"{config['owner']}/"
        f"{config['repo']}/contents/"
        f"{path}"
    )

    return requests.put(
        url,
        headers=get_headers(),
        json=payload,
        timeout=20
    )


# ============================================================
# APPEND ATTENDANCE
# ============================================================

def append_attendance(
    seminar_info,
    student_name,
    mobile_number,
    email_address,
    current_year,
    semester,
    branch
):

    path = get_attendance_file_path(
        seminar_info["date"],
        seminar_info["college"]
    )

    for attempt in range(4):

        try:

            df, sha = read_csv_from_github(
                path
            )

            # ------------------------------------------------
            # EXPECTED CSV COLUMNS
            # ------------------------------------------------

            columns = [
                "timestamp",
                "seminar",
                "seminar_date",
                "college",
                "student_name",
                "mobile_number",
                "email_address",
                "current_year",
                "semester",
                "branch",
                "status"
            ]

            # ------------------------------------------------
            # CREATE NEW DATAFRAME
            # ------------------------------------------------

            if df.empty:

                df = pd.DataFrame(
                    columns=columns
                )

            # ------------------------------------------------
            # BACKWARD COMPATIBILITY
            # ------------------------------------------------

            # If an older CSV exists, automatically
            # add missing columns.

            for column in columns:

                if column not in df.columns:

                    df[column] = ""

            # Remove old Enrollment / Roll Number
            # column from the active structure.

            if "enrollment_number" in df.columns:

                df = df.drop(
                    columns=["enrollment_number"]
                )

            # Ensure correct column order.

            df = df[columns]

            # ------------------------------------------------
            # NORMALIZE CURRENT VALUES
            # ------------------------------------------------

            current_mobile = (
                str(mobile_number)
                .strip()
                .lower()
            )

            current_email = (
                str(email_address)
                .strip()
                .lower()
            )

            current_date = (
                str(seminar_info["date"])
                .strip()
            )

            current_college = (
                str(seminar_info["college"])
                .strip()
                .lower()
            )

            # ------------------------------------------------
            # DUPLICATE CHECK
            # ------------------------------------------------
            #
            # Duplicate is identified using:
            #
            # Mobile Number
            # +
            # Email Address
            # +
            # Seminar Date
            # +
            # College
            #
            # The same student can therefore attend
            # another seminar on another date.
            # ------------------------------------------------

            if not df.empty:

                existing_mobile = (
                    df["mobile_number"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                )

                existing_email = (
                    df["email_address"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                )

                existing_date = (
                    df["seminar_date"]
                    .astype(str)
                    .str.strip()
                )

                existing_college = (
                    df["college"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                )

                duplicate_mask = (
                    (existing_mobile == current_mobile)
                    &
                    (existing_email == current_email)
                    &
                    (existing_date == current_date)
                    &
                    (existing_college == current_college)
                )

                if duplicate_mask.any():

                    return {
                        "status": "duplicate"
                    }

            # ------------------------------------------------
            # CREATE ATTENDANCE RECORD
            # ------------------------------------------------

            record = {

                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                "seminar": seminar_info[
                    "seminar"
                ],

                "seminar_date": seminar_info[
                    "date"
                ],

                "college": seminar_info[
                    "college"
                ],

                "student_name": student_name,

                "mobile_number": mobile_number,

                "email_address": email_address,

                "current_year": current_year,

                "semester": semester,

                "branch": branch,

                "status": "Present"
            }

            # ------------------------------------------------
            # APPEND RECORD
            # ------------------------------------------------

            new_df = pd.concat(
                [
                    df,
                    pd.DataFrame([record])
                ],
                ignore_index=True
            )

            # ------------------------------------------------
            # WRITE TO GITHUB
            # ------------------------------------------------

            response = write_csv_to_github(
                path,
                new_df,
                sha
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code in (
                200,
                201
            ):

                return {
                    "status": "success"
                }

            # ------------------------------------------------
            # CONCURRENT UPDATE
            # ------------------------------------------------

            if response.status_code == 409:

                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

            # ------------------------------------------------
            # OTHER GITHUB ERROR
            # ------------------------------------------------

            return {
                "status": "error",
                "message": (
                    f"GitHub returned HTTP "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                )
            }

        except Exception as error:

            if attempt < 3:

                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

            return {
                "status": "error",
                "message": str(error)
            }

    # ========================================================
    # ALL RETRIES FAILED
    # ========================================================

    return {
        "status": "error",
        "message": (
            "The attendance file was updated by "
            "another submission. Please try again."
        )
    }


# ============================================================
# LIST ATTENDANCE FILES
# ============================================================

def list_attendance_files():

    config = get_config()

    path = (
        config["attendance_dir"]
        .strip("/")
    )

    url = (
        f"{GITHUB_API}/repos/"
        f"{config['owner']}/"
        f"{config['repo']}/contents/"
        f"{path}?ref={config['branch']}"
    )

    response = requests.get(
        url,
        headers=get_headers(),
        timeout=20
    )

    if response.status_code == 404:

        return []

    response.raise_for_status()

    items = response.json()

    return sorted(
        [
            item["path"]
            for item in items
            if (
                item.get("type") == "file"
                and
                item.get(
                    "name",
                    ""
                ).lower().endswith(".csv")
            )
        ],
        reverse=True
    )


# ============================================================
# READ ATTENDANCE
# ============================================================

def read_attendance(path):

    df, _ = read_csv_from_github(path)

    return df
```
