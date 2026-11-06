"""Demo auth: password 'demo' for every persona; token is the username. Not for production."""
from fastapi import Depends, Header, HTTPException

from . import refdata
from .schemas import Persona


def current_user(authorization: str = Header(default="")) -> Persona:
    token = authorization.removeprefix("Bearer ").strip()
    p = next((p for p in refdata.personas() if p["username"] == token), None)
    if not p:
        raise HTTPException(401, "Not signed in")
    return Persona(**p)


def require(*roles):
    def dep(user: Persona = Depends(current_user)) -> Persona:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return user
    return dep


ATEC_ROLES = ("g3", "range_scheduler", "atec_viewer")
