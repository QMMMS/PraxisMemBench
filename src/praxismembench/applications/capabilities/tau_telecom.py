from __future__ import annotations

import copy
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    import tomli as tomllib


def _jsonify(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonify(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonify(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class TauTelecomToolkit:
    """Standardized wrapper for Tau telecom assistant-side tools."""

    def __init__(self, db: Dict[str, Any]) -> None:
        self.db = copy.deepcopy(db)

    @classmethod
    def from_db_path(cls, db_path: str | Path) -> "TauTelecomToolkit":
        path = Path(db_path)
        with path.open("rb") as f:
            db = tomllib.load(f)
        return cls(db)

    def clone(self) -> "TauTelecomToolkit":
        return TauTelecomToolkit(self.db)

    def dump_db(self) -> Dict[str, Any]:
        return _jsonify(copy.deepcopy(self.db))

    def list_tools(self) -> List[str]:
        return [
            "get_customer_by_phone",
            "get_customer_by_id",
            "get_customer_by_name",
            "get_details_by_id",
            "suspend_line",
            "resume_line",
            "get_bills_for_customer",
            "send_payment_request",
            "get_data_usage",
            "enable_roaming",
            "disable_roaming",
            "transfer_to_human_agents",
            "refuel_data",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown telecom tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def _get_customer_by_phone_number(self, phone_number: str) -> Dict[str, Any]:
        for customer in self.db["customers"]:
            if customer["phone_number"] == phone_number:
                return customer
            for line_id in customer["line_ids"]:
                line = self._get_line_by_id(line_id)
                if line["phone_number"] == phone_number:
                    return customer
        raise ValueError(f"Customer with phone number {phone_number} not found")

    def _get_customer_by_id(self, customer_id: str) -> Dict[str, Any]:
        for customer in self.db["customers"]:
            if customer["customer_id"] == customer_id:
                return customer
        raise ValueError(f"Customer with ID {customer_id} not found")

    def _get_line_by_phone(self, phone_number: str) -> Dict[str, Any]:
        for line in self.db["lines"]:
            if line["phone_number"] == phone_number:
                return line
        raise ValueError(f"Line with phone number {phone_number} not found")

    def _get_line_by_id(self, line_id: str) -> Dict[str, Any]:
        for line in self.db["lines"]:
            if line["line_id"] == line_id:
                return line
        raise ValueError(f"Line with ID {line_id} not found")

    def _get_plan_by_id(self, plan_id: str) -> Dict[str, Any]:
        for plan in self.db["plans"]:
            if plan["plan_id"] == plan_id:
                return plan
        raise ValueError(f"Plan with ID {plan_id} not found")

    def _get_device_by_id(self, device_id: str) -> Dict[str, Any]:
        for device in self.db["devices"]:
            if device["device_id"] == device_id:
                return device
        raise ValueError(f"Device with ID {device_id} not found")

    def _get_bill_by_id(self, bill_id: str) -> Dict[str, Any]:
        for bill in self.db["bills"]:
            if bill["bill_id"] == bill_id:
                return bill
        raise ValueError(f"Bill with ID {bill_id} not found")

    def _get_target_line(self, customer_id: str, line_id: str) -> Dict[str, Any]:
        customer = self._get_customer_by_id(customer_id)
        if line_id not in customer["line_ids"]:
            raise ValueError(f"Line {line_id} not found for customer {customer_id}")
        return self._get_line_by_id(line_id)

    def _get_bills_awaiting_payment(self, customer: Dict[str, Any]) -> List[Dict[str, Any]]:
        bills = []
        for bill_id in customer["bill_ids"]:
            bill = self._get_bill_by_id(bill_id)
            if bill["status"] == "Awaiting Payment":
                bills.append(bill)
        return bills

    def _apply_one_time_charge(self, customer_id: str, amount: float, description: str) -> None:
        customer = self._get_customer_by_id(customer_id)
        draft_bill = None
        for bill_id in customer["bill_ids"]:
            bill = self._get_bill_by_id(bill_id)
            if bill["status"] == "Draft":
                draft_bill = bill
                break

        if draft_bill is None:
            today = self.get_today()
            next_month = today.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            if next_month.month < 12:
                next_after = next_month.replace(month=next_month.month + 1)
            else:
                next_after = next_month.replace(year=next_month.year + 1, month=1)
            new_bill_id = f"B{uuid.uuid4().hex[:8]}"
            draft_bill = {
                "bill_id": new_bill_id,
                "customer_id": customer_id,
                "period_start": next_month,
                "period_end": next_after - timedelta(days=1),
                "issue_date": next_month,
                "total_due": 0.0,
                "due_date": next_month + timedelta(days=14),
                "status": "Draft",
                "line_items": [],
            }
            self.db["bills"].append(draft_bill)
            customer["bill_ids"].append(new_bill_id)

        line_item = {
            "description": description,
            "amount": amount,
            "date": self.get_today(),
            "item_type": "Credit" if amount < 0 else "Charge",
        }
        draft_bill["line_items"].append(line_item)
        draft_bill["total_due"] += amount

    def get_today(self) -> date:
        return date(2025, 2, 25)

    def get_customer_by_phone(self, phone_number: str) -> Dict[str, Any]:
        return _jsonify(copy.deepcopy(self._get_customer_by_phone_number(phone_number)))

    def get_customer_by_id(self, customer_id: str) -> Dict[str, Any]:
        return _jsonify(copy.deepcopy(self._get_customer_by_id(customer_id)))

    def get_customer_by_name(self, full_name: str, dob: str) -> List[Dict[str, Any]]:
        matches = []
        for customer in self.db["customers"]:
            if customer["full_name"].lower() == full_name.lower() and customer["date_of_birth"] == dob:
                matches.append(copy.deepcopy(customer))
        return _jsonify(matches)

    def get_details_by_id(self, id: str) -> Dict[str, Any]:
        if id.startswith("L"):
            return _jsonify(copy.deepcopy(self._get_line_by_id(id)))
        if id.startswith("D"):
            return _jsonify(copy.deepcopy(self._get_device_by_id(id)))
        if id.startswith("B"):
            return _jsonify(copy.deepcopy(self._get_bill_by_id(id)))
        if id.startswith("C"):
            return _jsonify(copy.deepcopy(self._get_customer_by_id(id)))
        if id.startswith("P"):
            return _jsonify(copy.deepcopy(self._get_plan_by_id(id)))
        raise ValueError(f"Unknown ID format or type: {id}")

    def suspend_line(self, customer_id: str, line_id: str, reason: str) -> Dict[str, Any]:
        target_line = self._get_target_line(customer_id, line_id)
        if target_line["status"] != "Active":
            raise ValueError("Line must be active to suspend")
        target_line["status"] = "Suspended"
        target_line["suspension_start_date"] = self.get_today()
        return _jsonify(
            {
                "message": "Line suspended successfully. $5/month holding fee will apply.",
                "line": copy.deepcopy(target_line),
            }
        )

    def resume_line(self, customer_id: str, line_id: str) -> Dict[str, Any]:
        target_line = self._get_target_line(customer_id, line_id)
        if target_line["status"] not in ["Suspended", "Pending Activation"]:
            raise ValueError("Line must be suspended to resume")
        target_line["status"] = "Active"
        target_line["suspension_start_date"] = None
        return _jsonify({"message": "Line resumed successfully", "line": copy.deepcopy(target_line)})

    def get_bills_for_customer(self, customer_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        customer = self._get_customer_by_id(customer_id)
        bills = [self._get_bill_by_id(bill_id) for bill_id in customer["bill_ids"]]
        bills = sorted(bills, key=lambda bill: bill["issue_date"], reverse=True)
        return _jsonify(copy.deepcopy(bills[:limit]))

    def send_payment_request(self, customer_id: str, bill_id: str, note: Optional[str] = None) -> str:
        """Send a payment request for a bill.

        Args:
            customer_id: Customer receiving the payment request.
            bill_id: Bill to request payment for.
            note: Optional personalized reminder text to attach to the payment request.
        """
        customer = self._get_customer_by_id(customer_id)
        bills = self._get_bills_awaiting_payment(customer)
        if len(bills) != 0:
            raise ValueError("A bill is already awaiting payment for this customer")
        if bill_id not in customer["bill_ids"]:
            raise ValueError(f"Bill {bill_id} not found for customer {customer_id}")
        bill = self._get_bill_by_id(bill_id)
        bill["status"] = "Awaiting Payment"
        if note is not None:
            bill["payment_request_note"] = note
        return f"Payment request sent to the customer for bill {bill['bill_id']}"

    def get_data_usage(self, customer_id: str, line_id: str) -> Dict[str, Any]:
        target_line = self._get_target_line(customer_id, line_id)
        plan = self._get_plan_by_id(target_line["plan_id"])
        today = self.get_today()
        if today.month < 12:
            cycle_end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
        else:
            cycle_end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        return _jsonify(
            {
                "line_id": line_id,
                "data_used_gb": target_line["data_used_gb"],
                "data_limit_gb": plan["data_limit_gb"],
                "data_refueling_gb": target_line["data_refueling_gb"],
                "cycle_end_date": cycle_end_date,
            }
        )

    def enable_roaming(self, customer_id: str, line_id: str) -> str:
        target_line = self._get_target_line(customer_id, line_id)
        if target_line["roaming_enabled"]:
            return "Roaming was already enabled"
        target_line["roaming_enabled"] = True
        return "Roaming enabled successfully"

    def disable_roaming(self, customer_id: str, line_id: str) -> str:
        target_line = self._get_target_line(customer_id, line_id)
        if not target_line["roaming_enabled"]:
            return "Roaming was already disabled"
        target_line["roaming_enabled"] = False
        return "Roaming disabled successfully"

    def transfer_to_human_agents(self, summary: str) -> str:
        return "Transfer successful"

    def refuel_data(self, customer_id: str, line_id: str, gb_amount: float) -> Dict[str, Any]:
        target_line = self._get_target_line(customer_id, line_id)
        if gb_amount <= 0:
            raise ValueError("Refuel amount must be positive")
        plan = self._get_plan_by_id(target_line["plan_id"])
        charge_amount = gb_amount * plan["data_refueling_price_per_gb"]
        target_line["data_refueling_gb"] += gb_amount
        self._apply_one_time_charge(
            customer_id,
            charge_amount,
            f"Data refueling: {gb_amount} GB at ${plan['data_refueling_price_per_gb']}/GB",
        )
        return _jsonify(
            {
                "message": f"Successfully added {gb_amount} GB of data for line {line_id} for ${charge_amount:.2f}",
                "new_data_refueling_gb": target_line["data_refueling_gb"],
                "charge": charge_amount,
            }
        )


def load_telecom_toolkit(db_path: str | Path) -> TauTelecomToolkit:
    return TauTelecomToolkit.from_db_path(db_path)
