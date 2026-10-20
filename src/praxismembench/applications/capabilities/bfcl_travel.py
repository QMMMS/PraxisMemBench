from __future__ import annotations

import random
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


# BFCL base_costs lookup (route -> base price)
BASE_COSTS: Dict[Tuple[str, str], int] = {
    ("SFO", "LAX"): 200, ("SFO", "JFK"): 500, ("SFO", "ORD"): 400, ("SFO", "BOS"): 450,
    ("SFO", "RMS"): 300, ("SFO", "SBK"): 350, ("SFO", "MPC"): 370, ("SFO", "SVP"): 320,
    ("SFO", "SHD"): 330, ("SFO", "SSV"): 340, ("SFO", "OKD"): 360, ("SFO", "WLB"): 310,
    ("SFO", "CRH"): 380, ("SFO", "ATV"): 390, ("SFO", "PHV"): 420, ("SFO", "GFD"): 430,
    ("SFO", "CIA"): 700,
    ("LAX", "SFO"): 100, ("LAX", "JFK"): 600, ("LAX", "ORD"): 500, ("LAX", "BOS"): 550,
    ("LAX", "RMS"): 310, ("LAX", "SBK"): 320, ("LAX", "MPC"): 330, ("LAX", "SVP"): 340,
    ("LAX", "SHD"): 350, ("LAX", "SSV"): 360, ("LAX", "OKD"): 370, ("LAX", "WLB"): 380,
    ("LAX", "CRH"): 390, ("LAX", "ATV"): 400, ("LAX", "PHV"): 410, ("LAX", "GFD"): 420,
    ("LAX", "HND"): 430,
    ("JFK", "ORD"): 300, ("JFK", "BOS"): 250, ("JFK", "RMS"): 450, ("JFK", "SBK"): 460,
    ("JFK", "MPC"): 470, ("JFK", "SVP"): 480, ("JFK", "SHD"): 490, ("JFK", "SSV"): 500,
    ("JFK", "OKD"): 510, ("JFK", "WLB"): 520, ("JFK", "CRH"): 530, ("JFK", "ATV"): 540,
    ("JFK", "PHV"): 550, ("JFK", "GFD"): 560, ("JFK", "LAX"): 570, ("JFK", "HND"): 800,
    ("JFK", "PVG"): 950, ("JFK", "PEK"): 1000,
    ("ORD", "LAX"): 180, ("ORD", "BOS"): 200, ("ORD", "RMS"): 350, ("ORD", "SBK"): 360,
    ("ORD", "MPC"): 370, ("ORD", "SVP"): 380, ("ORD", "SHD"): 390, ("ORD", "SSV"): 400,
    ("ORD", "OKD"): 410, ("ORD", "WLB"): 420, ("ORD", "CRH"): 430, ("ORD", "ATV"): 440,
    ("ORD", "PHV"): 450, ("ORD", "GFD"): 460,
    ("RMS", "BOS"): 200, ("RMS", "JFK"): 210, ("RMS", "SBK"): 220, ("RMS", "MPC"): 230,
    ("RMS", "LAX"): 330,
    ("LHR", "CDG"): 100,
    ("OKD", "LAX"): 220,
}

EXCHANGE_RATES = {
    ("USD", "RMB"): 7, ("USD", "EUR"): 0.8, ("USD", "JPY"): 110, ("USD", "GBP"): 0.7,
    ("USD", "CAD"): 1.3, ("USD", "AUD"): 1.4, ("USD", "INR"): 70, ("USD", "RUB"): 60,
    ("USD", "BRL"): 3.8, ("USD", "MXN"): 20,
}

AIRPORTS = [
    "RMS", "SBK", "MPC", "SVP", "SHD", "CDG", "LHR", "SSV", "OKD", "WLB",
    "PEK", "HND", "HKG", "CIA", "CRH", "ATV", "PHV", "GFD", "SFO", "LAX", "JFK", "ORD", "BOS",
]

CITY_TO_AIRPORT = {
    "Rivermist": "RMS", "Stonebrook": "SBK", "Maplecrest": "MPC", "Silverpine": "SVP",
    "Shadowridge": "SHD", "London": "LHR", "Paris": "CDG", "Sunset Valley": "SSV",
    "Oakendale": "OKD", "Willowbend": "WLB", "Crescent Hollow": "CRH", "Autumnville": "ATV",
    "Pinehaven": "PHV", "Greenfield": "GFD", "San Francisco": "SFO", "Los Angeles": "LAX",
    "New York": "JFK", "Chicago": "ORD", "Boston": "BOS", "Beijing": "PEK",
    "Hong Kong": "HKG", "Rome": "CIA", "Tokyo": "HND",
}

CURRENCIES = ["USD", "RMB", "EUR", "JPY", "GBP", "CAD", "AUD", "INR", "RUB", "BRL", "MXN"]


class BFCLTravelToolkit:
    """Standardized wrapper for BFCL TravelAPI tools.

    Faithfully reproduces BFCL travel_booking.py behavior including:
    - Flight cost calculation based on route, class, date
    - Credit card balance and booking operations
    - Policy constraints: balance, budget limit, age >= 18
    """

    def __init__(
        self,
        credit_card_list: Optional[Dict[str, Dict[str, Any]]] = None,
        booking_record: Optional[Dict[str, Dict[str, Any]]] = None,
        access_token: Optional[str] = None,
        token_type: Optional[str] = None,
        token_expires_in: Optional[int] = None,
        token_scope: Optional[str] = None,
        user_first_name: Optional[str] = None,
        user_last_name: Optional[str] = None,
        budget_limit: Optional[float] = None,
        budget_context: Optional[str] = None,
        random_seed: int = 141053,
    ) -> None:
        """Initialize travel toolkit with optional state.

        BFCL DEFAULT_STATE fields:
        - credit_card_list, booking_record
        - access_token, token_type, token_expires_in, token_scope
        - user_first_name, user_last_name, budget_limit, budget_context
        - random_seed (used for _random generator)
        """
        self._random = random.Random(random_seed)
        self._random_seed: int = random_seed

        self.credit_card_list: Dict[str, Dict[str, Any]] = credit_card_list if credit_card_list is not None else {}
        self.booking_record: Dict[str, Dict[str, Any]] = booking_record if booking_record is not None else {}
        self.access_token: Optional[str] = access_token
        self.token_type: Optional[str] = token_type
        self.token_expires_in: Optional[int] = token_expires_in
        self.token_scope: Optional[str] = token_scope
        self.user_first_name: Optional[str] = user_first_name
        self.user_last_name: Optional[str] = user_last_name
        self.budget_limit: Optional[float] = budget_limit
        self.budget_context: Optional[str] = budget_context

        self._flight_cost_cache: Dict[str, Dict[str, float]] = {}

    def clone(self) -> "BFCLTravelToolkit":
        """Return toolkit reset to default BFCL state."""
        return BFCLTravelToolkit()

    def dump_state(self) -> Dict[str, Any]:
        """Export current state in BFCL format."""
        return {
            "credit_card_list": deepcopy(self.credit_card_list),
            "booking_record": deepcopy(self.booking_record),
            "access_token": self.access_token,
            "token_type": self.token_type,
            "token_expires_in": self.token_expires_in,
            "token_scope": self.token_scope,
            "user_first_name": self.user_first_name,
            "user_last_name": self.user_last_name,
            "budget_limit": self.budget_limit,
            "budget_context": self.budget_context,
            "random_seed": self._random_seed,
        }

    def list_tools(self) -> List[str]:
        """Return available tool names."""
        return [
            "authenticate_travel",
            "travel_get_login_status",
            "get_budget_fiscal_year",
            "get_budget_limit",
            "register_credit_card",
            "get_all_credit_cards",
            "get_credit_card_balance",
            "list_all_airports",
            "get_nearest_airport_by_city",
            "get_flight_cost",
            "book_flight",
            "cancel_booking",
            "get_booking_history",
            "retrieve_invoice",
            "compute_exchange_rate",
            "verify_traveler_information",
            "set_budget_limit",
            "purchase_insurance",
            "contact_customer_support",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke tool by name."""
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown travel tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def _check_token(self, access_token: str) -> Optional[str]:
        """Check if token is valid. Returns error message if invalid.

        BFCL distinguishes:
        - token_expires_in is None -> "Token not initialized"
        - token_expires_in is 0 -> "Token expired"
        """
        if self.token_expires_in is None:
            return "Token not initialized"
        if self.token_expires_in == 0:
            return "Token expired"
        if access_token != self.access_token:
            return "Invalid access token"
        return None

    # === Authentication ===

    def authenticate_travel(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        grant_type: str,
        user_first_name: str,
        user_last_name: str,
    ) -> Dict[str, Any]:
        """Authenticate travel API.

        Args:
            client_id, client_secret, refresh_token, grant_type: Auth params.
            user_first_name, user_last_name: User names.

        Returns:
            expires_in, access_token, token_type, scope.
        """
        self.token_expires_in = 2
        self.access_token = str(self._random.randint(100000, 999999))
        self.token_type = "Bearer"
        self.token_scope = grant_type
        self.user_first_name = user_first_name
        self.user_last_name = user_last_name
        return {
            "expires_in": 2,
            "access_token": self.access_token,
            "token_type": self.token_type,
            "scope": self.token_scope,
        }

    def travel_get_login_status(self) -> Dict[str, bool]:
        """Get login status.

        Returns:
            status: True if logged in.
        """
        is_logged = self.token_expires_in is not None and self.token_expires_in > 0
        return {"status": is_logged}

    def get_budget_fiscal_year(
        self,
        lastModifiedAfter: Optional[str] = None,
        includeRemoved: Optional[str] = None,
    ) -> Dict[str, str]:
        """Get budget fiscal year.

        Returns:
            budget_fiscal_year: "2018".
        """
        return {"budget_fiscal_year": "2018"}

    def get_budget_limit(self, access_token: str) -> Dict[str, Any]:
        """Get budget limit amount and any saved context.

        Args:
            access_token: Auth token.

        Returns:
            budget_limit: Current budget limit (may be None if not set).
            budget_context: Optional note explaining the limit.
        """
        error = self._check_token(access_token)
        if error:
            return {"error": error}
        result: Dict[str, Any] = {"budget_limit": self.budget_limit}
        if self.budget_context is not None:
            result["budget_context"] = self.budget_context
        return result

    # === Credit Card Management ===

    def register_credit_card(
        self,
        access_token: str,
        card_number: str,
        expiration_date: str,
        cardholder_name: str,
        card_verification_number: int,
    ) -> Dict[str, Any]:
        """Register a credit card.

        Args:
            access_token: Auth token.
            card_number, expiration_date, cardholder_name, card_verification_number: Card details.

        Returns:
            card_id: ID of registered card.
        """
        error = self._check_token(access_token)
        if error:
            return {"error": error}
        if card_number in [c.get("card_number") for c in self.credit_card_list.values()]:
            return {"error": "Card already registered"}

        card_id = str(self._random.randint(100000000000, 999999999999))
        self.credit_card_list[card_id] = {
            "card_number": card_number,
            "expiration_date": expiration_date,
            "cardholder_name": cardholder_name,
            "card_verification_number": card_verification_number,
            "balance": self._random.randint(10000, 99999),
        }
        return {"card_id": card_id}

    def get_all_credit_cards(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered credit cards.

        Returns:
            credit_card_list: All cards with details.
        """
        return {"credit_card_list": deepcopy(self.credit_card_list)}

    def get_credit_card_balance(
        self, access_token: str, card_id: str
    ) -> Dict[str, Any]:
        """Get credit card balance.

        Args:
            access_token: Auth token.
            card_id: Card ID.

        Returns:
            card_balance: Current balance.
        """
        error = self._check_token(access_token)
        if error:
            return {"error": error}
        if card_id not in self.credit_card_list:
            return {
                "error": "Card not registered. Here are a list of card_id's: " + str(list(self.credit_card_list.keys()))
            }
        return {"card_balance": self.credit_card_list[card_id]["balance"]}

    # === Flight Information ===

    def list_all_airports(self) -> List[str]:
        """List all available airports.

        Returns:
            airports: List of airport codes.
        """
        return AIRPORTS

    def get_nearest_airport_by_city(self, location: str) -> Dict[str, str]:
        """Get nearest airport by city name.

        Args:
            location: City name.

        Returns:
            nearest_airport: Airport code.
        """
        return {"nearest_airport": CITY_TO_AIRPORT.get(location, "Unknown")}

    def get_flight_cost(
        self, travel_from: str, travel_to: str, travel_date: str, travel_class: str
    ) -> Dict[str, List[float]]:
        """Get flight cost.

        Args:
            travel_from: Departure airport code.
            travel_to: Arrival airport code.
            travel_date: Date (YYYY-MM-DD).
            travel_class: economy, business, first.

        Returns:
            travel_cost_list: List of costs.
        """
        travel_pair = (travel_from, travel_to)
        if travel_pair not in BASE_COSTS:
            raise ValueError("No available route for the given airports.")

        base_cost = BASE_COSTS[travel_pair]

        # Class factor
        class_factor = {"economy": 1, "business": 2, "first": 5}
        if travel_class not in class_factor:
            raise ValueError("Invalid travel class. Options are: economy, business, first.")
        factor = class_factor[travel_class]

        # Date factor based on digit sum
        digit_sum = sum(int(c) for c in travel_date if c.isdigit())
        date_factor = 2 if digit_sum % 2 == 0 else 1

        cost = float(base_cost * factor * date_factor)
        key = f"{travel_from}|{travel_to}|{travel_class}|{travel_date}"
        self._flight_cost_cache[key] = {"cost": cost}

        return {"travel_cost_list": [cost]}

    # === Booking Operations ===

    def book_flight(
        self,
        access_token: str,
        card_id: str,
        travel_date: str,
        travel_from: str,
        travel_to: str,
        travel_class: str,
    ) -> Dict[str, Any]:
        """Book a flight.

        Args:
            access_token: Auth token.
            card_id: Credit card ID.
            travel_date, travel_from, travel_to, travel_class: Flight details.

        Returns:
            booking_id, transaction_id, booking_status, booking_history.
        """
        error = self._check_token(access_token)
        if error:
            return {"booking_status": False, "error": error}
        if card_id not in self.credit_card_list:
            return {"booking_status": False, "error": "Card not registered"}
        if "balance" not in self.credit_card_list[card_id]:
            return {"booking_status": False, "error": "Balance not found"}

        # Validate airport
        if travel_from not in AIRPORTS:
            return {"booking_status": False, "error": f"Invalid departure airport code: {travel_from}"}
        if travel_to not in AIRPORTS:
            return {"booking_status": False, "error": f"Invalid destination airport code: {travel_to}"}

        # Validate date
        try:
            datetime.strptime(travel_date, "%Y-%m-%d")
        except ValueError:
            return {"booking_status": False, "error": "Invalid date format. Use YYYY-MM-DD."}

        # Validate class
        if travel_class not in {"economy", "business", "first"}:
            return {"booking_status": False, "error": f"Invalid travel class."}

        # Calculate cost
        try:
            self.get_flight_cost(travel_from, travel_to, travel_date, travel_class)
            key = f"{travel_from}|{travel_to}|{travel_class}|{travel_date}"
            travel_cost = self._flight_cost_cache.get(key, {}).get("cost")
            if travel_cost is None:
                return {"booking_status": False, "error": "No available route"}
        except ValueError as e:
            return {"booking_status": False, "error": str(e)}

        # Check balance
        balance = self.credit_card_list[card_id]["balance"]
        if balance < travel_cost:
            return {"booking_status": False, "error": "Insufficient funds"}
        if self.budget_limit is not None and balance < self.budget_limit:
            return {"booking_status": False, "error": "Balance is less than budget limit"}

        # Deduct balance
        self.credit_card_list[card_id]["balance"] -= travel_cost

        # Create booking
        booking_id = str(self._random.randint(1000000, 9999999))
        transaction_id = str(self._random.randint(10000000, 99999999))
        self.booking_record[booking_id] = {
            "card_id": card_id,
            "travel_date": travel_date,
            "travel_from": travel_from,
            "travel_to": travel_to,
            "travel_class": travel_class,
            "travel_cost": travel_cost,
            "transaction_id": transaction_id,
        }

        return {
            "booking_id": booking_id,
            "transaction_id": transaction_id,
            "booking_status": True,
            "booking_history": {},
        }

    def cancel_booking(self, access_token: str, booking_id: str) -> Dict[str, Any]:
        """Cancel a booking.

        Args:
            access_token: Auth token.
            booking_id: Booking ID.

        Returns:
            cancel_status: True if successful.
        """
        error = self._check_token(access_token)
        if error:
            return {"cancel_status": False, "error": error}
        if booking_id not in self.booking_record:
            return {"cancel_status": False, "error": "Booking not found"}

        # Refund
        booking = self.booking_record[booking_id]
        card_id = booking["card_id"]
        travel_cost = booking["travel_cost"]
        self.credit_card_list[card_id]["balance"] += travel_cost
        del self.booking_record[booking_id]

        return {"cancel_status": True}

    def get_booking_history(self, access_token: str) -> Dict[str, Any]:
        """Get booking history.

        Args:
            access_token: Auth token.

        Returns:
            booking_history: All bookings.
        """
        error = self._check_token(access_token)
        if error:
            return {"error": error}
        return {"booking_history": deepcopy(self.booking_record)}

    def retrieve_invoice(
        self, access_token: str, booking_id: Optional[str] = None, insurance_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve invoice for booking.

        Args:
            access_token: Auth token.
            booking_id: Booking ID.

        Returns:
            invoice: Booking details.
        """
        error = self._check_token(access_token)
        if error:
            return {"error": error}
        if booking_id not in self.booking_record:
            return {"error": "Booking not found"}

        booking = self.booking_record[booking_id]
        return {
            "invoice": {
                "booking_id": booking_id,
                "travel_date": booking["travel_date"],
                "travel_from": booking["travel_from"],
                "travel_to": booking["travel_to"],
                "travel_class": booking["travel_class"],
                "travel_cost": booking["travel_cost"],
                "transaction_id": booking["transaction_id"],
            }
        }

    # === Exchange & Verification ===

    def compute_exchange_rate(
        self, base_currency: str, target_currency: str, value: float
    ) -> Dict[str, float]:
        """Compute exchange rate.

        Args:
            base_currency: Source currency.
            target_currency: Target currency.
            value: Amount to convert.

        Returns:
            exchanged_value: Converted amount.
        """
        if base_currency not in CURRENCIES or target_currency not in CURRENCIES:
            raise ValueError("No available exchange rate for the given currencies.")

        for (src, tgt), rate in EXCHANGE_RATES.items():
            if base_currency == src and target_currency == tgt:
                return {"exchanged_value": float(value * rate)}
            if base_currency == tgt and target_currency == src:
                return {"exchanged_value": round(value / rate, 2)}

        raise ValueError("No available exchange rate for the given currencies.")

    def verify_traveler_information(
        self, first_name: str, last_name: str, date_of_birth: str, passport_number: str
    ) -> Dict[str, Any]:
        """Verify traveler information.

        Args:
            first_name, last_name: Names.
            date_of_birth: YYYY-MM-DD.
            passport_number: Passport number.

        Returns:
            verification_status, verification_failure.
        """
        if first_name != self.user_first_name or last_name != self.user_last_name:
            return {
                "verification_status": False,
                "verification_failure": f"Cannot book flight information for another user. Expected {self.user_first_name} {self.user_last_name}, got {first_name} {last_name}",
            }

        try:
            birth = datetime.strptime(date_of_birth, "%Y-%m-%d")
            age = (datetime.today() - birth).days // 365
        except ValueError:
            return {"verification_status": False, "verification_failure": "Invalid date of birth format. Please use YYYY-MM-DD."}

        if age < 18:
            return {"verification_status": False, "verification_failure": "Traveler must be at least 18 years old."}

        if not passport_number.startswith("US"):
            return {"verification_status": False, "verification_failure": "Passport must be issued by the United States."}

        return {"verification_status": True}

    def set_budget_limit(
        self,
        access_token: str,
        budget_limit: float,
        budget_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set budget limit with optional context.

        Args:
            access_token: Auth token.
            budget_limit: Budget in USD.
            budget_context: Optional personalized rationale or travel-budget context to save with the limit.

        Returns:
            budget_limit: Set value.
            budget_context: Saved context when provided.
        """
        error = self._check_token(access_token)
        if error:
            return {"error": error}
        self.budget_limit = float(budget_limit)
        if budget_context is not None:
            self.budget_context = budget_context
        result: Dict[str, Any] = {"budget_limit": self.budget_limit}
        if self.budget_context is not None:
            result["budget_context"] = self.budget_context
        return result

    def purchase_insurance(
        self,
        access_token: str,
        insurance_type: str,
        booking_id: str,
        insurance_cost: float,
        card_id: str,
    ) -> Dict[str, Any]:
        """Purchase insurance.

        Args:
            access_token: Auth token.
            insurance_type, booking_id, insurance_cost, card_id: Details.

        Returns:
            insurance_id, insurance_status.
        """
        error = self._check_token(access_token)
        if error:
            return {"insurance_status": False, "error": error}
        if self.budget_limit is not None and self.budget_limit < insurance_cost:
            return {"insurance_status": False, "error": "Exceeded budget limit"}
        if booking_id not in self.booking_record:
            return {"insurance_status": False, "error": "Booking not found"}
        if card_id not in self.credit_card_list:
            return {"insurance_status": False, "error": "Credit card not registered"}

        self.credit_card_list[card_id]["balance"] -= insurance_cost
        return {
            "insurance_id": str(self._random.randint(100000000, 999999999)),
            "insurance_status": True,
        }

    def contact_customer_support(self, booking_id: str, message: str) -> Dict[str, str]:
        """Contact customer support.

        Args:
            booking_id: Booking ID.
            message: Message to send.

        Returns:
            customer_support_message: Acknowledgment.
        """
        if booking_id not in self.booking_record:
            return {"error": "Booking not found"}
        return {
            "customer_support_message": "Thank you for contacting customer support. Your message has been received and we will get back to you shortly."
        }


def load_default_travel_toolkit() -> BFCLTravelToolkit:
    """Load toolkit with default BFCL state."""
    return BFCLTravelToolkit()
