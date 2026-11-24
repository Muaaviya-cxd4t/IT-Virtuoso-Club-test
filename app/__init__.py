import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import razorpay
from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from supabase import create_client

from .confirmation_pdf import generate_confirmation_pdf


# ============================================================
# PATHS / ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Always load the .env belonging to this project.
load_dotenv(BASE_DIR / ".env")


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY",
    "change-me",
)


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")

# Support all common Supabase key names.
SUPABASE_KEY = (
    os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
)

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
    )
else:
    supabase = None


# ============================================================
# RAZORPAY
# ============================================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET,
        )
    )
else:
    razorpay_client = None


# ============================================================
# VALIDATION
# ============================================================

USN_RE = re.compile(r"^1GA\d{2}[A-Z]{2}\d{3}$")
PHONE_RE = re.compile(r"^\d{10}$")


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(name):
    """
    Load a JSON file from the project root.
    """
    with open(
        BASE_DIR / name,
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_events():
    return load_json("events.json")


def get_active_event():
    events = get_events()

    return next(
        (
            event
            for event in events
            if event.get("status") == "open"
        ),
        events[0] if events else None,
    )


def find_event(name):
    return next(
        (
            event
            for event in get_events()
            if event.get("event_name") == name
        ),
        None,
    )


# ============================================================
# EVENT STATUS
# ============================================================

def registration_is_open(event):
    return event.get("status") == "open"


# ============================================================
# MEMBER VALIDATION
# ============================================================

def validate_members(raw, event):

    if not isinstance(raw, list):
        raise ValueError(
            "Members must be an array."
        )

    minimum = int(event["min_members"])
    maximum = int(event["max_members"])

    if not minimum <= len(raw) <= maximum:
        raise ValueError(
            f"Team must have between "
            f"{minimum} and {maximum} members."
        )

    seen = set()
    cleaned = []

    for member in raw:

        if not isinstance(member, dict):
            raise ValueError(
                "Invalid member data."
            )

        name = str(
            member.get("name", "")
        ).strip()

        usn = str(
            member.get("usn", "")
        ).strip().upper()

        phone = re.sub(
            r"\D",
            "",
            str(member.get("phone", "")),
        )

        # Name
        if not name or len(name) > 100:
            raise ValueError(
                "Every member must have a valid name."
            )

        # USN
        if not USN_RE.fullmatch(usn):
            raise ValueError(
                f"Invalid USN: "
                f"{usn or 'blank'}. "
                f"Use the format 1GAXXXXXXX."
            )

        # Phone
        if not PHONE_RE.fullmatch(phone):
            raise ValueError(
                f"Phone number for {usn} "
                f"must contain exactly 10 digits."
            )

        # Duplicate inside current registration
        if usn in seen:
            raise ValueError(
                f"Duplicate USN detected: {usn}"
            )

        seen.add(usn)

        cleaned.append(
            {
                "name": name,
                "usn": usn,
                "phone": phone,
            }
        )

    return cleaned


# ============================================================
# REGISTRATION FEE
# ============================================================

def calculate_registration_fee(event, members):
    pricing_type = event.get("pricing_type", "per_team")
    if pricing_type == "per_member":
        return len(members) * int(event["amount_per_member"])
    return int(event["amount_per_team"])


# ============================================================
# HOME
# ============================================================

@app.get("/")
def index():

    return render_template(
        "index.html",
        events=get_events(),
        active_event=get_active_event(),
        members=load_json("members.json"),
    )


# ============================================================
# REGISTRATION
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"],
)
def register():

    # --------------------------------------------------------
    # Determine event
    # --------------------------------------------------------

    if request.method == "GET":
        event_name = request.args.get("event")
    else:
        event_name = request.form.get(
            "event_name"
        )

    event = (
        find_event(event_name)
        if event_name
        else get_active_event()
    )

    if not event:
        return (
            "Event not found",
            404,
        )

    # --------------------------------------------------------
    # Registration closed
    # --------------------------------------------------------

    if not registration_is_open(event):
        return (
            render_template(
                "closed.html",
                event=event,
            ),
            403,
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "register.html",
            event=event,
        )

    # --------------------------------------------------------
    # Supabase check
    # --------------------------------------------------------

    if not supabase:

        return jsonify(
            ok=False,
            error=(
                "Supabase is not configured. "
                "Check your .env file."
            ),
        ), 500

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    try:

        # ====================================================
        # TEAM NAME
        # ====================================================

        team_name = str(
            request.form.get(
                "team_name",
                "",
            )
        ).strip()

        if not team_name:
            raise ValueError(
                "Enter a team name."
            )

        if len(team_name) > 100:
            raise ValueError(
                "Team name must be 100 characters "
                "or fewer."
            )

        # ====================================================
        # MEMBERS
        # ====================================================

        members_json = request.form.get(
            "members_json",
            "",
        )

        if not members_json:
            raise ValueError(
                "Please add your team members."
            )

        try:
            raw_members = json.loads(
                members_json
            )
        except json.JSONDecodeError:
            raise ValueError(
                "Invalid member data. "
                "Please refresh the page and try again."
            )

        members = validate_members(
            raw_members,
            event,
        )

        # ====================================================
        # DUPLICATE TEAM NAME CHECK
        #
        # IMPORTANT:
        # We intentionally DO NOT use Supabase .ilike()
        # here because that was producing:
        #
        # team_name=ilike.none
        #
        # Instead, fetch team names for this event and
        # compare them safely in Python.
        # ====================================================

        existing_teams = (
            supabase
            .table("event_teams")
            .select("id, team_name")
            .eq(
                "event_name",
                event["event_name"],
            )
            .execute()
        )

        existing_team_names = (
            existing_teams.data
            or []
        )

        requested_team_key = (
            team_name.strip().casefold()
        )

        for existing_team in existing_team_names:

            existing_name = str(
                existing_team.get(
                    "team_name",
                    "",
                )
            ).strip().casefold()

            if (
                existing_name
                and existing_name
                == requested_team_key
            ):
                raise ValueError(
                    f'Team name "{team_name}" '
                    f"is already registered "
                    f"for this event."
                )

        # ====================================================
        # DUPLICATE USN CHECK
        # ====================================================

        usns = [
            member["usn"]
            for member in members
        ]

        existing_members = (
            supabase
            .table("event_members")
            .select("usn")
            .eq(
                "event_name",
                event["event_name"],
            )
            .in_(
                "usn",
                usns,
            )
            .execute()
        )

        if existing_members.data:

            duplicate_usn = (
                existing_members
                .data[0]
                .get("usn")
            )

            raise ValueError(
                f"USN {duplicate_usn} "
                f"is already registered "
                f"for this event."
            )

        # ====================================================
        # DO NOT INSERT INTO SUPABASE YET
        # ====================================================
        # The registration is kept only in the Flask session until
        # Razorpay payment is successfully verified. This prevents
        # abandoned/unpaid registrations from occupying the database.
        #
        # The duplicate checks above are only an early user-friendly
        # check. USNs are checked AGAIN immediately before insertion
        # after successful payment.
        # ====================================================

        registration_fee = calculate_registration_fee(event, members)

        session["pending_registration"] = {
            "event_name": event["event_name"],
            "team_name": team_name,
            "amount": registration_fee,
            "members": members,
        }
        session.pop("confirmed_team_id", None)
        session.modified = True

        return jsonify(
            ok=True,
            redirect_url=url_for("payment_page"),
        )

    # ========================================================
    # ERROR
    # ========================================================

    except ValueError as exc:

        return jsonify(
            ok=False,
            error=str(exc),
        ), 400

    except Exception as exc:

        message = str(exc)

        # Database duplicate team-name protection
        if (
            "event_teams_event_team_name_unique"
            in message
            or (
                "duplicate key value"
                in message
                and "team_name"
                in message
            )
        ):

            message = (
                f'Team name "{team_name}" '
                f"is already registered "
                f"for this event."
            )

        # Database duplicate USN protection
        elif (
            "event_members_event_usn_unique"
            in message
        ):

            message = (
                "One of these USNs is already "
                "registered for this event."
            )

        return jsonify(
            ok=False,
            error=message,
        ), 400


# ============================================================
# PAYMENT PAGE
# ============================================================

@app.get("/payment")
def payment_page():

    pending = session.get("pending_registration")

    if not pending:
        return (
            "No pending registration found. Please start registration again.",
            404,
        )

    event = find_event(pending.get("event_name"))

    if not event or not registration_is_open(event):
        session.pop("pending_registration", None)
        session.modified = True
        return (
            render_template("closed.html", event=event),
            403,
        ) if event else ("Event not found.", 404)

    # `id` is intentionally None. There is no database team yet.
    # payment.html may still send team_id, but the server ignores it.
    team = {
        "id": None,
        "event_name": pending["event_name"],
        "team_name": pending["team_name"],
        "amount": pending["amount"],
    }

    return render_template(
        "payment.html",
        team=team,
        razorpay_key=(
            RAZORPAY_KEY_ID
            or ""
        ),
    )


# ============================================================
# CREATE RAZORPAY ORDER
# ============================================================

@app.post("/create_order")
def create_order():

    if not supabase or not razorpay_client:
        return jsonify(
            ok=False,
            error=(
                "Payment service is not configured."
            ),
        ), 500

    pending = session.get("pending_registration")

    if not pending:
        return jsonify(
            ok=False,
            error=(
                "No pending registration found. "
                "Please start registration again."
            ),
        ), 400

    event = find_event(pending.get("event_name"))

    if not event or not registration_is_open(event):
        return jsonify(
            ok=False,
            error="Registration for this event is closed."
        ), 400

    amount = int(pending["amount"]) * 100

    # Use a Razorpay order as the payment-side identifier.
    # Nothing is written to Supabase before payment succeeds.
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "receipt": f"ITV-{uuid.uuid4().hex[:24]}",
        "notes": {
            "event_name": pending["event_name"],
        },
    })

    session["razorpay_order_id"] = order["id"]
    session.modified = True

    return jsonify(
        ok=True,
        order_id=order["id"],
        amount=amount,
        currency="INR",
        key_id=RAZORPAY_KEY_ID,
    )


# ============================================================
# VERIFY PAYMENT
# ============================================================

@app.post("/verify_payment")
def verify_payment():

    if not supabase or not razorpay_client:
        return jsonify(
            ok=False,
            error=(
                "Payment service is not configured."
            ),
        ), 500

    pending = session.get("pending_registration")

    if not pending:
        return jsonify(
            ok=False,
            error=(
                "Pending registration was not found. "
                "Please contact the club if payment was deducted."
            ),
        ), 400

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    required = [
        "razorpay_order_id",
        "razorpay_payment_id",
        "razorpay_signature",
    ]

    if any(
        not data.get(key)
        for key in required
    ):
        return jsonify(
            ok=False,
            error=(
                "Incomplete payment verification payload."
            ),
        ), 400

    # The order ID must be the order created for this session.
    if (
        session.get("razorpay_order_id")
        != data["razorpay_order_id"]
    ):
        return jsonify(
            ok=False,
            error="Order mismatch.",
        ), 400

    # ========================================================
    # VERIFY RAZORPAY PAYMENT
    # ========================================================

    try:

        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id":
                    data["razorpay_order_id"],
                "razorpay_payment_id":
                    data["razorpay_payment_id"],
                "razorpay_signature":
                    data["razorpay_signature"],
            }
        )

        payment = (
            razorpay_client
            .payment
            .fetch(
                data["razorpay_payment_id"]
            )
        )

        if (
            payment.get("order_id")
            != data["razorpay_order_id"]
        ):
            return jsonify(
                ok=False,
                error=(
                    "Payment does not belong "
                    "to this order."
                ),
            ), 400

        if payment.get("currency") != "INR":
            return jsonify(
                ok=False,
                error="Unexpected payment currency.",
            ), 400

        if payment.get("status") != "captured":
            return jsonify(
                ok=False,
                error=(
                    "Payment has not been "
                    "captured yet."
                ),
            ), 400

    except Exception:
        return jsonify(
            ok=False,
            error="Payment verification failed.",
        ), 400

    # ========================================================
    # RE-CHECK REGISTRATION DATA AFTER PAYMENT
    # ========================================================

    event = find_event(pending["event_name"])

    if not event or not registration_is_open(event):
        return jsonify(
            ok=False,
            error=(
                "Registration for this event is closed. "
                "Please contact the club regarding the payment."
            ),
        ), 400

    members = validate_members(
        pending["members"],
        event,
    )

    registration_fee = calculate_registration_fee(event, members)
    expected_amount = registration_fee * 100

    if int(payment.get("amount", 0)) != expected_amount:
        return jsonify(
            ok=False,
            error=(
                "Payment amount does not match "
                "the current registration fee."
            ),
        ), 400

    usns = [
        member["usn"]
        for member in members
    ]

    # IMPORTANT: this is the final duplicate check.
    # Another user could have registered one of these USNs
    # while this user was sitting on the Razorpay screen.
    existing_members = (
        supabase
        .table("event_members")
        .select("usn")
        .eq(
            "event_name",
            event["event_name"],
        )
        .in_("usn", usns)
        .execute()
    )

    if existing_members.data:
        duplicate_usn = (
            existing_members
            .data[0]
            .get("usn")
        )

        return jsonify(
            ok=False,
            error=(
                f"USN {duplicate_usn} "
                "was registered while you were "
                "completing payment. Please contact "
                "the club regarding this payment."
            ),
        ), 400

    # Final team-name check as well.
    existing_teams = (
        supabase
        .table("event_teams")
        .select("team_name")
        .eq(
            "event_name",
            event["event_name"],
        )
        .execute()
    )

    requested_team_key = (
        pending["team_name"]
        .strip()
        .casefold()
    )

    for existing_team in (
        existing_teams.data or []
    ):
        existing_name = str(
            existing_team.get(
                "team_name",
                "",
            )
        ).strip().casefold()

        if (
            existing_name
            and existing_name == requested_team_key
        ):
            return jsonify(
                ok=False,
                error=(
                    f'Team name "{pending["team_name"]}" '
                    "was registered while you were "
                    "completing payment. Please contact "
                    "the club regarding this payment."
                ),
            ), 400

    # ========================================================
    # ONLY NOW WRITE TO SUPABASE
    # ========================================================

    team_id = str(uuid.uuid4())

    try:
        supabase.rpc(
            "register_event_team",
            {
                "p_team_id": team_id,
                "p_event_name": event[
                    "event_name"
                ],
                "p_team_name": pending[
                    "team_name"
                ],
                "p_amount": registration_fee,
                "p_members": members,
            },
        ).execute()

        # The RPC creates the team with is_paid=False in
        # the current schema. Immediately mark it paid after
        # the successful Razorpay verification.
        supabase.table("event_teams").update({
            "is_paid": True,
            "razorpay_order_id": data[
                "razorpay_order_id"
            ],
            "razorpay_payment_id": data[
                "razorpay_payment_id"
            ],
        }).eq(
            "id",
            team_id,
        ).execute()

    except Exception as exc:
        message = str(exc)

        if (
            "event_teams_event_team_name_unique"
            in message
            or (
                "duplicate key value" in message
                and "team_name" in message
            )
        ):
            message = (
                f'Team name "{pending["team_name"]}" '
                "is already registered for this event. "
                "Please contact the club regarding this payment."
            )
        elif "event_members_event_usn_unique" in message:
            message = (
                "One of these USNs was registered while "
                "you were completing payment. Please "
                "contact the club regarding this payment."
            )

        return jsonify(
            ok=False,
            error=message,
        ), 400

    # Save only the confirmed DB team ID in the session.
    session["confirmed_team_id"] = team_id
    session.pop("pending_registration", None)
    session.pop("razorpay_order_id", None)
    session.modified = True

    return jsonify(
        ok=True,
        team_id=team_id,
        message=(
            "Payment verified successfully."
        ),
    )


# ============================================================
# PAYMENT RESULT
# ============================================================

@app.get("/payment-result")
def payment_result():

    team_id = (
        session.get("confirmed_team_id")
        or request.args.get("team_id")
    )

    success = (
        request.args.get(
            "success"
        )
        == "1"
    )

    if not supabase or not team_id:

        return render_template(
            "payment_result.html",
            success=False,
            team=None,
            members=[],
            message=(
                "Registration could not "
                "be loaded."
            ),
        )

    result = (
        supabase
        .table("event_teams")
        .select("*")
        .eq(
            "id",
            team_id,
        )
        .single()
        .execute()
    )

    if not result.data:

        return render_template(
            "payment_result.html",
            success=False,
            team=None,
            members=[],
            message=(
                "Registration not found."
            ),
        )

    team = result.data

    members_result = (
        supabase
        .table("event_members")
        .select(
            "name, usn, phone"
        )
        .eq(
            "team_id",
            team_id,
        )
        .order("id")
        .execute()
    )

    members = (
        members_result.data
        or []
    )

    confirmed = (
        success
        and bool(
            team.get("is_paid")
        )
    )

    event = find_event(team["event_name"])

    whatsapp_link = (
        str(event.get("whatsapp_link", "") or "").strip()
        if event
        else ""
    )

    return render_template(
        "payment_result.html",
        success=confirmed,
        team=team,
        members=members,
        whatsapp_link=whatsapp_link,
        message=(
            "Payment verified successfully. "
            "Your team registration is confirmed."
            if confirmed
            else
            "Payment was not verified. "
            "Please contact the club if money "
            "was deducted."
        ),
    )

# ============================================================
# CONFIRMATION PDF
# ============================================================

@app.get("/confirmation/<team_id>/pdf")
def confirmation_pdf(team_id):

    if not supabase:
        return (
            "Supabase is not configured.",
            500,
        )

    result = (
        supabase
        .table("event_teams")
        .select("*")
        .eq(
            "id",
            team_id,
        )
        .single()
        .execute()
    )

    if not result.data:
        return (
            "Registration not found.",
            404,
        )

    team = result.data

    # Only paid registrations get official PDFs.
    if not team.get("is_paid"):
        return (
            "Registration payment "
            "has not been verified.",
            403,
        )

    members_result = (
        supabase
        .table("event_members")
        .select(
            "name, usn, phone"
        )
        .eq(
            "team_id",
            team_id,
        )
        .order("id")
        .execute()
    )

    members = (
        members_result.data
        or []
    )

    event = find_event(
        team["event_name"]
    )

    if not event:
        return (
            "Event not found.",
            404,
        )

    whatsapp_link = str(
        event.get(
            "whatsapp_link",
            "",
        )
        or ""
    ).strip()

    pdf = generate_confirmation_pdf(
        team,
        members,
        whatsapp_link,
    )

    safe_team_name = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        str(
            team.get(
                "team_name",
                "team",
            )
        ),
    ).strip("_")

    filename = (
        f"ITV_{safe_team_name}"
        f"_Registration_Confirmation.pdf"
    )

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return jsonify(
        status="ok"
    )


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    app.run(
        debug=True
    )