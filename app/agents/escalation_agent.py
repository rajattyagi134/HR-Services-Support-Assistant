"""Agent 3: classifies which team owns an unanswered query and emails them."""
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.guardrails import redact_pii
from app.llm import get_llm

_SYSTEM_PROMPT = """You triage HR support requests that could not be answered from policy
documents. Classify the request into exactly one team:
- IT: laptop/hardware, accounts, VPN, software, password resets, network access.
- PAYROLL: salary, payslips, tax forms, deductions, reimbursement payments, bank details.
- HR: everything else (leave, benefits, policy, onboarding, conduct, general HR).

Respond with only the single label, nothing else."""

_TEAM_NAMES = {"IT": "IT Support", "PAYROLL": "Payroll", "HR": "Human Resources"}

_TEAM_EMAILS = {
    "IT": lambda: settings.it_team_email,
    "PAYROLL": lambda: settings.payroll_team_email,
    "HR": lambda: settings.hr_team_email,
}


@dataclass
class EscalationResult:
    department: str
    team_email: str
    notified: bool


class EscalationAgent:
    """Routes unresolved queries to the right team via email (Agent 3)."""

    def __init__(self):
        self._llm = get_llm(temperature=0.0)

    def escalate(
        self,
        message: str,
        reason: str,
        employee_id: str,
        employee_email: str,
    ) -> EscalationResult:
        department = self._classify_department(message)
        team_email = _TEAM_EMAILS[department]()
        notified = self._send_email(department, team_email, message, reason, employee_id, employee_email)
        return EscalationResult(department=department, team_email=team_email, notified=notified)

    def _classify_department(self, message: str) -> str:
        response = self._llm.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=message)]
        )
        label = response.content.strip().upper()
        return label if label in _TEAM_EMAILS else "HR"

    def _send_email(
        self,
        department: str,
        team_email: str,
        message: str,
        reason: str,
        employee_id: str,
        employee_email: str,
    ) -> bool:
        team_name = _TEAM_NAMES[department]
        today = datetime.now(timezone.utc).strftime("%d %b %Y")
        email = EmailMessage()
        email["Subject"] = f"HR Support Escalation - {employee_id} needs {team_name} assistance"
        email["From"] = settings.smtp_from
        email["To"] = team_email
        email["Reply-To"] = employee_email
        email.set_content(
            f"Dear {team_name} Team,\n\n"
            f"The HR Support Assistant was unable to resolve the request below from our "
            f"policy documents and is escalating it for your attention.\n\n"
            f"Employee ID: {employee_id}\n"
            f"Employee Email: {employee_email}\n"
            f"Date: {today}\n"
            f"Escalation Reason: {reason}\n\n"
            f"Employee's Request:\n\"{redact_pii(message)}\"\n\n"
            f"Please reach out to the employee directly at {employee_email} at your earliest "
            f"convenience.\n\n"
            f"Best regards,\n"
            f"HR Support Assistant (automated)"
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
                smtp.send_message(email)
            return True
        except OSError:
            return False
