"""
ToolbenchEcommerceToolkit - Mock ecommerce domain toolkit for SOP workbench.

Provides product search, comparison, cart management, checkout, and return
capabilities for testing brand preference, budget constraints, delivery
preferences, and shopping habits.
"""

from typing import Optional
import copy


def load_default_ecommerce_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchEcommerceToolkit()


class ToolbenchEcommerceToolkit:
    """
    Mock ecommerce toolkit supporting:
    - Product search with category, price, brand, tags filters
    - Product detail lookup
    - Offer comparison across sellers
    - Cart creation and item management
    - Checkout with shipping/budget preferences
    - Order lookup
    - Return request management
    """

    def __init__(
        self,
        products: Optional[dict] = None,
        offers: Optional[dict] = None,
        carts: Optional[dict] = None,
        orders: Optional[dict] = None,
        returns: Optional[dict] = None,
    ):
        self._products = copy.deepcopy(products) if products is not None else self._build_product_fixture()
        self._offers = copy.deepcopy(offers) if offers is not None else self._build_offer_fixture()
        self._carts = copy.deepcopy(carts) if carts is not None else {}
        self._orders = copy.deepcopy(orders) if orders is not None else self._build_order_fixture()
        self._returns = copy.deepcopy(returns) if returns is not None else {}

    def _build_product_fixture(self):
        """Build 14 products covering required test scenarios."""
        return {
            "prod_001": {
                "id": "prod_001",
                "title": "Wireless Bluetooth Headphones",
                "brand": "SoundMax",
                "category": "Electronics",
                "base_price": 79.99,
                "rating": 4.5,
                "tags": ["wireless", "bluetooth", "noise-canceling", "compact"],
                "return_window_days": 30,
                "delivery_days": 3,
                "description": "Compact wireless headphones with 20-hour battery. Good for daily commute.",
            },
            "prod_002": {
                "id": "prod_002",
                "title": "Premium Noise-Canceling Headphones",
                "brand": "QuietPro",
                "category": "Electronics",
                "base_price": 299.99,
                "rating": 4.8,
                "tags": ["premium", "noise-canceling", "over-ear", "travel"],
                "return_window_days": 14,
                "delivery_days": 2,
                "description": "Premium over-ear headphones with active noise cancellation. Ideal for travel.",
            },
            "prod_003": {
                "id": "prod_003",
                "title": "Budget Wired Earbuds",
                "brand": "ValueAudio",
                "category": "Electronics",
                "base_price": 12.99,
                "rating": 3.8,
                "tags": ["budget", "wired", "compact", "student"],
                "return_window_days": 7,
                "delivery_days": 5,
                "description": "Affordable wired earbuds for everyday use. Not wireless.",
            },
            "prod_004": {
                "id": "prod_004",
                "title": "Smart Home Speaker",
                "brand": "HomeAssist",
                "category": "Smart Home",
                "base_price": 129.99,
                "rating": 4.2,
                "tags": ["smart-home", "voice-control", "speaker", "assistant"],
                "return_window_days": 30,
                "delivery_days": 4,
                "description": "Voice-controlled smart speaker. Plays music and answers questions.",
            },
            "prod_005": {
                "id": "prod_005",
                "title": "Compact Air Purifier",
                "brand": "FreshAir",
                "category": "Home",
                "base_price": 89.99,
                "rating": 4.6,
                "tags": ["health", "compact", "quiet", "apartment-friendly"],
                "return_window_days": 45,
                "delivery_days": 3,
                "description": "Compact air purifier for small rooms. Whisper-quiet operation.",
            },
            "prod_006": {
                "id": "prod_006",
                "title": "Large Standing Air Purifier",
                "brand": "AirPure",
                "category": "Home",
                "base_price": 249.99,
                "rating": 4.7,
                "tags": ["health", "large", "powerful"],
                "return_window_days": 30,
                "delivery_days": 5,
                "description": "Large capacity air purifier for whole house. Not suitable for small apartments.",
            },
            "prod_007": {
                "id": "prod_007",
                "title": "Stainless Steel Coffee Maker",
                "brand": "KitchenMaster",
                "category": "Kitchen",
                "base_price": 59.99,
                "rating": 4.3,
                "tags": ["kitchen", "coffee", "drip", "easy-clean"],
                "return_window_days": 30,
                "delivery_days": 4,
                "description": "12-cup drip coffee maker. Easy to clean and maintain.",
            },
            "prod_008": {
                "id": "prod_008",
                "title": "Premium Espresso Machine",
                "brand": "CaffePro",
                "category": "Kitchen",
                "base_price": 449.99,
                "rating": 4.9,
                "tags": ["premium", "kitchen", "coffee", "espresso", "barista"],
                "return_window_days": 14,
                "delivery_days": 2,
                "description": "Professional-grade espresso machine. Requires maintenance.",
            },
            "prod_009": {
                "id": "prod_009",
                "title": "Portable Hand Blender",
                "brand": "MixEasy",
                "category": "Kitchen",
                "base_price": 34.99,
                "rating": 4.1,
                "tags": ["compact", "kitchen", "portable", "apartment-friendly"],
                "return_window_days": 21,
                "delivery_days": 3,
                "description": "Hand blender for quick blending tasks. Compact and easy to store.",
            },
            "prod_010": {
                "id": "prod_010",
                "title": "Elder Care Digital Thermometer",
                "brand": "HealthFirst",
                "category": "Health",
                "base_price": 19.99,
                "rating": 4.7,
                "tags": ["health", "elder-care", "easy-read", "family"],
                "return_window_days": 60,
                "delivery_days": 2,
                "description": "Large-display digital thermometer. Easy to read for seniors.",
            },
            "prod_011": {
                "id": "prod_011",
                "title": "Blood Pressure Monitor",
                "brand": "HealthFirst",
                "category": "Health",
                "base_price": 45.99,
                "rating": 4.8,
                "tags": ["health", "elder-care", "easy-use", "family"],
                "return_window_days": 60,
                "delivery_days": 2,
                "description": "Automatic blood pressure monitor with voice readout. Elder-friendly.",
            },
            "prod_012": {
                "id": "prod_012",
                "title": "Gaming Console Controller",
                "brand": "GamePro",
                "category": "Gaming",
                "base_price": 69.99,
                "rating": 4.4,
                "tags": ["gaming", "wireless", "ergonomic"],
                "return_window_days": 21,
                "delivery_days": 3,
                "description": "Wireless gaming controller. Ergonomic design for long sessions.",
            },
            "prod_013": {
                "id": "prod_013",
                "title": "Budget Mechanical Keyboard",
                "brand": "TypeTech",
                "category": "Electronics",
                "base_price": 49.99,
                "rating": 4.0,
                "tags": ["budget", "mechanical", "clicky", "loud"],
                "return_window_days": 14,
                "delivery_days": 4,
                "description": "Mechanical keyboard with clicky switches. Loud typing sound.",
            },
            "prod_014": {
                "id": "prod_014",
                "title": "Silent Mechanical Keyboard",
                "brand": "QuietType",
                "category": "Electronics",
                "base_price": 89.99,
                "rating": 4.5,
                "tags": ["mechanical", "silent", "quiet", "office-friendly"],
                "return_window_days": 30,
                "delivery_days": 3,
                "description": "Mechanical keyboard with silent switches. Ideal for quiet environments.",
            },
        }

    def _build_offer_fixture(self):
        """Build offers from 2-3 sellers for several products."""
        return {
            "prod_001": [
                {"seller": "OfficialStore", "price": 79.99, "condition": "New", "shipping_days": 3, "return_policy": "30-day full refund"},
                {"seller": "QuickShip", "price": 75.99, "condition": "New", "shipping_days": 1, "return_policy": "14-day return"},
                {"seller": "ValueDeal", "price": 59.99, "condition": "Used-Good", "shipping_days": 5, "return_policy": "7-day return, used items"},
            ],
            "prod_002": [
                {"seller": "OfficialStore", "price": 299.99, "condition": "New", "shipping_days": 2, "return_policy": "14-day full refund"},
                {"seller": "PremiumDeals", "price": 289.99, "condition": "New", "shipping_days": 3, "return_policy": "30-day return"},
            ],
            "prod_003": [
                {"seller": "BudgetBuy", "price": 12.99, "condition": "New", "shipping_days": 5, "return_policy": "7-day return"},
                {"seller": "ValueDeal", "price": 8.99, "condition": "Used-Good", "shipping_days": 7, "return_policy": "No returns on used items"},
            ],
            "prod_005": [
                {"seller": "OfficialStore", "price": 89.99, "condition": "New", "shipping_days": 3, "return_policy": "45-day full refund"},
                {"seller": "QuickShip", "price": 84.99, "condition": "New", "shipping_days": 1, "return_policy": "30-day return"},
            ],
            "prod_010": [
                {"seller": "OfficialStore", "price": 19.99, "condition": "New", "shipping_days": 2, "return_policy": "60-day return, health products"},
                {"seller": "HealthSupply", "price": 17.99, "condition": "New", "shipping_days": 3, "return_policy": "30-day return"},
            ],
            "prod_011": [
                {"seller": "OfficialStore", "price": 45.99, "condition": "New", "shipping_days": 2, "return_policy": "60-day return, health products"},
                {"seller": "HealthSupply", "price": 42.99, "condition": "New", "shipping_days": 3, "return_policy": "30-day return"},
            ],
            "prod_013": [
                {"seller": "OfficialStore", "price": 49.99, "condition": "New", "shipping_days": 4, "return_policy": "14-day return"},
                {"seller": "ValueDeal", "price": 35.99, "condition": "Used-Good", "shipping_days": 6, "return_policy": "No returns on used items"},
            ],
            "prod_014": [
                {"seller": "OfficialStore", "price": 89.99, "condition": "New", "shipping_days": 3, "return_policy": "30-day full refund"},
                {"seller": "QuickShip", "price": 85.99, "condition": "New", "shipping_days": 1, "return_policy": "14-day return"},
            ],
        }

    def _build_order_fixture(self):
        """Build initial orders for return scenarios."""
        return {
            "order_001": {
                "id": "order_001",
                "cart_id": "cart_001",
                "items": [
                    {"product_id": "prod_003", "quantity": 2, "seller": "BudgetBuy", "price": 12.99},
                ],
                "shipping_preference": "standard",
                "total": 25.98,
                "order_date": "2026-05-15",
                "delivery_date": "2026-05-20",
                "status": "delivered",
                "budget_note": "",
            },
            "order_002": {
                "id": "order_002",
                "cart_id": "cart_002",
                "items": [
                    {"product_id": "prod_001", "quantity": 1, "seller": "ValueDeal", "price": 59.99},
                ],
                "shipping_preference": "standard",
                "total": 59.99,
                "order_date": "2026-05-25",
                "delivery_date": "2026-05-30",
                "status": "delivered",
                "budget_note": "Budget option - used item",
            },
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "search_products",
            "get_product",
            "compare_offers",
            "create_cart",
            "add_to_cart",
            "checkout_cart",
            "get_order",
            "request_return",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "search_products": self._search_products,
            "get_product": self._get_product,
            "compare_offers": self._compare_offers,
            "create_cart": self._create_cart,
            "add_to_cart": self._add_to_cart,
            "checkout_cart": self._checkout_cart,
            "get_order": self._get_order,
            "request_return": self._request_return,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _search_products(
        self,
        query: str = "",
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        brand: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search products by query and filters."""
        results = []
        query_lower = query.lower() if query else ""
        for product in self._products.values():
            # Filter by category
            if category and product.get("category") != category:
                continue
            # Filter by brand
            if brand and product.get("brand") != brand:
                continue
            # Filter by max price
            if max_price and product.get("base_price", 999) > max_price:
                continue
            # Filter by tags (must have ALL specified tags)
            if tags:
                product_tags = product.get("tags", [])
                if not all(tag in product_tags for tag in tags):
                    continue
            # Filter by query (search in title, brand, description, tags)
            if query_lower:
                searchable = (
                    product.get("title", "").lower() + " " +
                    product.get("brand", "").lower() + " " +
                    product.get("description", "").lower() + " " +
                    " ".join(product.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            # Return subset of fields for search results
            results.append({
                "id": product["id"],
                "title": product["title"],
                "brand": product["brand"],
                "category": product["category"],
                "base_price": product["base_price"],
                "rating": product["rating"],
                "tags": product.get("tags", []),
                "delivery_days": product["delivery_days"],
                "return_window_days": product["return_window_days"],
            })
        return results

    def _get_product(self, product_id: str) -> Optional[dict]:
        """Get full product details by ID."""
        product = self._products.get(product_id)
        if product:
            # Return full product info
            return copy.deepcopy(product)
        return None

    def _compare_offers(self, product_id: str) -> Optional[list[dict]]:
        """Get all offers for a product."""
        offers = self._offers.get(product_id)
        if offers:
            # Add product base price as reference
            product = self._products.get(product_id)
            result = copy.deepcopy(offers)
            if product:
                for offer in result:
                    offer["base_price_reference"] = product["base_price"]
            return result
        return None

    def _create_cart(self, name: str = "default") -> dict:
        """Create a new cart."""
        cart_id = f"cart_{len(self._carts) + 1}"
        self._carts[cart_id] = {
            "name": name,
            "items": [],
        }
        return {"cart_id": cart_id, "name": name, "created": True}

    def _add_to_cart(
        self,
        cart_id: str,
        product_id: str,
        quantity: int = 1,
        preferred_seller: Optional[str] = None,
    ) -> dict:
        """Add a product to cart."""
        if cart_id not in self._carts:
            return {"success": False, "error": f"Cart {cart_id} not found"}
        if product_id not in self._products:
            return {"success": False, "error": f"Product {product_id} not found"}
        if quantity < 1:
            return {"success": False, "error": "Quantity must be at least 1"}

        # Find best offer if no preferred seller specified
        best_offer = None
        offers = self._offers.get(product_id, [])
        if preferred_seller:
            for offer in offers:
                if offer["seller"] == preferred_seller:
                    best_offer = offer
                    break
        elif offers:
            # Default to lowest price new item
            new_offers = [o for o in offers if o["condition"] == "New"]
            if new_offers:
                best_offer = min(new_offers, key=lambda o: o["price"])
            else:
                best_offer = min(offers, key=lambda o: o["price"])

        # Use base price if no offers
        price = best_offer["price"] if best_offer else self._products[product_id]["base_price"]
        seller = best_offer["seller"] if best_offer else "DefaultSeller"

        cart = self._carts[cart_id]
        cart["items"].append({
            "product_id": product_id,
            "quantity": quantity,
            "preferred_seller": preferred_seller,
            "selected_seller": seller,
            "price": price,
        })
        return {
            "success": True,
            "cart_id": cart_id,
            "product_id": product_id,
            "quantity": quantity,
            "selected_seller": seller,
            "price": price,
        }

    def _checkout_cart(
        self,
        cart_id: str,
        shipping_preference: str = "standard",
        budget_note: str = "",
    ) -> dict:
        """Checkout cart and create order."""
        if cart_id not in self._carts:
            return {"success": False, "error": f"Cart {cart_id} not found"}
        cart = self._carts[cart_id]
        if not cart["items"]:
            return {"success": False, "error": "Cart is empty"}

        # Calculate total
        total = sum(item["price"] * item["quantity"] for item in cart["items"])

        # Create order
        order_id = f"order_{len(self._orders) + 1}"
        order = {
            "id": order_id,
            "cart_id": cart_id,
            "items": copy.deepcopy(cart["items"]),
            "shipping_preference": shipping_preference,
            "total": total,
            "order_date": "2026-05-31",
            "delivery_date": "2026-06-04",  # Estimated
            "status": "pending",
            "budget_note": budget_note,
        }
        self._orders[order_id] = order

        # Clear cart items
        cart["items"] = []

        return {
            "success": True,
            "order_id": order_id,
            "total": total,
            "shipping_preference": shipping_preference,
            "status": "pending",
        }

    def _get_order(self, order_id: str) -> Optional[dict]:
        """Get order details."""
        order = self._orders.get(order_id)
        if order:
            return copy.deepcopy(order)
        return None

    def _request_return(self, order_id: str, product_id: str, reason: str) -> dict:
        """Request return for a product from an order."""
        if order_id not in self._orders:
            return {"success": False, "error": f"Order {order_id} not found"}
        order = self._orders[order_id]

        # Check product is in order
        product_in_order = False
        for item in order["items"]:
            if item["product_id"] == product_id:
                product_in_order = True
                break
        if not product_in_order:
            return {"success": False, "error": f"Product {product_id} not in order"}

        # Check return window
        product = self._products.get(product_id)
        if product:
            return_window = product.get("return_window_days", 0)
            # Simplified: assume within window for fixture orders
            # In real system, would check delivery_date

        # Create return request
        return_id = f"return_{len(self._returns) + 1}"
        self._returns[return_id] = {
            "return_id": return_id,
            "order_id": order_id,
            "product_id": product_id,
            "reason": reason,
            "status": "requested",
            "requested_date": "2026-05-31",
        }

        return {
            "success": True,
            "return_id": return_id,
            "order_id": order_id,
            "product_id": product_id,
            "reason": reason,
            "status": "requested",
        }

    def dump_state(self) -> dict:
        """Dump current toolkit state including carts, orders, and returns."""
        return {
            "product_count": len(self._products),
            "offer_count": len(self._offers),
            "carts": copy.deepcopy(self._carts),
            "orders": copy.deepcopy(self._orders),
            "returns": copy.deepcopy(self._returns),
        }

    def clone(self):
        """Create a fresh toolkit instance (default state, no carts/orders/returns created)."""
        return ToolbenchEcommerceToolkit()

    # Public method wrappers (for invoke_tool compatibility)
    def search_products(
        self,
        query: str = "",
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        brand: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict]:
        return self._search_products(query, category, max_price, brand, tags)

    def get_product(self, product_id: str) -> Optional[dict]:
        return self._get_product(product_id)

    def compare_offers(self, product_id: str) -> Optional[list[dict]]:
        return self._compare_offers(product_id)

    def create_cart(self, name: str = "default") -> dict:
        return self._create_cart(name)

    def add_to_cart(
        self,
        cart_id: str,
        product_id: str,
        quantity: int = 1,
        preferred_seller: Optional[str] = None,
    ) -> dict:
        return self._add_to_cart(cart_id, product_id, quantity, preferred_seller)

    def checkout_cart(
        self,
        cart_id: str,
        shipping_preference: str = "standard",
        budget_note: str = "",
    ) -> dict:
        return self._checkout_cart(cart_id, shipping_preference, budget_note)

    def get_order(self, order_id: str) -> Optional[dict]:
        return self._get_order(order_id)

    def request_return(self, order_id: str, product_id: str, reason: str) -> dict:
        return self._request_return(order_id, product_id, reason)
