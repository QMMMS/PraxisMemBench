from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


AIRPORTS = [
    {"iata": "SFO", "city": "San Francisco"},
    {"iata": "JFK", "city": "New York"},
    {"iata": "LAX", "city": "Los Angeles"},
    {"iata": "ORD", "city": "Chicago"},
    {"iata": "DFW", "city": "Dallas"},
    {"iata": "DEN", "city": "Denver"},
    {"iata": "SEA", "city": "Seattle"},
    {"iata": "ATL", "city": "Atlanta"},
    {"iata": "MIA", "city": "Miami"},
    {"iata": "BOS", "city": "Boston"},
    {"iata": "PHX", "city": "Phoenix"},
    {"iata": "IAH", "city": "Houston"},
    {"iata": "LAS", "city": "Las Vegas"},
    {"iata": "MCO", "city": "Orlando"},
    {"iata": "EWR", "city": "Newark"},
    {"iata": "CLT", "city": "Charlotte"},
    {"iata": "MSP", "city": "Minneapolis"},
    {"iata": "DTW", "city": "Detroit"},
    {"iata": "PHL", "city": "Philadelphia"},
    {"iata": "LGA", "city": "LaGuardia"},
]


class TauAirlineToolkit:
    """Standardized wrapper for Tau airline assistant-side tools."""

    def __init__(self, db: Dict[str, Any]) -> None:
        self.db = deepcopy(db)

    @classmethod
    def from_db_path(cls, db_path: str | Path) -> "TauAirlineToolkit":
        path = Path(db_path)
        db = json.loads(path.read_text(encoding="utf-8"))
        return cls(db)

    def clone(self) -> "TauAirlineToolkit":
        return TauAirlineToolkit(self.db)

    def dump_db(self) -> Dict[str, Any]:
        return deepcopy(self.db)

    def list_tools(self) -> List[str]:
        return [
            "book_reservation",
            "calculate",
            "cancel_reservation",
            "get_flight_status",
            "get_reservation_details",
            "get_user_details",
            "list_all_airports",
            "lookup_reservations",
            "search_direct_flight",
            "search_onestop_flight",
            "send_certificate",
            "transfer_to_human_agents",
            "update_reservation_baggages",
            "update_reservation_flights",
            "update_reservation_passengers",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown airline tool: {tool_name}")
        tool = getattr(self, tool_name)
        return tool(**kwargs)

    def _get_user(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self.db["users"]:
            raise ValueError(f"User {user_id} not found")
        return self.db["users"][user_id]

    def _get_reservation(self, reservation_id: str) -> Dict[str, Any]:
        if reservation_id not in self.db["reservations"]:
            raise ValueError(f"Reservation {reservation_id} not found")
        return self.db["reservations"][reservation_id]

    def _get_flight(self, flight_number: str) -> Dict[str, Any]:
        if flight_number not in self.db["flights"]:
            raise ValueError(f"Flight {flight_number} not found")
        return self.db["flights"][flight_number]

    def _get_flight_instance(self, flight_number: str, date: str) -> Dict[str, Any]:
        flight = self._get_flight(flight_number)
        if date not in flight["dates"]:
            raise ValueError(f"Flight {flight_number} not found on date {date}")
        return flight["dates"][date]

    def _get_new_reservation_id(self) -> str:
        for reservation_id in ["HATHAT", "HATHAU", "HATHAV"]:
            if reservation_id not in self.db["reservations"]:
                return reservation_id
        raise ValueError("Too many reservations")

    def _get_new_payment_ids(self) -> List[int]:
        return [3221322, 3221323, 3221324]

    def _get_datetime(self) -> str:
        return "2024-05-15T15:00:00"

    def _reservation_summary(self, reservation: Dict[str, Any]) -> Dict[str, Any]:
        flights = [
            {
                "flight_number": flight["flight_number"],
                "date": flight["date"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "route": f"{flight['origin']}-{flight['destination']}",
            }
            for flight in reservation["flights"]
        ]
        return {
            "reservation_id": reservation["reservation_id"],
            "user_id": reservation["user_id"],
            "status": reservation.get("status"),
            "origin": reservation["origin"],
            "destination": reservation["destination"],
            "route": f"{reservation['origin']}-{reservation['destination']}",
            "flight_type": reservation["flight_type"],
            "cabin": reservation["cabin"],
            "flights": flights,
        }

    def _airport_search_terms(self, airport_code: str) -> List[str]:
        terms = [airport_code]
        airport = next((item for item in AIRPORTS if item["iata"] == airport_code), None)
        if airport is not None:
            terms.append(airport["city"])
        return terms

    def _reservation_search_text(self, reservation: Dict[str, Any]) -> str:
        user = self.db["users"].get(reservation["user_id"], {})
        user_name = user.get("name", {})
        parts = [
            reservation["reservation_id"],
            reservation["user_id"],
            reservation.get("origin", ""),
            reservation.get("destination", ""),
            reservation.get("flight_type", ""),
            reservation.get("cabin", ""),
            user.get("email", ""),
            user_name.get("first_name", ""),
            user_name.get("last_name", ""),
        ]
        parts.extend(self._airport_search_terms(reservation["origin"]))
        parts.extend(self._airport_search_terms(reservation["destination"]))
        for flight in reservation["flights"]:
            parts.extend(
                [
                    flight["flight_number"],
                    flight["date"],
                    flight["origin"],
                    flight["destination"],
                    f"{flight['origin']}-{flight['destination']}",
                    f"{flight['origin']} to {flight['destination']}",
                ]
            )
            parts.extend(self._airport_search_terms(flight["origin"]))
            parts.extend(self._airport_search_terms(flight["destination"]))
        return " ".join(str(part).lower() for part in parts if part)

    def _search_direct_flight(
        self,
        date: str,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        leave_after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for flight in self.db["flights"].values():
            if origin is not None and flight["origin"] != origin:
                continue
            if destination is not None and flight["destination"] != destination:
                continue
            if date not in flight["dates"]:
                continue
            flight_date_data = flight["dates"][date]
            if flight_date_data["status"] != "available":
                continue
            if leave_after is not None and flight["scheduled_departure_time_est"] < leave_after:
                continue
            results.append(
                {
                    "flight_number": flight["flight_number"],
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "status": "available",
                    "scheduled_departure_time_est": flight["scheduled_departure_time_est"],
                    "scheduled_arrival_time_est": flight["scheduled_arrival_time_est"],
                    "available_seats": deepcopy(flight_date_data["available_seats"]),
                    "prices": deepcopy(flight_date_data["prices"]),
                }
            )
        return results

    def _payment_for_update(
        self,
        user: Dict[str, Any],
        payment_id: str,
        total_price: int,
    ) -> Optional[Dict[str, Any]]:
        if payment_id not in user["payment_methods"]:
            raise ValueError("Payment method not found")
        payment_method = user["payment_methods"][payment_id]
        if payment_method["source"] == "certificate":
            raise ValueError("Certificate cannot be used to update reservation")
        if payment_method["source"] == "gift_card" and payment_method["amount"] < total_price:
            raise ValueError("Gift card balance is not enough")
        if payment_method["source"] == "gift_card":
            payment_method["amount"] -= total_price
        if total_price != 0:
            return {"payment_id": payment_id, "amount": total_price}
        return None

    def book_reservation(
        self,
        user_id: str,
        origin: str,
        destination: str,
        flight_type: str,
        cabin: str,
        flights: List[Dict[str, Any]],
        passengers: List[Dict[str, Any]],
        payment_methods: List[Dict[str, Any]],
        total_baggages: int,
        nonfree_baggages: int,
        insurance: str,
    ) -> Dict[str, Any]:
        user = self._get_user(user_id)
        reservation_id = self._get_new_reservation_id()
        reservation = {
            "reservation_id": reservation_id,
            "user_id": user_id,
            "origin": origin,
            "destination": destination,
            "flight_type": flight_type,
            "cabin": cabin,
            "flights": [],
            "passengers": deepcopy(passengers),
            "payment_history": deepcopy(payment_methods),
            "created_at": self._get_datetime(),
            "total_baggages": total_baggages,
            "nonfree_baggages": nonfree_baggages,
            "insurance": insurance,
            "status": None,
        }

        total_price = 0
        all_flights_date_data: List[Dict[str, Any]] = []
        for flight_info in flights:
            flight_number = flight_info["flight_number"]
            date = flight_info["date"]
            flight = self._get_flight(flight_number)
            flight_date_data = self._get_flight_instance(flight_number, date)
            if flight_date_data["status"] != "available":
                raise ValueError(f"Flight {flight_number} not available on date {date}")
            if flight_date_data["available_seats"][cabin] < len(passengers):
                raise ValueError(f"Not enough seats on flight {flight_number}")
            price = flight_date_data["prices"][cabin]
            reservation["flights"].append(
                {
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "flight_number": flight_number,
                    "date": date,
                    "price": price,
                }
            )
            all_flights_date_data.append(flight_date_data)
            total_price += price * len(passengers)

        if insurance == "yes":
            total_price += 30 * len(passengers)
        total_price += 50 * nonfree_baggages

        for payment_method in payment_methods:
            payment_id = payment_method["payment_id"]
            amount = payment_method["amount"]
            if payment_id not in user["payment_methods"]:
                raise ValueError(f"Payment method {payment_id} not found")
            user_payment_method = user["payment_methods"][payment_id]
            if user_payment_method["source"] in {"gift_card", "certificate"}:
                if user_payment_method["amount"] < amount:
                    raise ValueError(f"Not enough balance in payment method {payment_id}")

        total_payment = sum(payment["amount"] for payment in payment_methods)
        if total_payment != total_price:
            raise ValueError(
                f"Payment amount does not add up, total price is {total_price}, but paid {total_payment}"
            )

        for payment_method in payment_methods:
            payment_id = payment_method["payment_id"]
            amount = payment_method["amount"]
            user_payment_method = user["payment_methods"][payment_id]
            if user_payment_method["source"] == "gift_card":
                user_payment_method["amount"] -= amount
            elif user_payment_method["source"] == "certificate":
                user["payment_methods"].pop(payment_id)

        for flight_date_data in all_flights_date_data:
            flight_date_data["available_seats"][cabin] -= len(passengers)
        self.db["reservations"][reservation_id] = reservation
        self.db["users"][user_id]["reservations"].append(reservation_id)
        return deepcopy(reservation)

    def calculate(self, expression: str) -> str:
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    def cancel_reservation(self, reservation_id: str) -> Dict[str, Any]:
        reservation = self._get_reservation(reservation_id)
        refunds = []
        for payment in reservation["payment_history"]:
            refunds.append({"payment_id": payment["payment_id"], "amount": -payment["amount"]})
        reservation["payment_history"].extend(refunds)
        reservation["status"] = "cancelled"
        return deepcopy(reservation)

    def get_reservation_details(self, reservation_id: str) -> Dict[str, Any]:
        return deepcopy(self._get_reservation(reservation_id))

    def get_user_details(self, user_id: str) -> Dict[str, Any]:
        return deepcopy(self._get_user(user_id))

    def list_all_airports(self) -> List[Dict[str, Any]]:
        return deepcopy(AIRPORTS)

    def lookup_reservations(
        self,
        user_id: Optional[str] = None,
        flight_number: Optional[str] = None,
        date: Optional[str] = None,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        trip_context: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Find reservations from natural trip filters without changing state.

        Args:
            user_id: Optional user identifier to scope the lookup.
            flight_number: Optional flight number that appears in the reservation.
            date: Optional flight date in YYYY-MM-DD format.
            origin: Optional origin airport IATA code for the reservation or a flight leg.
            destination: Optional destination airport IATA code for the reservation or a flight leg.
            trip_context: Optional text such as a route, city name, user name, email, flight, or date.
            limit: Maximum number of reservation summaries to return.
        """
        matches = []
        normalized_trip_context = trip_context.lower() if trip_context else None
        normalized_origin = origin.upper() if origin else None
        normalized_destination = destination.upper() if destination else None
        for reservation in self.db["reservations"].values():
            if user_id is not None and reservation["user_id"] != user_id:
                continue
            if flight_number is not None and not any(
                flight["flight_number"] == flight_number for flight in reservation["flights"]
            ):
                continue
            if date is not None and not any(
                flight["date"] == date for flight in reservation["flights"]
            ):
                continue
            if (
                normalized_origin is not None
                and reservation["origin"] != normalized_origin
                and not any(
                    flight["origin"] == normalized_origin for flight in reservation["flights"]
                )
            ):
                continue
            if (
                normalized_destination is not None
                and reservation["destination"] != normalized_destination
                and not any(
                    flight["destination"] == normalized_destination
                    for flight in reservation["flights"]
                )
            ):
                continue
            if normalized_trip_context is not None:
                haystack = self._reservation_search_text(reservation)
                if normalized_trip_context not in haystack:
                    continue

            matches.append(self._reservation_summary(reservation))
            if len(matches) >= limit:
                break
        return deepcopy(matches)

    def search_direct_flight(self, origin: str, destination: str, date: str) -> List[Dict[str, Any]]:
        return self._search_direct_flight(date=date, origin=origin, destination=destination)

    def search_onestop_flight(
        self, origin: str, destination: str, date: str
    ) -> List[List[Dict[str, Any]]]:
        results: List[List[Dict[str, Any]]] = []
        for result1 in self._search_direct_flight(date=date, origin=origin, destination=None):
            result1["date"] = date
            date2 = (
                f"2024-05-{int(date[-2:]) + 1}"
                if "+1" in result1["scheduled_arrival_time_est"]
                else date
            )
            for result2 in self._search_direct_flight(
                date=date2,
                origin=result1["destination"],
                destination=destination,
                leave_after=result1["scheduled_arrival_time_est"],
            ):
                result2["date"] = date2
                results.append([deepcopy(result1), deepcopy(result2)])
        return results

    def send_certificate(self, user_id: str, amount: int) -> str:
        user = self._get_user(user_id)
        for payment_id in [f"certificate_{id_}" for id_ in self._get_new_payment_ids()]:
            if payment_id not in user["payment_methods"]:
                user["payment_methods"][payment_id] = {
                    "id": payment_id,
                    "amount": amount,
                    "source": "certificate",
                }
                return f"Certificate {payment_id} added to user {user_id} with amount {amount}."
        raise ValueError("Too many certificates")

    def transfer_to_human_agents(self, summary: str) -> str:
        return "Transfer successful"

    def update_reservation_baggages(
        self,
        reservation_id: str,
        total_baggages: int,
        nonfree_baggages: int,
        payment_id: str,
    ) -> Dict[str, Any]:
        reservation = self._get_reservation(reservation_id)
        user = self._get_user(reservation["user_id"])
        total_price = 50 * max(0, nonfree_baggages - reservation["nonfree_baggages"])
        payment = self._payment_for_update(user, payment_id, total_price)
        if payment is not None:
            reservation["payment_history"].append(payment)
        reservation["total_baggages"] = total_baggages
        reservation["nonfree_baggages"] = nonfree_baggages
        return deepcopy(reservation)

    def update_reservation_flights(
        self,
        reservation_id: str,
        cabin: str,
        flights: List[Dict[str, Any]],
        payment_id: str,
    ) -> Dict[str, Any]:
        reservation = self._get_reservation(reservation_id)
        user = self._get_user(reservation["user_id"])

        total_price = 0
        reservation_flights: List[Dict[str, Any]] = []
        for flight_info in flights:
            matching_reservation_flight = next(
                (
                    reservation_flight
                    for reservation_flight in reservation["flights"]
                    if reservation_flight["flight_number"] == flight_info["flight_number"]
                    and reservation_flight["date"] == flight_info["date"]
                    and cabin == reservation["cabin"]
                ),
                None,
            )
            if matching_reservation_flight:
                total_price += matching_reservation_flight["price"] * len(reservation["passengers"])
                reservation_flights.append(deepcopy(matching_reservation_flight))
                continue

            flight = self._get_flight(flight_info["flight_number"])
            flight_date_data = self._get_flight_instance(
                flight_number=flight_info["flight_number"],
                date=flight_info["date"],
            )
            if flight_date_data["status"] != "available":
                raise ValueError(
                    f"Flight {flight_info['flight_number']} not available on date {flight_info['date']}"
                )
            if flight_date_data["available_seats"][cabin] < len(reservation["passengers"]):
                raise ValueError(f"Not enough seats on flight {flight_info['flight_number']}")
            reservation_flight = {
                "flight_number": flight_info["flight_number"],
                "date": flight_info["date"],
                "price": flight_date_data["prices"][cabin],
                "origin": flight["origin"],
                "destination": flight["destination"],
            }
            total_price += reservation_flight["price"] * len(reservation["passengers"])
            reservation_flights.append(reservation_flight)

        total_price -= sum(flight["price"] for flight in reservation["flights"]) * len(
            reservation["passengers"]
        )
        payment = self._payment_for_update(user, payment_id, total_price)
        if payment is not None:
            reservation["payment_history"].append(payment)
        reservation["flights"] = reservation_flights
        reservation["cabin"] = cabin
        return deepcopy(reservation)

    def update_reservation_passengers(
        self,
        reservation_id: str,
        passengers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        reservation = self._get_reservation(reservation_id)
        if len(passengers) != len(reservation["passengers"]):
            raise ValueError("Number of passengers does not match")
        reservation["passengers"] = deepcopy(passengers)
        return deepcopy(reservation)

    def get_flight_status(self, flight_number: str, date: str) -> str:
        return self._get_flight_instance(flight_number, date)["status"]


def load_airline_toolkit(db_path: str | Path) -> TauAirlineToolkit:
    return TauAirlineToolkit.from_db_path(db_path)
