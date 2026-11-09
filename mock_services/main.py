"""Mock company services for the prototype.

HR directory:  GET  /hr/employees/{username}
Email notifier: POST /email/send      GET /email/outbox
Run:  uvicorn mock_services.main:app --port 9000
"""
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Mock company services")

EMPLOYEES = {
    "emp1":   {"name": "Eva Employee",  "email": "eva.employee@company.local",  "department": "Operations", "status": "active"},
    "hr1":    {"name": "Hari HR",       "email": "hari.hr@company.local",       "department": "HR",         "status": "active"},
    "it1":    {"name": "Ivan IT",       "email": "ivan.it@company.local",       "department": "IT",         "status": "active"},
    "fin1":   {"name": "Fiona Finance", "email": "fiona.finance@company.local", "department": "Finance",    "status": "active"},
    "legal1": {"name": "Leo Legal",     "email": "leo.legal@company.local",     "department": "Legal",      "status": "active"},
    "admin1": {"name": "Asha Admin",    "email": "asha.admin@company.local",    "department": "IT",         "status": "active"},
    "admin2": {"name": "Second Admin",  "email": "second.admin@company.local",  "department": "IT",         "status": "active"},
    "kavya":  {"name": "Kavya",         "email": "kavya@company.local",         "department": "IT",         "status": "active"},
}
OUTBOX = []


class Email(BaseModel):
    to: str = Field(min_length=3, max_length=200)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(max_length=2000)


@app.get("/hr/employees/{username}")
def employee(username: str):
    person = EMPLOYEES.get(username)
    if not person:
        raise HTTPException(status_code=404, detail="Employee not found")
    return person


@app.post("/email/send")
def send(mail: Email):
    OUTBOX.append({"time": datetime.now().isoformat(timespec="seconds"),
                   **mail.model_dump()})
    print(f"[MOCK EMAIL] to={mail.to} subject={mail.subject}")
    return {"sent": True, "id": len(OUTBOX)}


@app.get("/email/outbox")
def outbox():
    return OUTBOX