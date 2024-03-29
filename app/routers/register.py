import os
from ..auth.auth_handler import create_jwt
from postmarker.core import PostmarkClient
from ..models.attendee import Attendee
from fastapi import APIRouter, HTTPException, Depends, Request
from pyairtable.api.table import Table
from ..dependencies import get_registration_table
from email_validator import validate_email, EmailNotValidError
from datetime import timedelta
import requests
import bisect
from sentry_sdk import capture_message
from dotenv import load_dotenv

load_dotenv()

POSTMARK_SERVER_TOKEN = os.getenv("POSTMARK_SERVER_TOKEN")
BLACKLIST_PATH = os.getenv("BLACKLIST_PATH")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

VERIFY_PATH = "https://register.losaltoshacks.com/verify"

router = APIRouter(
    prefix="/register",
    tags=["register"],
)

postmark = PostmarkClient(server_token=POSTMARK_SERVER_TOKEN, verbosity=3)


class EmailDomainValidator:
    def __init__(self):
        path = os.path.join(
            os.path.dirname(__file__), "../disposable_email_blocklist.txt"
        )
        with open(path) as fin:
            self.sorted_blacklist = tuple(fin.read().splitlines())

    def validate(self, email: str):
        index = bisect.bisect_left(self.sorted_blacklist, email)
        # Returns false if the domain is found in the blacklist, and true if not
        return not (
            index < len(self.sorted_blacklist) and self.sorted_blacklist[index] == email
        )


domain_validator = EmailDomainValidator()


@router.post("/attendee")
async def add_attendee(
    attendee: Attendee, request: Request, table: Table = Depends(get_registration_table)
):
    # Check if the reCAPTCHA token is valid
    # recaptcha = requests.post(
    #     "https://www.google.com/recaptcha/api/siteverify",
    #     data={
    #         "secret": RECAPTCHA_SECRET_KEY,
    #         "response": attendee.token,
    #     },
    # ).json()

    # if not recaptcha["success"]:
    #     e = HTTPException(
    #         status_code=400, detail="reCAPTCHA Error: " + str(recaptcha["error-codes"])
    #     )
    #     capture_message("reCAPTCHA Error: " + str(recaptcha["error-codes"]))
    #     raise e

    # if recaptcha["action"] != "submit":
    #     e = HTTPException(
    #         status_code=400,
    #         detail="Invalid reCAPTCHA action for this route.",
    #     )
    #     capture_message(
    #         f'Invalid reCAPTCHA action for this route. Action was {recaptcha["action"]}'
    #     )
    #     raise e

    # if recaptcha["score"] < 0.5:
    #     e = HTTPException(
    #         status_code=400,
    #         detail=f'Failed reCAPTCHA (score was {recaptcha["score"]}). Are you a bot?',
    #     )
    #     capture_message(f'Failed reCAPTCHA (score was {recaptcha["score"]}).')
    #     raise e

    # Check emails are valid
    try:
        email = validate_email(attendee.email, check_deliverability=True)
        attendee.email = email.ascii_email
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Your email address is not valid. {e}",
        )

    try:
        parent_email = validate_email(attendee.parent_email, check_deliverability=True)
        attendee.parent_email = parent_email.ascii_email
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Your parent/legal guardian's email address is not valid. {e}",
        )

    if attendee.email == attendee.parent_email:
        raise HTTPException(
            status_code=400,
            detail="Attendee email and parent email cannot be the same.",
        )

    if not domain_validator.validate(
        email.ascii_domain
    ) or not domain_validator.validate(parent_email.ascii_domain):
        e = HTTPException(
            status_code=400,
            detail="Do not use temporary email addresses.",
        )
        raise e

    # Verify both attendee and parent emails
    res = table.create(attendee.getAirtableFields())
    attendee_id = res["id"]

    # Tokens expire in 6 weeks
    expire_delta = timedelta(weeks=6)
    student_token = create_jwt(
        {"id": attendee_id, "type": "student"}, expires_delta=expire_delta
    )
    parent_token = create_jwt(
        {"id": attendee_id, "type": "parent"}, expires_delta=expire_delta
    )

    postmark.emails.send_with_template(
        TemplateAlias="email-verification",
        TemplateModel={
            "name": attendee.first_name,
            "action_url": f"{VERIFY_PATH}?token={student_token}",
        },
        From="hello@losaltoshacks.com",
        To=attendee.email,
    )

    postmark.emails.send_with_template(
        TemplateAlias="email-verification",
        TemplateModel={
            "name": attendee.first_name + "'s parent/guardian",
            "action_url": f"{VERIFY_PATH}?token={parent_token}",
        },
        From="hello@losaltoshacks.com",
        To=attendee.parent_email,
    )

    return res
