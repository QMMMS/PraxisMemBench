"""
ToolbenchFoodToolkit - Mock food domain toolkit for SOP workbench.

Provides recipe search, restaurant search, nutrition info, and meal planning
capabilities for testing dietary preferences, budget constraints, and time limits.
"""

from typing import Optional
import copy


def load_default_food_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchFoodToolkit()


class ToolbenchFoodToolkit:
    """
    Mock food toolkit supporting:
    - Recipe search with cuisine, diet, prep time, cost filters
    - Restaurant search with neighborhood, cuisine, price filters
    - Restaurant menu lookup
    - Nutrition information lookup
    - Meal plan state management
    """

    def __init__(
        self,
        recipes: Optional[dict] = None,
        restaurants: Optional[dict] = None,
        restaurant_menus: Optional[dict] = None,
        nutrition_data: Optional[dict] = None,
        meal_plans: Optional[dict] = None,
    ):
        self._recipes = copy.deepcopy(recipes) if recipes is not None else self._build_recipe_fixture()
        self._restaurants = copy.deepcopy(restaurants) if restaurants is not None else self._build_restaurant_fixture()
        self._restaurant_menus = (
            copy.deepcopy(restaurant_menus) if restaurant_menus is not None else self._build_menu_fixture()
        )
        self._nutrition_data = (
            copy.deepcopy(nutrition_data) if nutrition_data is not None else self._build_nutrition_fixture()
        )
        self._meal_plans = copy.deepcopy(meal_plans) if meal_plans is not None else {}

    def _build_recipe_fixture(self):
        """Build 12 recipes covering required test scenarios."""
        return {
            "recipe_001": {
                "id": "recipe_001",
                "name": "Vegetable Stir Fry",
                "cuisine": "Chinese",
                "diet_tags": ["vegetarian", "dairy-free", "low-sodium"],
                "prep_minutes": 15,
                "cost_per_serving": 4.50,
                "ingredients": ["broccoli", "bell peppers", "carrots", "soy sauce", "garlic", "ginger"],
                "nutrition_summary": {"calories": 180, "protein": 6, "fat": 5, "carbs": 28},
                "tags": ["quick", "healthy", "budget-friendly", "weeknight"],
                "instructions": "1. Heat oil in pan. 2. Add garlic and ginger. 3. Add vegetables. 4. Stir fry 5 min. 5. Add soy sauce.",
            },
            "recipe_002": {
                "id": "recipe_002",
                "name": "Grilled Chicken Salad",
                "cuisine": "American",
                "diet_tags": ["high-protein", "low-carb"],
                "prep_minutes": 20,
                "cost_per_serving": 6.00,
                "ingredients": ["chicken breast", "mixed greens", "tomatoes", "olive oil", "lemon"],
                "nutrition_summary": {"calories": 320, "protein": 35, "fat": 12, "carbs": 8},
                "tags": ["healthy", "high-protein", "quick"],
                "instructions": "1. Grill chicken 8 min each side. 2. Chop vegetables. 3. Slice chicken. 4. Toss with dressing.",
            },
            "recipe_003": {
                "id": "recipe_003",
                "name": "Pasta Primavera",
                "cuisine": "Italian",
                "diet_tags": ["vegetarian"],
                "prep_minutes": 25,
                "cost_per_serving": 5.00,
                "ingredients": ["pasta", "zucchini", "tomatoes", "basil", "parmesan", "olive oil"],
                "nutrition_summary": {"calories": 380, "protein": 12, "fat": 10, "carbs": 58},
                "tags": ["classic", "vegetarian", "family-friendly"],
                "instructions": "1. Boil pasta. 2. Saute vegetables. 3. Combine pasta and vegetables. 4. Add parmesan.",
            },
            "recipe_004": {
                "id": "recipe_004",
                "name": "Spicy Thai Curry",
                "cuisine": "Thai",
                "diet_tags": ["dairy-free", "gluten-free"],
                "prep_minutes": 30,
                "cost_per_serving": 7.00,
                "ingredients": ["coconut milk", "curry paste", "chicken", "bamboo shoots", "basil"],
                "nutrition_summary": {"calories": 450, "protein": 28, "fat": 22, "carbs": 15},
                "tags": ["spicy", "flavorful", "authentic"],
                "instructions": "1. Heat curry paste in pan. 2. Add coconut milk. 3. Add chicken and simmer. 4. Add bamboo shoots. 5. Garnish with basil.",
            },
            "recipe_005": {
                "id": "recipe_005",
                "name": "Quinoa Buddha Bowl",
                "cuisine": "Modern",
                "diet_tags": ["vegetarian", "dairy-free", "gluten-free", "high-protein"],
                "prep_minutes": 20,
                "cost_per_serving": 5.50,
                "ingredients": ["quinoa", "roasted chickpeas", "avocado", "greens", " tahini dressing"],
                "nutrition_summary": {"calories": 420, "protein": 18, "fat": 15, "carbs": 52},
                "tags": ["healthy", "plant-based", "trendy"],
                "instructions": "1. Cook quinoa. 2. Roast chickpeas. 3. Assemble bowl with greens, quinoa, chickpeas, avocado. 4. Drizzle tahini.",
            },
            "recipe_006": {
                "id": "recipe_006",
                "name": "Beef Tacos",
                "cuisine": "Mexican",
                "diet_tags": [],
                "prep_minutes": 20,
                "cost_per_serving": 4.00,
                "ingredients": ["ground beef", "taco shells", "lettuce", "tomatoes", "cheese", "salsa"],
                "nutrition_summary": {"calories": 350, "protein": 22, "fat": 18, "carbs": 28},
                "tags": ["quick", "family-friendly", "budget-friendly", "weeknight"],
                "instructions": "1. Brown beef. 2. Warm taco shells. 3. Fill shells with beef and toppings. 4. Serve with salsa.",
            },
            "recipe_007": {
                "id": "recipe_007",
                "name": "Miso Soup",
                "cuisine": "Japanese",
                "diet_tags": ["vegetarian", "dairy-free", "low-sodium", "gluten-free"],
                "prep_minutes": 10,
                "cost_per_serving": 3.00,
                "ingredients": ["miso paste", "dashi", "tofu", "green onions", "wakame seaweed"],
                "nutrition_summary": {"calories": 60, "protein": 6, "fat": 2, "carbs": 5},
                "tags": ["quick", "light", "healthy", "low-calorie"],
                "instructions": "1. Heat dashi. 2. Dissolve miso. 3. Add tofu and wakame. 4. Garnish with green onions.",
            },
            "recipe_008": {
                "id": "recipe_008",
                "name": "BBQ Pulled Pork",
                "cuisine": "American",
                "diet_tags": [],
                "prep_minutes": 240,  # slow cook
                "cost_per_serving": 8.00,
                "ingredients": ["pork shoulder", "bbq sauce", "brown sugar", "onion", "garlic"],
                "nutrition_summary": {"calories": 450, "protein": 32, "fat": 25, "carbs": 18},
                "tags": ["slow-cook", "weekend", "crowd-pleaser"],
                "instructions": "1. Rub pork with spices. 2. Slow cook 8 hours. 3. Shred meat. 4. Mix with BBQ sauce.",
            },
            "recipe_009": {
                "id": "recipe_009",
                "name": "Greek Salad",
                "cuisine": "Greek",
                "diet_tags": ["vegetarian", "dairy-free"],  # feta optional
                "prep_minutes": 10,
                "cost_per_serving": 4.50,
                "ingredients": ["cucumber", "tomatoes", "olives", "feta cheese", "olive oil", "oregano"],
                "nutrition_summary": {"calories": 150, "protein": 6, "fat": 12, "carbs": 8},
                "tags": ["quick", "fresh", "light", "summer"],
                "instructions": "1. Chop vegetables. 2. Add olives and feta. 3. Drizzle with olive oil and oregano.",
            },
            "recipe_010": {
                "id": "recipe_010",
                "name": "Dal Tadka",
                "cuisine": "Indian",
                "diet_tags": ["vegetarian", "dairy-free", "gluten-free", "high-protein"],
                "prep_minutes": 35,
                "cost_per_serving": 3.50,
                "ingredients": ["lentils", "tomatoes", "onion", "garlic", "cumin", "turmeric", "ghee"],
                "nutrition_summary": {"calories": 220, "protein": 14, "fat": 8, "carbs": 32},
                "tags": ["vegetarian", "budget-friendly", "protein-rich", "comfort-food"],
                "instructions": "1. Boil lentils. 2. Prepare tadka with spices in ghee. 3. Mix lentils with tadka. 4. Simmer 10 min.",
            },
            "recipe_011": {
                "id": "recipe_011",
                "name": "Salmon with Roasted Vegetables",
                "cuisine": "Mediterranean",
                "diet_tags": ["high-protein", "dairy-free", "gluten-free"],
                "prep_minutes": 30,
                "cost_per_serving": 12.00,
                "ingredients": ["salmon fillet", "asparagus", "zucchini", "lemon", "olive oil", "herbs"],
                "nutrition_summary": {"calories": 380, "protein": 35, "fat": 18, "carbs": 12},
                "tags": ["healthy", "premium", "omega-3"],
                "instructions": "1. Season salmon. 2. Roast vegetables 20 min. 3. Bake salmon 15 min. 4. Serve together.",
            },
            "recipe_012": {
                "id": "recipe_012",
                "name": "Veggie Wraps",
                "cuisine": "American",
                "diet_tags": ["vegetarian", "dairy-free"],
                "prep_minutes": 10,
                "cost_per_serving": 3.50,
                "ingredients": ["tortilla wrap", "hummus", "lettuce", "tomatoes", "cucumber", "bell peppers"],
                "nutrition_summary": {"calories": 200, "protein": 8, "fat": 8, "carbs": 30},
                "tags": ["quick", "portable", "light", "weeknight", "budget-friendly"],
                "instructions": "1. Spread hummus on wrap. 2. Add vegetables. 3. Roll tightly. 4. Slice if desired.",
            },
        }

    def _build_restaurant_fixture(self):
        """Build 6 restaurants covering different neighborhoods and price levels."""
        return {
            "rest_001": {
                "id": "rest_001",
                "name": "Golden Dragon",
                "neighborhood": "Downtown",
                "cuisine": "Chinese",
                "price_level": 2,
                "tags": ["vegetarian-options", "quick-service", "family-friendly"],
                "distance_minutes": 10,
            },
            "rest_002": {
                "id": "rest_002",
                "name": "Bella Italia",
                "neighborhood": "Midtown",
                "cuisine": "Italian",
                "price_level": 3,
                "tags": ["romantic", "fine-dining", "vegetarian-options"],
                "distance_minutes": 15,
            },
            "rest_003": {
                "id": "rest_003",
                "name": "Taco Fiesta",
                "neighborhood": "Eastside",
                "cuisine": "Mexican",
                "price_level": 1,
                "tags": ["budget-friendly", "quick-service", "family-friendly", "casual"],
                "distance_minutes": 8,
            },
            "rest_004": {
                "id": "rest_004",
                "name": "Sakura Sushi",
                "neighborhood": "Downtown",
                "cuisine": "Japanese",
                "price_level": 4,
                "tags": ["premium", "authentic", "quiet"],
                "distance_minutes": 12,
            },
            "rest_005": {
                "id": "rest_005",
                "name": "The Healthy Kitchen",
                "neighborhood": "Westside",
                "cuisine": "Modern",
                "price_level": 2,
                "tags": ["vegetarian-friendly", "healthy", "salads", "gluten-free-options"],
                "distance_minutes": 20,
            },
            "rest_006": {
                "id": "rest_006",
                "name": "Spice Garden",
                "neighborhood": "Midtown",
                "cuisine": "Indian",
                "price_level": 2,
                "tags": ["vegetarian-options", "spicy", "authentic", "curry"],
                "distance_minutes": 18,
            },
        }

    def _build_menu_fixture(self):
        """Build menus for each restaurant."""
        return {
            "rest_001": [
                {"name": "Vegetable Lo Mein", "price": 8.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 380, "protein": 12}},
                {"name": "Kung Pao Chicken", "price": 10.99, "diet_tags": [], "nutrition_summary": {"calories": 450, "protein": 28}},
                {"name": "Tofu Stir Fry", "price": 9.99, "diet_tags": ["vegetarian", "dairy-free"], "nutrition_summary": {"calories": 220, "protein": 15}},
                {"name": "Spring Rolls", "price": 5.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 150, "protein": 4}},
            ],
            "rest_002": [
                {"name": "Margherita Pizza", "price": 14.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 600, "protein": 18}},
                {"name": "Pasta Carbonara", "price": 16.99, "diet_tags": [], "nutrition_summary": {"calories": 550, "protein": 22}},
                {"name": "Caprese Salad", "price": 9.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 180, "protein": 8}},
                {"name": "Vegetable Risotto", "price": 15.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 420, "protein": 10}},
            ],
            "rest_003": [
                {"name": "Bean Burrito", "price": 5.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 350, "protein": 12}},
                {"name": "Chicken Tacos", "price": 7.99, "diet_tags": [], "nutrition_summary": {"calories": 320, "protein": 22}},
                {"name": "Veggie Quesadilla", "price": 6.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 280, "protein": 10}},
                {"name": "Nachos Supreme", "price": 8.99, "diet_tags": [], "nutrition_summary": {"calories": 480, "protein": 15}},
            ],
            "rest_004": [
                {"name": "Salmon Sashimi", "price": 18.99, "diet_tags": ["dairy-free", "gluten-free"], "nutrition_summary": {"calories": 120, "protein": 20}},
                {"name": "Vegetable Tempura", "price": 12.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 280, "protein": 6}},
                {"name": "Miso Soup", "price": 4.99, "diet_tags": ["vegetarian", "dairy-free", "low-sodium"], "nutrition_summary": {"calories": 60, "protein": 6}},
                {"name": "Tuna Roll", "price": 14.99, "diet_tags": ["dairy-free"], "nutrition_summary": {"calories": 200, "protein": 18}},
            ],
            "rest_005": [
                {"name": "Quinoa Buddha Bowl", "price": 11.99, "diet_tags": ["vegetarian", "dairy-free", "gluten-free"], "nutrition_summary": {"calories": 420, "protein": 18}},
                {"name": "Grilled Chicken Salad", "price": 12.99, "diet_tags": ["high-protein", "low-carb"], "nutrition_summary": {"calories": 320, "protein": 35}},
                {"name": "Veggie Wrap", "price": 9.99, "diet_tags": ["vegetarian", "dairy-free"], "nutrition_summary": {"calories": 200, "protein": 8}},
                {"name": "Fresh Fruit Smoothie", "price": 5.99, "diet_tags": ["vegetarian", "dairy-free"], "nutrition_summary": {"calories": 180, "protein": 3}},
            ],
            "rest_006": [
                {"name": "Dal Tadka", "price": 8.99, "diet_tags": ["vegetarian", "dairy-free", "gluten-free", "high-protein"], "nutrition_summary": {"calories": 220, "protein": 14}},
                {"name": "Chicken Curry", "price": 12.99, "diet_tags": ["dairy-free", "gluten-free"], "nutrition_summary": {"calories": 450, "protein": 28}},
                {"name": "Vegetable Biryani", "price": 10.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 380, "protein": 12}},
                {"name": "Naan Bread", "price": 2.99, "diet_tags": ["vegetarian"], "nutrition_summary": {"calories": 260, "protein": 6}},
            ],
        }

    def _build_nutrition_fixture(self):
        """Build 15 nutrition entries covering common foods."""
        return {
            "chicken breast": {"name": "Chicken Breast", "calories": 119, "protein": 21.23, "fat": 2.66, "carbs": 0, "fiber": 0},
            "salmon": {"name": "Salmon", "calories": 208, "protein": 20.42, "fat": 13.42, "carbs": 0, "fiber": 0},
            "tofu": {"name": "Tofu", "calories": 76, "protein": 8.08, "fat": 4.77, "carbs": 1.87, "fiber": 0.3},
            "lentils": {"name": "Lentils (cooked)", "calories": 116, "protein": 9.02, "fat": 0.38, "carbs": 20.13, "fiber": 7.3},
            "quinoa": {"name": "Quinoa (cooked)", "calories": 120, "protein": 4.4, "fat": 1.92, "carbs": 21.3, "fiber": 2.8},
            "broccoli": {"name": "Broccoli", "calories": 55, "protein": 3.7, "fat": 0.64, "carbs": 11.2, "fiber": 5.1},
            "pasta": {"name": "Pasta (cooked)", "calories": 131, "protein": 5.0, "fat": 1.1, "carbs": 25.0, "fiber": 1.8},
            "brown rice": {"name": "Brown Rice (cooked)", "calories": 111, "protein": 2.6, "fat": 0.9, "carbs": 23.0, "fiber": 1.8},
            "avocado": {"name": "Avocado", "calories": 160, "protein": 2.0, "fat": 14.7, "carbs": 8.5, "fiber": 6.7},
            "egg": {"name": "Egg (whole)", "calories": 143, "protein": 12.56, "fat": 9.51, "carbs": 0.72, "fiber": 0},
            "spinach": {"name": "Spinach", "calories": 23, "protein": 2.9, "fat": 0.39, "carbs": 3.63, "fiber": 2.2},
            "chickpeas": {"name": "Chickpeas (cooked)", "calories": 164, "protein": 8.86, "fat": 2.59, "carbs": 27.42, "fiber": 7.6},
            "ground beef": {"name": "Ground Beef (lean)", "calories": 176, "protein": 20.0, "fat": 10.0, "carbs": 0, "fiber": 0},
            "bell pepper": {"name": "Bell Pepper", "calories": 31, "protein": 1.0, "fat": 0.3, "carbs": 6.0, "fiber": 2.1},
            "pork shoulder": {"name": "Pork Shoulder", "calories": 165, "protein": 17.0, "fat": 9.0, "carbs": 0, "fiber": 0},
            "cucumber": {"name": "Cucumber", "calories": 16, "protein": 0.65, "fat": 0.11, "carbs": 3.63, "fiber": 0.5},
            "tomatoes": {"name": "Tomatoes", "calories": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "fiber": 1.2},
            "cheese": {"name": "Cheese (cheddar)", "calories": 403, "protein": 25.0, "fat": 33.0, "carbs": 1.3, "fiber": 0},
            "tortilla": {"name": "Tortilla (flour)", "calories": 140, "protein": 3.0, "fat": 3.0, "carbs": 24.0, "fiber": 1.5},
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "search_recipes",
            "get_recipe",
            "search_restaurants",
            "get_restaurant_menu",
            "get_nutrition",
            "create_meal_plan",
            "get_meal_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "search_recipes": self._search_recipes,
            "get_recipe": self._get_recipe,
            "search_restaurants": self._search_restaurants,
            "get_restaurant_menu": self._get_restaurant_menu,
            "get_nutrition": self._get_nutrition,
            "create_meal_plan": self._create_meal_plan,
            "get_meal_plan": self._get_meal_plan,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _search_recipes(
        self,
        query: str = "",
        cuisine: Optional[str] = None,
        diet_tags: Optional[list[str]] = None,
        max_prep_minutes: Optional[int] = None,
        max_cost_per_serving: Optional[float] = None,
    ) -> list[dict]:
        """Search recipes by query and filters."""
        results = []
        query_lower = query.lower() if query else ""
        for recipe in self._recipes.values():
            # Filter by cuisine
            if cuisine and recipe.get("cuisine") != cuisine:
                continue
            # Filter by diet tags (must have ALL specified tags)
            if diet_tags:
                recipe_tags = recipe.get("diet_tags", [])
                if not all(tag in recipe_tags for tag in diet_tags):
                    continue
            # Filter by prep time
            if max_prep_minutes and recipe.get("prep_minutes", 999) > max_prep_minutes:
                continue
            # Filter by cost
            if max_cost_per_serving and recipe.get("cost_per_serving", 999) > max_cost_per_serving:
                continue
            # Filter by query (search in name and tags)
            if query_lower:
                searchable = (
                    recipe.get("name", "").lower() + " " +
                    " ".join(recipe.get("tags", [])).lower() + " " +
                    " ".join(recipe.get("ingredients", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            # Return subset of fields for search results
            results.append({
                "id": recipe["id"],
                "name": recipe["name"],
                "cuisine": recipe["cuisine"],
                "diet_tags": recipe.get("diet_tags", []),
                "prep_minutes": recipe["prep_minutes"],
                "cost_per_serving": recipe["cost_per_serving"],
                "tags": recipe.get("tags", []),
            })
        return results

    def _get_recipe(self, recipe_id: str) -> Optional[dict]:
        """Get full recipe details by ID."""
        return self._recipes.get(recipe_id)

    def _search_restaurants(
        self,
        query: str = "",
        neighborhood: Optional[str] = None,
        cuisine: Optional[str] = None,
        max_price_level: Optional[int] = None,
    ) -> list[dict]:
        """Search restaurants by query and filters."""
        results = []
        query_lower = query.lower() if query else ""
        for rest in self._restaurants.values():
            # Filter by neighborhood
            if neighborhood and rest.get("neighborhood") != neighborhood:
                continue
            # Filter by cuisine
            if cuisine and rest.get("cuisine") != cuisine:
                continue
            # Filter by price level
            if max_price_level and rest.get("price_level", 4) > max_price_level:
                continue
            # Filter by query (search in name and tags)
            if query_lower:
                searchable = (
                    rest.get("name", "").lower() + " " +
                    " ".join(rest.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            results.append({
                "id": rest["id"],
                "name": rest["name"],
                "neighborhood": rest["neighborhood"],
                "cuisine": rest["cuisine"],
                "price_level": rest["price_level"],
                "tags": rest.get("tags", []),
                "distance_minutes": rest["distance_minutes"],
            })
        return results

    def _get_restaurant_menu(self, restaurant_id: str) -> Optional[list[dict]]:
        """Get menu for a restaurant."""
        return self._restaurant_menus.get(restaurant_id)

    def _get_nutrition(self, item_name: str) -> Optional[dict]:
        """Get nutrition info for a food item."""
        item_lower = item_name.lower()
        # Direct match
        if item_lower in self._nutrition_data:
            return self._nutrition_data[item_lower]
        # Partial match: key contains item or item contains key (use word boundaries)
        item_words = set(item_lower.split())
        for key, data in self._nutrition_data.items():
            key_words = set(key.split())
            # Check if any significant word from item is in key
            if item_words & key_words:
                return data
        return None

    def _create_meal_plan(
        self,
        name: str,
        recipe_ids: Optional[list[str]] = None,
        restaurant_ids: Optional[list[str]] = None,
        constraints_note: str = "",
    ) -> dict:
        """Create a new meal plan."""
        plan_id = f"plan_{len(self._meal_plans) + 1}"
        self._meal_plans[plan_id] = {
            "name": name,
            "recipe_ids": recipe_ids or [],
            "restaurant_ids": restaurant_ids or [],
            "constraints_note": constraints_note,
        }
        return {"plan_id": plan_id, "name": name, "created": True}

    def _get_meal_plan(self, plan_id: str) -> Optional[dict]:
        """Get meal plan details."""
        plan = self._meal_plans.get(plan_id)
        if not plan:
            return None
        # Resolve recipe details
        resolved_recipes = []
        for rid in plan.get("recipe_ids", []):
            recipe = self._recipes.get(rid)
            if recipe:
                resolved_recipes.append({
                    "id": rid,
                    "name": recipe["name"],
                    "cuisine": recipe["cuisine"],
                    "prep_minutes": recipe["prep_minutes"],
                })
        # Resolve restaurant details
        resolved_restaurants = []
        for rid in plan.get("restaurant_ids", []):
            rest = self._restaurants.get(rid)
            if rest:
                resolved_restaurants.append({
                    "id": rid,
                    "name": rest["name"],
                    "cuisine": rest["cuisine"],
                    "distance_minutes": rest["distance_minutes"],
                })
        return {
            "plan_id": plan_id,
            "name": plan["name"],
            "recipes": resolved_recipes,
            "restaurants": resolved_restaurants,
            "constraints_note": plan["constraints_note"],
        }

    def dump_state(self) -> dict:
        """Dump current toolkit state including meal plans."""
        return {
            "recipe_count": len(self._recipes),
            "restaurant_count": len(self._restaurants),
            "nutrition_count": len(self._nutrition_data),
            "meal_plans": copy.deepcopy(self._meal_plans),
        }

    def clone(self):
        """Create a fresh toolkit instance (default state, no meal plans)."""
        return ToolbenchFoodToolkit()

    # Public method wrappers (for invoke_tool compatibility)
    def search_recipes(
        self,
        query: str = "",
        cuisine: Optional[str] = None,
        diet_tags: Optional[list[str]] = None,
        max_prep_minutes: Optional[int] = None,
        max_cost_per_serving: Optional[float] = None,
    ) -> list[dict]:
        return self._search_recipes(query, cuisine, diet_tags, max_prep_minutes, max_cost_per_serving)

    def get_recipe(self, recipe_id: str) -> Optional[dict]:
        return self._get_recipe(recipe_id)

    def search_restaurants(
        self,
        query: str = "",
        neighborhood: Optional[str] = None,
        cuisine: Optional[str] = None,
        max_price_level: Optional[int] = None,
    ) -> list[dict]:
        return self._search_restaurants(query, neighborhood, cuisine, max_price_level)

    def get_restaurant_menu(self, restaurant_id: str) -> Optional[list[dict]]:
        return self._get_restaurant_menu(restaurant_id)

    def get_nutrition(self, item_name: str) -> Optional[dict]:
        return self._get_nutrition(item_name)

    def create_meal_plan(
        self,
        name: str,
        recipe_ids: Optional[list[str]] = None,
        restaurant_ids: Optional[list[str]] = None,
        constraints_note: str = "",
    ) -> dict:
        return self._create_meal_plan(name, recipe_ids, restaurant_ids, constraints_note)

    def get_meal_plan(self, plan_id: str) -> Optional[dict]:
        return self._get_meal_plan(plan_id)
