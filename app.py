import os
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "smart-agriculture-secret-key"  # Used only for session signing (demo purposes)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the uploads folder exists locally.
# NOTE: In the AWS version, files will instead be uploaded directly to an S3
# bucket using boto3, so this local folder is only used for local/demo mode.
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Hardcoded Users (No Database)
# ---------------------------------------------------------------------------

USERS = {
    "admin": {
        "password": "admin123",
        "role": "Admin"
    },
    "farmer": {
        "password": "farmer123",
        "role": "Farmer"
    }
}


# ---------------------------------------------------------------------------
# Sample / Placeholder Data (used until real AWS data sources are connected)
# ---------------------------------------------------------------------------

# Sample sensor readings shown on the Dashboard page.
SENSOR_DATA = {
    "temperature": "30°C",
    "humidity": "65%",
    "soil_moisture": "42%",
    "water_level": "78%",
    "soil_ph": "6.8"
}

# Sample report filenames shown on the Reports page (before real uploads exist).
SAMPLE_REPORTS = [
    "Crop_Report.pdf",
    "January_Report.pdf",
    "Soil_Data.csv"
]


def _seed_sample_reports():
    """
    Creates a few small placeholder files in the local 'uploads' folder so
    the Reports page has something to view/download the very first time the
    app is run (before any real uploads exist).

    This is only for local/demo mode. In the AWS version, these sample
    reports would simply already exist as objects inside the S3 bucket.
    """
    for name in SAMPLE_REPORTS:
        file_path = os.path.join(UPLOAD_FOLDER, name)
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write(f"This is a sample placeholder file for {name}.\n")
                f.write("Replace with a real report once files are uploaded.\n")


_seed_sample_reports()


# Sample analytics statistics shown on the Analytics page.
# In the AWS version, these values would be read from a CSV file stored on
# an Amazon EBS volume attached to the EC2 instance.
ANALYTICS_DATA = {
    "avg_temperature": "29°C",
    "avg_humidity": "64%",
    "highest_moisture": "82%",
    "lowest_moisture": "31%"
}


# ---------------------------------------------------------------------------
# AWS Helper Functions (Placeholders for future S3 integration via boto3)
# ---------------------------------------------------------------------------
#
# These functions are intentionally left as placeholders. When this
# application is deployed on an EC2 instance with an IAM Role attached,
# boto3 will automatically use the EC2 instance's temporary security
# credentials (Access Key, Secret Key, and Session Token) provided by the
# IAM Role through the EC2 instance metadata service.
#
# This means:
#   - No AWS Access Keys are hardcoded anywhere in this application.
#   - boto3 uses the "default credential provider chain", which automatically
#     detects and uses the IAM Role credentials when running on EC2.
#   - The IAM Role attached to the EC2 instance must have a policy granting
#     the necessary S3 permissions (e.g., s3:PutObject, s3:GetObject,
#     s3:ListBucket, s3:DeleteObject) scoped to the specific S3 bucket.
#
# Example of how boto3 would be initialized (no keys required):
#
#     import boto3
#     s3_client = boto3.client("s3")  # Credentials auto-loaded from IAM Role
#
# The actual S3 bucket name is intentionally NOT hardcoded here. When ready,
# set it via an environment variable, e.g.:
#
#     S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
#
# ---------------------------------------------------------------------------

def upload_to_s3(file):
    """
    Upload a report directly to Amazon S3.
    """

    if file and file.filename:
        safe_name = secure_filename(file.filename)

        s3_client.upload_fileobj(
            file,
            S3_BUCKET_NAME,
            S3_REPORT_PREFIX + safe_name
        )

        return True

    return False


def list_reports():
    response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET_NAME,
        Prefix=S3_REPORT_PREFIX
    )

    reports = []

    if "Contents" not in response:
        return reports

    for obj in response["Contents"]:
        key = obj["Key"]

        if key == S3_REPORT_PREFIX:
            continue

        reports.append(key.replace(S3_REPORT_PREFIX, ""))

    return sorted(reports)


def download_report(filename):
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET_NAME,
                "Key": S3_REPORT_PREFIX + filename
            },
            ExpiresIn=300
        )

        return url

    except Exception:
        return None


def delete_report(filename):
    try:
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=S3_REPORT_PREFIX + filename
        )

        return True

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Login Required Decorator
# ---------------------------------------------------------------------------

def login_required(view_func):
    """Redirects to the login page if the user is not logged in."""
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "username" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped_view


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Redirect the root URL to the login page (or home if already logged in)."""
    if "username" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Simple hardcoded login using Flask sessions (no database)."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = USERS.get(username)

        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user["role"]
            flash(f"Welcome, {username}!")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password. Please try again.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clears the session and logs the user out."""
    session.clear()
    flash("You have been logged out successfully.")
    return redirect(url_for("login"))


@app.route("/home")
@login_required
def home():
    """Home page - project title, description, and AWS services used."""
    aws_services = [
        "Amazon EC2",
        "Amazon S3",
        "IAM Role",
        "Amazon EBS",
        "Custom VPC"
    ]
    return render_template("home.html", aws_services=aws_services)


@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard page - displays sample sensor readings."""
    return render_template("dashboard.html", sensor_data=SENSOR_DATA)


@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    """
    Reports page.

    GET  -> Shows the upload form and the current list of reports.
    POST -> Handles the file upload, then redirects back to this page
            (Post/Redirect/Get pattern, avoids re-submitting the form on refresh).
    """
    if request.method == "POST":
        uploaded_file = request.files.get("report_file")

        if uploaded_file and uploaded_file.filename != "":
            # This call currently saves the file locally. Once AWS is set
            # up, only the inside of upload_to_s3() needs to change to use
            # boto3 - this route does not need to change at all.
            success = upload_to_s3(uploaded_file)
            if success:
                flash(f"'{uploaded_file.filename}' uploaded successfully.")
            else:
                flash("File upload failed. Please try again.")
        else:
            flash("Please choose a file before clicking Upload.")

        return redirect(url_for("reports"))

    report_list = list_reports()
    return render_template("reports.html", reports=report_list)


@app.route("/reports/download/<filename>")
@login_required
def reports_download(filename):
    """
    Downloads a single report file.

    Any logged-in user (Admin or Farmer) is allowed to download reports.
    """
    safe_name = secure_filename(filename)

    # Confirm the file actually exists before trying to send it.
    # In the AWS version, download_report() would instead check S3 and
    # could return a pre-signed URL to redirect the user to.
    file_path = download_report(safe_name)

    if file_path is None:
        flash(f"'{safe_name}' was not found.")
        return redirect(url_for("reports"))

    return redirect(file_path)


@app.route("/reports/delete/<filename>", methods=["POST"])
@login_required
def reports_delete(filename):
    """
    Deletes a single report file. Restricted to Admin users only.
    """
    if session.get("role") != "Admin":
        flash("Only Admin users are allowed to delete reports.")
        return redirect(url_for("reports"))

    safe_name = secure_filename(filename)
    success = delete_report(safe_name)

    if success:
        flash(f"'{safe_name}' deleted successfully.")
    else:
        flash(f"'{safe_name}' could not be found or deleted.")

    return redirect(url_for("reports"))


@app.route("/analytics")
@login_required
def analytics():
    """Analytics page - displays simple statistics read from an EBS-stored CSV."""
    return render_template("analytics.html", analytics_data=ANALYTICS_DATA)


@app.route("/about")
@login_required
def about():
    """About page - explains the project and the purpose of each AWS service."""
    return render_template("about.html")


# ---------------------------------------------------------------------------
# Run the Application
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # debug=True is convenient for local development.
    # When deploying to EC2 for production, set debug=False.
    app.run(host="0.0.0.0", port=5000, debug=True)