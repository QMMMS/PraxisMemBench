from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Union


# BFCL DEFAULT_STATE
DEFAULT_STATE = {
    "ticket_queue": [],
    "ticket_counter": 1,
    "current_user": None,
}


class BFCLTicketToolkit:
    """Standardized wrapper for BFCL TicketAPI tools.

    Faithfully reproduces BFCL ticket_api.py behavior including:
    - Ticket creation with priority levels
    - Ticket lifecycle: open, close, resolve
    - Ticket editing and retrieval
    - User authentication
    """

    def __init__(
        self,
        ticket_queue: Optional[List[Dict[str, Any]]] = None,
        ticket_counter: int = 1,
        current_user: Optional[str] = None,
    ) -> None:
        """Initialize ticket toolkit with optional state.

        Args:
            ticket_counter: BFCL explicit counter. New ticket uses current counter,
                           then counter increments. Default is 1 (BFCL DEFAULT_STATE).
        """
        self.ticket_queue: List[Dict[str, Any]] = ticket_queue if ticket_queue is not None else []
        self.ticket_counter: int = ticket_counter
        self.current_user: Optional[str] = current_user

    def clone(self) -> "BFCLTicketToolkit":
        """Return toolkit reset to default BFCL state."""
        return BFCLTicketToolkit()

    def dump_state(self) -> Dict[str, Any]:
        """Export current state in BFCL format."""
        return {
            "ticket_queue": deepcopy(self.ticket_queue),
            "ticket_counter": self.ticket_counter,
            "current_user": self.current_user,
        }

    def list_tools(self) -> List[str]:
        """Return available tool names."""
        return [
            "create_ticket",
            "get_ticket",
            "close_ticket",
            "resolve_ticket",
            "edit_ticket",
            "ticket_login",
            "ticket_get_login_status",
            "logout",
            "get_user_tickets",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke tool by name."""
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown ticket tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def _find_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Find ticket by ID.

        Args:
            ticket_id: Ticket ID.

        Returns:
            Ticket dict or None.
        """
        for ticket in self.ticket_queue:
            if ticket["id"] == ticket_id:
                return ticket
        return None

    # === Authentication ===

    def ticket_login(self, username: str, password: str) -> Dict[str, bool]:
        """Login to ticket system.

        Args:
            username: Username.
            password: Password.

        Returns:
            success.
        """
        if username and password:
            self.current_user = username
            return {"success": True}
        return {"success": False}

    def ticket_get_login_status(self) -> Dict[str, bool]:
        """Get login status.

        Returns:
            login_status.
        """
        return {"login_status": bool(self.current_user)}

    def logout(self) -> Dict[str, bool]:
        """Logout.

        Returns:
            success.
        """
        if self.current_user:
            self.current_user = None
            return {"success": True}
        return {"success": False}

    # === Tickets ===

    def create_ticket(
        self, title: str, description: str = "", priority: int = 1
    ) -> Dict[str, Union[int, str]]:
        """Create a ticket.

        Args:
            title: Ticket title.
            description: Ticket description.
            priority: Priority level (1-5, 5 is highest).

        Returns:
            id, title, description, status, priority.
        """
        if not self.current_user:
            return {"error": "User not authenticated. Please log in to create a ticket."}
        if priority < 1 or priority > 5:
            return {"error": "Invalid priority. Priority must be between 1 and 5."}

        # BFCL semantics: use current ticket_counter as id, then increment
        ticket_id = self.ticket_counter
        self.ticket_counter += 1

        ticket = {
            "id": ticket_id,
            "title": title,
            "description": description,
            "status": "Open",
            "priority": priority,
            "created_by": self.current_user,
        }
        self.ticket_queue.append(ticket)
        return ticket

    def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Get a ticket by ID.

        Args:
            ticket_id: Ticket ID.

        Returns:
            Ticket details.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}
        return deepcopy(ticket)

    def close_ticket(self, ticket_id: int) -> Dict[str, str]:
        """Close a ticket.

        Args:
            ticket_id: Ticket ID.

        Returns:
            status.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}
        if ticket["status"] == "Closed":
            return {"error": f"Ticket with ID {ticket_id} is already closed."}
        ticket["status"] = "Closed"
        return {"status": f"Ticket {ticket_id} has been closed successfully."}

    def resolve_ticket(self, ticket_id: int, resolution: str) -> Dict[str, str]:
        """Resolve a ticket.

        Args:
            ticket_id: Ticket ID.
            resolution: Resolution details.

        Returns:
            status.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}
        if ticket["status"] == "Resolved":
            return {"error": f"Ticket with ID {ticket_id} is already resolved."}
        ticket["status"] = "Resolved"
        ticket["resolution"] = resolution
        return {"status": f"Ticket {ticket_id} has been resolved successfully."}

    def edit_ticket(
        self, ticket_id: int, updates: Dict[str, Optional[Union[str, int]]]
    ) -> Dict[str, str]:
        """Edit a ticket.

        Args:
            ticket_id: Ticket ID.
            updates: Dict with fields to update (title, description, status, priority).

        Returns:
            status.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}

        valid_fields = {"title", "description", "status", "priority"}
        invalid_fields = set(updates.keys()) - valid_fields
        if invalid_fields:
            return {"error": f"Invalid fields for update: {', '.join(invalid_fields)}"}

        for key, value in updates.items():
            if value is not None:
                ticket[key] = value

        return {"status": f"Ticket {ticket_id} has been updated successfully."}

    def get_user_tickets(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all tickets for current user.

        Args:
            status: Optional status filter.

        Returns:
            List of tickets, or list with error dict.
        """
        if not self.current_user:
            return [{"error": "User not authenticated. Please log in to view tickets."}]

        user_tickets = [
            deepcopy(ticket) for ticket in self.ticket_queue
            if ticket["created_by"] == self.current_user
        ]

        if status:
            user_tickets = [
                ticket for ticket in user_tickets
                if ticket["status"].lower() == status.lower()
            ]

        return user_tickets


def load_default_ticket_toolkit() -> BFCLTicketToolkit:
    """Load toolkit with default BFCL state."""
    return BFCLTicketToolkit()