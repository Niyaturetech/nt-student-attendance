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
# CONFIGURATION
# ============================================================

def github_configured():

    required = [
        "GITHUB_OWNER",
        "GITHUB_REPO",
        "GITHUB_BRANCH",
        "GITHUB_TOKEN"
    ]

    return all(
        bool(st.secrets.get(k, ""))
        for k in required
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

    c = get_config()

    return (
        f"{GITHUB_API}/repos/"
        f"{c['owner']}/"
        f"{c['repo']}/contents/"
        f"{path}?ref={c['branch']}"
    )


# ============================================================
# READ CSV FROM GITHUB
# ============================================================

def read_csv_from_github(path):

    r = requests.get(
        github_file_url(path),
        headers=get_headers(),
        timeout=20
    )

    if r.status_code == 404:

        return pd.DataFrame(), None

    r.raise_for_status()

    data = r.json()

    content = data.get(
        "content",
        ""
    ).replace("\n", "")

    if not content:

        return pd.DataFrame(), data.get("sha")

    decoded = base64.b64decode(
        content
    ).decode("utf-8")

    if not decoded.strip():

        return pd.DataFrame(), data.get("sha")

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

    c = get_config()

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
        "branch": c["branch"],
    }

    if sha:

        payload["sha"] = sha

    url = (
        f"{GITHUB_API}/repos/"
        f"{c['owner']}/"
        f"{c['repo']}/contents/"
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
    enrollment_number,
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

            df, sha = read_csv_from_github(path)

            # ------------------------------------------------
            # CSV COLUMNS
            # ------------------------------------------------

            columns = [
                "timestamp",
                "seminar",
                "seminar_date",
                "college",
                "student_name",
                "enrollment_number",
                "mobile_number",
                "email_address",
                "current_year",
                "semester",
                "branch",
                "status"
            ]

            if df.empty:

                df = pd.DataFrame(
                    columns=columns
                )

            # ------------------------------------------------
            # BACKWARD COMPATIBILITY
            # ------------------------------------------------

            # If an older attendance CSV exists,
            # add the new columns automatically.

            for column in columns:

                if column not in df.columns:

                    df[column] = ""

            # Keep only the expected columns/order

            df = df[columns]

            # ------------------------------------------------
            # DUPLICATE CHECK
            # ------------------------------------------------

            existing = (
                df["enrollment_number"]
                .astype(str)
                .str.strip()
                .str.lower()
                .tolist()
            )

            current = (
                str(enrollment_number)
                .strip()
                .lower()
            )

            if current in existing:

                return {
                    "status": "duplicate"
                }

            # ------------------------------------------------
            # NEW ATTENDANCE RECORD
            # ------------------------------------------------

            record = {

                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                "seminar": seminar_info["seminar"],

                "seminar_date": seminar_info["date"],

                "college": seminar_info["college"],

                "student_name": student_name,

                "enrollment_number": enrollment_number,

                "mobile_number": mobile_number,

                "email_address": email_address,

                "current_year": current_year,

                "semester": semester,

                "branch": branch,

                "status": "Present",
            }

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

            # Successful GitHub update

            if response.status_code in (
                200,
                201
            ):

                return {
                    "status": "success"
                }

            # Concurrent update

            if response.status_code == 409:

                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

            return {
                "status": "error",
                "message": (
                    f"GitHub returned HTTP "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                )
            }

        except Exception as e:

            if attempt < 3:

                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

            return {
                "status": "error",
                "message": str(e)
            }

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

    c = get_config()

    path = c["attendance_dir"].strip("/")

    url = (
        f"{GITHUB_API}/repos/"
        f"{c['owner']}/"
        f"{c['repo']}/contents/"
        f"{path}?ref={c['branch']}"
    )

    r = requests.get(
        url,
        headers=get_headers(),
        timeout=20
    )

    if r.status_code == 404:

        return []

    r.raise_for_status()

    items = r.json()

    return sorted(
        [
            x["path"]
            for x in items
            if (
                x.get("type") == "file"
                and
                x.get(
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
