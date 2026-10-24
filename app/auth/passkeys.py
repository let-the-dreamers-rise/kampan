"""Passkey (WebAuthn) sign-up and sign-in. Discoverable credentials, so signing in needs no user name."""
from __future__ import annotations

import json
import re
import secrets

from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from app.repo.table import ConditionFailed, Table, now
from app.web import BadRequest, Request, Unauthorized

RP_NAME = "Kampan"
CHALLENGE_TTL = 300
HOST = re.compile(r"^(localhost|[a-z0-9-]+\.lambda-url\.[a-z0-9-]+\.on\.aws)(:\d+)?$")


def relying_party(request: Request) -> tuple[str, str]:
    """rp_id and expected origin. Only the function URL host or localhost are accepted."""
    if not HOST.match(request.host):
        raise BadRequest("passkeys work only on the app's own address")
    return request.host.split(":")[0], request.origin


def _store_challenge(table: Table, challenge: bytes, kind: str, extra: dict) -> str:
    cid = secrets.token_urlsafe(16)
    table.put({"pk": f"CHALLENGE#{cid}", "sk": kind, "challenge": bytes_to_base64url(challenge),
               "ttl": now() + CHALLENGE_TTL, **extra})
    return cid


def _take_challenge(table: Table, cid: str, kind: str) -> dict:
    if not isinstance(cid, str) or not cid:
        raise BadRequest("challenge_id is required")
    item = table.get(f"CHALLENGE#{cid}", kind)
    if item is None:
        raise Unauthorized("this sign-in attempt expired; start again")
    table.delete(f"CHALLENGE#{cid}", kind)  # single use
    return item


def registration_options(table: Table, request: Request, name: str) -> dict:
    rp_id, _ = relying_party(request)
    user_id = secrets.token_hex(12)
    opts = generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_name=name, user_display_name=name, user_id=user_id.encode(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.PREFERRED))
    cid = _store_challenge(table, opts.challenge, "register", {"user_id": user_id, "name": name})
    return {"challenge_id": cid, "options": json.loads(options_to_json(opts))}


def verify_registration(table: Table, request: Request, cid: str, credential: dict) -> dict:
    """Returns {user_id, name, credential_id, public_key, sign_count} for a verified new passkey."""
    pending = _take_challenge(table, cid, "register")
    rp_id, origin = relying_party(request)
    try:
        verified = verify_registration_response(credential=credential, expected_challenge=base64url_to_bytes(
            pending["challenge"]), expected_rp_id=rp_id, expected_origin=origin)
    except (InvalidRegistrationResponse, ValueError, KeyError, TypeError) as exc:
        raise Unauthorized(f"the passkey could not be verified: {exc}") from exc
    return {"user_id": pending["user_id"], "name": pending["name"],
            "credential_id": bytes_to_base64url(verified.credential_id),
            "public_key": bytes_to_base64url(verified.credential_public_key), "sign_count": verified.sign_count}


def authentication_options(table: Table, request: Request) -> dict:
    rp_id, _ = relying_party(request)
    opts = generate_authentication_options(rp_id=rp_id, user_verification=UserVerificationRequirement.PREFERRED)
    cid = _store_challenge(table, opts.challenge, "login", {})
    return {"challenge_id": cid, "options": json.loads(options_to_json(opts))}


def verify_authentication(table: Table, request: Request, cid: str, credential: dict) -> str:
    """Returns the user id that owns the passkey."""
    pending = _take_challenge(table, cid, "login")
    rp_id, origin = relying_party(request)
    cred_id = credential.get("id") if isinstance(credential, dict) else None
    stored = table.get(f"CRED#{cred_id}", "CRED") if isinstance(cred_id, str) else None
    if stored is None:
        raise Unauthorized("this passkey is not registered here; create an account first")
    try:
        verified = verify_authentication_response(
            credential=credential, expected_challenge=base64url_to_bytes(pending["challenge"]), expected_rp_id=rp_id,
            expected_origin=origin, credential_public_key=base64url_to_bytes(stored["public_key"]),
            credential_current_sign_count=int(stored.get("sign_count", 0)))
    except (InvalidAuthenticationResponse, ValueError, KeyError, TypeError) as exc:
        raise Unauthorized(f"the passkey could not be verified: {exc}") from exc
    try:
        table.update(f"CRED#{cred_id}", "CRED", {"sign_count": verified.new_sign_count, "last_used": now()})
    except ConditionFailed:
        pass
    return stored["user_id"]
