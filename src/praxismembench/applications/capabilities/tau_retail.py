from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


class TauRetailToolkit:
    """Standardized wrapper for Tau retail assistant-side tools."""

    def __init__(self, db: Dict[str, Any]) -> None:
        self.db = deepcopy(db)

    @classmethod
    def from_db_path(cls, db_path: str | Path) -> "TauRetailToolkit":
        path = Path(db_path)
        db = json.loads(path.read_text(encoding="utf-8"))
        return cls(db)

    def clone(self) -> "TauRetailToolkit":
        return TauRetailToolkit(self.db)

    def dump_db(self) -> Dict[str, Any]:
        return deepcopy(self.db)

    def dump_state(self) -> Dict[str, Any]:
        return self.dump_db()

    def list_tools(self) -> List[str]:
        return [
            "calculate",
            "cancel_pending_order",
            "exchange_delivered_order_items",
            "find_user_id_by_email",
            "find_user_id_by_name_zip",
            "get_item_details",
            "get_order_details",
            "get_product_details",
            "get_user_details",
            "list_all_product_types",
            "modify_pending_order_address",
            "modify_pending_order_items",
            "modify_pending_order_payment",
            "modify_user_address",
            "return_delivered_order_items",
            "transfer_to_human_agents",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown retail tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def _get_order(self, order_id: str) -> Dict[str, Any]:
        if order_id not in self.db["orders"]:
            raise ValueError("Order not found")
        return self.db["orders"][order_id]

    def _get_user(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self.db["users"]:
            raise ValueError("User not found")
        return self.db["users"][user_id]

    def _get_product(self, product_id: str) -> Dict[str, Any]:
        if product_id not in self.db["products"]:
            raise ValueError("Product not found")
        return self.db["products"][product_id]

    def _get_item(self, item_id: str) -> Dict[str, Any]:
        for product in self.db["products"].values():
            if item_id in product["variants"]:
                return product["variants"][item_id]
        raise ValueError("Item not found")

    def _get_variant(self, product_id: str, variant_id: str) -> Dict[str, Any]:
        product = self._get_product(product_id)
        if variant_id not in product["variants"]:
            raise ValueError("Variant not found")
        return product["variants"][variant_id]

    def _get_payment_method(self, user_id: str, payment_method_id: str) -> Dict[str, Any]:
        user = self._get_user(user_id)
        if payment_method_id not in user["payment_methods"]:
            raise ValueError("Payment method not found")
        return user["payment_methods"][payment_method_id]

    def _is_pending_order(self, order: Dict[str, Any]) -> bool:
        return "pending" in order["status"]

    def calculate(self, expression: str) -> str:
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    def cancel_pending_order(
        self,
        order_id: str,
        reason: str,
        cancellation_note: str | None = None,
    ) -> Dict[str, Any]:
        """Cancel a pending order.

        Args:
            order_id: Order identifier to cancel.
            reason: Cancellation reason. Must be "no longer needed" or "ordered by mistake".
            cancellation_note: Optional free-form user context to save on the order state.
        """
        order = self._get_order(order_id)
        if order["status"] != "pending":
            raise ValueError("Non-pending order cannot be cancelled")
        if reason not in {"no longer needed", "ordered by mistake"}:
            raise ValueError("Invalid reason")

        refunds = []
        for payment in order["payment_history"]:
            refunds.append(
                {
                    "transaction_type": "refund",
                    "amount": payment["amount"],
                    "payment_method_id": payment["payment_method_id"],
                }
            )
            user = self._get_user(order["user_id"])
            payment_method = self._get_payment_method(user["user_id"], payment["payment_method_id"])
            if payment_method["source"] == "gift_card":
                payment_method["balance"] = round(payment_method["balance"] + payment["amount"], 2)

        order["status"] = "cancelled"
        order["cancel_reason"] = reason
        if cancellation_note is not None and cancellation_note.strip():
            order["cancellation_note"] = cancellation_note
        order["payment_history"].extend(refunds)
        return deepcopy(order)

    def exchange_delivered_order_items(
        self,
        order_id: str,
        item_ids: List[str],
        new_item_ids: List[str],
        payment_method_id: str,
    ) -> Dict[str, Any]:
        order = self._get_order(order_id)
        if order["status"] != "delivered":
            raise ValueError("Non-delivered order cannot be exchanged")

        all_item_ids = [item["item_id"] for item in order["items"]]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                raise ValueError(f"Number of {item_id} not found.")

        if len(item_ids) != len(new_item_ids):
            raise ValueError("The number of items to be exchanged should match.")

        diff_price = 0.0
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            item = next((item for item in order["items"] if item["item_id"] == item_id), None)
            if item is None:
                raise ValueError(f"Item {item_id} not found")
            product_id = item["product_id"]
            variant = self._get_variant(product_id, new_item_id)
            if not variant["available"]:
                raise ValueError(f"New item {new_item_id} not found or available")
            diff_price += variant["price"] - item["price"]

        diff_price = round(diff_price, 2)
        payment_method = self._get_payment_method(order["user_id"], payment_method_id)
        if payment_method["source"] == "gift_card" and payment_method["balance"] < diff_price:
            raise ValueError("Insufficient gift card balance to pay for the price difference")

        order["status"] = "exchange requested"
        order["exchange_items"] = sorted(item_ids)
        order["exchange_new_items"] = sorted(new_item_ids)
        order["exchange_payment_method_id"] = payment_method_id
        order["exchange_price_difference"] = diff_price
        return deepcopy(order)

    def find_user_id_by_name_zip(self, first_name: str, last_name: str, zip: str) -> str:
        for user_id, user in self.db["users"].items():
            if (
                user["name"]["first_name"].lower() == first_name.lower()
                and user["name"]["last_name"].lower() == last_name.lower()
                and user["address"]["zip"] == zip
            ):
                return user_id
        raise ValueError("User not found")

    def find_user_id_by_email(self, email: str) -> str:
        for user_id, user in self.db["users"].items():
            if user["email"].lower() == email.lower():
                return user_id
        raise ValueError("User not found")

    def get_order_details(self, order_id: str) -> Dict[str, Any]:
        return deepcopy(self._get_order(order_id))

    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        return deepcopy(self._get_product(product_id))

    def get_item_details(self, item_id: str) -> Dict[str, Any]:
        return deepcopy(self._get_item(item_id))

    def get_user_details(self, user_id: str) -> Dict[str, Any]:
        return deepcopy(self._get_user(user_id))

    def list_all_product_types(self) -> str:
        product_dict = {
            product["name"]: product["product_id"] for product in self.db["products"].values()
        }
        return json.dumps(product_dict, sort_keys=True)

    def modify_pending_order_address(
        self,
        order_id: str,
        address1: str,
        address2: str,
        city: str,
        state: str,
        country: str,
        zip: str,
    ) -> Dict[str, Any]:
        order = self._get_order(order_id)
        if not self._is_pending_order(order):
            raise ValueError("Non-pending order cannot be modified")
        order["address"] = {
            "address1": address1,
            "address2": address2,
            "city": city,
            "state": state,
            "country": country,
            "zip": zip,
        }
        return deepcopy(order)

    def modify_pending_order_items(
        self,
        order_id: str,
        item_ids: List[str],
        new_item_ids: List[str],
        payment_method_id: str,
    ) -> Dict[str, Any]:
        order = self._get_order(order_id)
        if order["status"] != "pending":
            raise ValueError("Non-pending order cannot be modified")

        all_item_ids = [item["item_id"] for item in order["items"]]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                raise ValueError(f"{item_id} not found")

        if len(item_ids) != len(new_item_ids):
            raise ValueError("The number of items to be exchanged should match")

        diff_price = 0.0
        replacement_info: Dict[str, Dict[str, Any]] = {}
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            if item_id == new_item_id:
                raise ValueError("The new item id should be different from the old item id")
            item = next((item for item in order["items"] if item["item_id"] == item_id), None)
            if item is None:
                raise ValueError(f"Item {item_id} not found")
            variant = self._get_variant(item["product_id"], new_item_id)
            if not variant["available"]:
                raise ValueError(f"New item {new_item_id} not found or available")
            diff_price += variant["price"] - item["price"]
            replacement_info[item_id] = deepcopy(variant)

        payment_method = self._get_payment_method(order["user_id"], payment_method_id)
        if payment_method["source"] == "gift_card" and payment_method["balance"] < diff_price:
            raise ValueError("Insufficient gift card balance to pay for the new item")

        order["payment_history"].append(
            {
                "transaction_type": "payment" if diff_price > 0 else "refund",
                "amount": abs(diff_price),
                "payment_method_id": payment_method_id,
            }
        )
        if payment_method["source"] == "gift_card":
            payment_method["balance"] = round(payment_method["balance"] - diff_price, 2)

        counts: Dict[str, int] = {}
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            counts[item_id] = counts.get(item_id, 0) + 1
            seen = 0
            for item in order["items"]:
                if item["item_id"] == item_id:
                    seen += 1
                    if seen == counts[item_id]:
                        variant = replacement_info[item_id]
                        item["item_id"] = new_item_id
                        item["price"] = variant["price"]
                        item["options"] = deepcopy(variant["options"])
                        break
        order["status"] = "pending (item modified)"
        return deepcopy(order)

    def modify_pending_order_payment(self, order_id: str, payment_method_id: str) -> Dict[str, Any]:
        order = self._get_order(order_id)
        if not self._is_pending_order(order):
            raise ValueError("Non-pending order cannot be modified")
        payment_method = self._get_payment_method(order["user_id"], payment_method_id)
        if len(order["payment_history"]) != 1 or order["payment_history"][0]["transaction_type"] != "payment":
            raise ValueError("There should be exactly one payment for a pending order")
        if order["payment_history"][0]["payment_method_id"] == payment_method_id:
            raise ValueError("The new payment method should be different from the current one")

        amount = order["payment_history"][0]["amount"]
        if payment_method["source"] == "gift_card" and payment_method["balance"] < amount:
            raise ValueError("Insufficient gift card balance to pay for the order")

        original_payment_method_id = order["payment_history"][0]["payment_method_id"]
        order["payment_history"].extend(
            [
                {
                    "transaction_type": "payment",
                    "amount": amount,
                    "payment_method_id": payment_method_id,
                },
                {
                    "transaction_type": "refund",
                    "amount": amount,
                    "payment_method_id": original_payment_method_id,
                },
            ]
        )
        if payment_method["source"] == "gift_card":
            payment_method["balance"] = round(payment_method["balance"] - amount, 2)
        old_payment_method = self._get_payment_method(order["user_id"], original_payment_method_id)
        if old_payment_method["source"] == "gift_card":
            old_payment_method["balance"] = round(old_payment_method["balance"] + amount, 2)
        return deepcopy(order)

    def modify_user_address(
        self,
        user_id: str,
        address1: str,
        address2: str,
        city: str,
        state: str,
        country: str,
        zip: str,
    ) -> Dict[str, Any]:
        user = self._get_user(user_id)
        user["address"] = {
            "address1": address1,
            "address2": address2,
            "city": city,
            "state": state,
            "country": country,
            "zip": zip,
        }
        return deepcopy(user)

    def return_delivered_order_items(
        self,
        order_id: str,
        item_ids: List[str],
        payment_method_id: str,
    ) -> Dict[str, Any]:
        order = self._get_order(order_id)
        if order["status"] != "delivered":
            raise ValueError("Non-delivered order cannot be returned")
        user = self._get_user(order["user_id"])
        payment_method = self._get_payment_method(user["user_id"], payment_method_id)
        if payment_method["source"] != "gift_card" and payment_method_id != order["payment_history"][0]["payment_method_id"]:
            raise ValueError("Payment method should be the original payment method")

        all_item_ids = [item["item_id"] for item in order["items"]]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                raise ValueError("Some item not found")

        order["status"] = "return requested"
        order["return_items"] = sorted(item_ids)
        order["return_payment_method_id"] = payment_method_id
        return deepcopy(order)

    def transfer_to_human_agents(self, summary: str) -> str:
        return "Transfer successful"


def load_retail_toolkit(db_path: str | Path) -> TauRetailToolkit:
    return TauRetailToolkit.from_db_path(db_path)
