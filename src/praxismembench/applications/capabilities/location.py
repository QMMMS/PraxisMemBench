"""
ToolbenchLocationToolkit - Mock location domain toolkit for SOP workbench.

Provides place search, nearby services, route calculation, and location planning
capabilities for testing commute preferences, distance preferences, accessibility,
and living radius preferences.
"""

from typing import Optional
import copy
import math


def load_default_location_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchLocationToolkit()


class ToolbenchLocationToolkit:
    """
    Mock location toolkit supporting:
    - Place search with type, location, distance filters
    - Nearby services search with mode (walk/drive/transit)
    - Route and distance calculation
    - Location plan state management
    """

    def __init__(
        self,
        places: Optional[dict] = None,
        routes: Optional[dict] = None,
        location_plans: Optional[dict] = None,
    ):
        self._places = copy.deepcopy(places) if places is not None else self._build_place_fixture()
        self._routes = copy.deepcopy(routes) if routes is not None else self._build_route_fixture()
        self._location_plans = copy.deepcopy(location_plans) if location_plans is not None else {}

    def _build_place_fixture(self):
        """Build ~50 places covering required test scenarios."""
        return {
            # Home locations
            "home_001": {
                "id": "home_001",
                "name": "Maple Street Apartment",
                "type": "home",
                "address": "123 Maple Street, Downtown",
                "coordinates": {"lat": 40.7128, "long": -74.0060},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["laundry", "gym", "doorman"],
                "noise_level": "moderate",
                "tags": ["apartment", "rental", "urban"],
            },
            "home_002": {
                "id": "home_002",
                "name": "Oak Avenue House",
                "type": "home",
                "address": "456 Oak Avenue, Westside",
                "coordinates": {"lat": 40.7589, "long": -73.9851},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": False, "has_parking": True, "family_friendly": True},
                "amenities": ["garden", "garage", "pet_friendly"],
                "noise_level": "quiet",
                "tags": ["house", "family", "suburban"],
            },
            "home_003": {
                "id": "home_003",
                "name": "Pine Road Condo",
                "type": "home",
                "address": "789 Pine Road, Midtown",
                "coordinates": {"lat": 40.7614, "long": -73.9776},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": False},
                "amenities": ["pool", "concierge", "rooftop"],
                "noise_level": "busy",
                "tags": ["condo", "luxury", "urban"],
            },

            # Work locations
            "work_001": {
                "id": "work_001",
                "name": "Tech Tower",
                "type": "work",
                "address": "100 Business Blvd, Downtown",
                "coordinates": {"lat": 40.7484, "long": -73.9857},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": False},
                "amenities": ["cafe", "gym", "conference_rooms"],
                "hours": {"open": "08:00", "close": "22:00"},
                "noise_level": "busy",
                "tags": ["office", "tech", "corporate"],
            },
            "work_002": {
                "id": "work_002",
                "name": "Creative Hub",
                "type": "work",
                "address": "200 Innovation Way, Eastside",
                "coordinates": {"lat": 40.7549, "long": -73.9682},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": False},
                "amenities": ["coworking", "coffee_bar", "event_space"],
                "hours": {"open": "09:00", "close": "21:00"},
                "noise_level": "moderate",
                "tags": ["coworking", "creative", "startup"],
            },

            # Schools
            "school_001": {
                "id": "school_001",
                "name": "Central Elementary School",
                "type": "school",
                "address": "50 Education Lane, Westside",
                "coordinates": {"lat": 40.7891, "long": -73.9645},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["playground", "library", "cafeteria"],
                "hours": {"open": "07:30", "close": "18:00"},
                "noise_level": "moderate",
                "tags": ["elementary", "public", "family"],
            },
            "school_002": {
                "id": "school_002",
                "name": "Downtown High School",
                "type": "school",
                "address": "75 Academic Avenue, Downtown",
                "coordinates": {"lat": 40.7214, "long": -74.0052},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["sports_field", "science_lab", "auditorium"],
                "hours": {"open": "08:00", "close": "17:00"},
                "noise_level": "moderate",
                "tags": ["high_school", "public", "education"],
            },

            # Clinics / Healthcare
            "clinic_001": {
                "id": "clinic_001",
                "name": "City Medical Center",
                "type": "clinic",
                "address": "300 Health Street, Downtown",
                "coordinates": {"lat": 40.7346, "long": -73.9894},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["emergency", "pharmacy", "lab"],
                "hours": {"open": "00:00", "close": "23:59"},
                "noise_level": "moderate",
                "tags": ["hospital", "emergency", "24h"],
            },
            "clinic_002": {
                "id": "clinic_002",
                "name": "Family Health Clinic",
                "type": "clinic",
                "address": "150 Wellness Road, Westside",
                "coordinates": {"lat": 40.7923, "long": -73.9587},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["pediatrics", "vaccinations", "checkups"],
                "hours": {"open": "08:00", "close": "20:00"},
                "noise_level": "quiet",
                "tags": ["clinic", "family", "pediatrics"],
            },
            "clinic_003": {
                "id": "clinic_003",
                "name": "Quick Care Express",
                "type": "clinic",
                "address": "25 Care Avenue, Eastside",
                "coordinates": {"lat": 40.7567, "long": -73.9654},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": False},
                "amenities": ["urgent_care", "xray", "prescriptions"],
                "hours": {"open": "08:00", "close": "22:00"},
                "noise_level": "busy",
                "tags": ["urgent_care", "walk_in", "express"],
            },

            # Grocery stores
            "grocery_001": {
                "id": "grocery_001",
                "name": "Fresh Market",
                "type": "grocery",
                "address": "400 Market Street, Downtown",
                "coordinates": {"lat": 40.7452, "long": -73.9912},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["organic", "deli", "bakery"],
                "hours": {"open": "07:00", "close": "22:00"},
                "noise_level": "busy",
                "tags": ["grocery", "supermarket", "organic", "fresh"],
            },
            "grocery_002": {
                "id": "grocery_002",
                "name": "Budget Grocers",
                "type": "grocery",
                "address": "500 Savings Lane, Westside",
                "coordinates": {"lat": 40.7982, "long": -73.9512},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["bulk", "discounts", "weekly_specials"],
                "hours": {"open": "08:00", "close": "21:00"},
                "noise_level": "moderate",
                "tags": ["grocery", "budget", "bulk", "family"],
            },
            "grocery_003": {
                "id": "grocery_003",
                "name": "Corner Convenience",
                "type": "grocery",
                "address": "10 Quick Stop, Eastside",
                "coordinates": {"lat": 40.7534, "long": -73.9723},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": False, "has_parking": False, "family_friendly": False},
                "amenities": ["snacks", "drinks", "basics"],
                "hours": {"open": "06:00", "close": "23:00"},
                "noise_level": "moderate",
                "tags": ["grocery", "convenience", "quick", "neighborhood"],
            },
            "grocery_004": {
                "id": "grocery_004",
                "name": "Organic Haven",
                "type": "grocery",
                "address": "350 Green Way, Midtown",
                "coordinates": {"lat": 40.7698, "long": -73.9821},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["organic_only", "local_produce", "vegan"],
                "hours": {"open": "09:00", "close": "20:00"},
                "noise_level": "quiet",
                "tags": ["grocery", "organic", "specialty", "health"],
            },

            # Parks
            "park_001": {
                "id": "park_001",
                "name": "Central Park",
                "type": "park",
                "address": "Central Park, Midtown",
                "coordinates": {"lat": 40.7829, "long": -73.9654},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["playground", "trails", "lake", "sports"],
                "hours": {"open": "06:00", "close": "22:00"},
                "noise_level": "moderate",
                "tags": ["large", "famous", "recreation", "nature"],
            },
            "park_002": {
                "id": "park_002",
                "name": "Quiet Garden Park",
                "type": "park",
                "address": "25 Serenity Path, Westside",
                "coordinates": {"lat": 40.8012, "long": -73.9478},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["garden", "benches", "meditation_area"],
                "hours": {"open": "07:00", "close": "19:00"},
                "noise_level": "quiet",
                "tags": ["quiet", "garden", "peaceful", "small"],
            },
            "park_003": {
                "id": "park_003",
                "name": "Adventure Playground",
                "type": "park",
                "address": "100 Fun Street, Eastside",
                "coordinates": {"lat": 40.7512, "long": -73.9687},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": False, "has_parking": True, "family_friendly": True},
                "amenities": ["playground", "splash_pad", "picnic_area"],
                "hours": {"open": "08:00", "close": "20:00"},
                "noise_level": "busy",
                "tags": ["playground", "kids", "family", "active"],
            },

            # Libraries
            "library_001": {
                "id": "library_001",
                "name": "Central Public Library",
                "type": "library",
                "address": "450 Book Lane, Downtown",
                "coordinates": {"lat": 40.7532, "long": -73.9821},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["reading_rooms", "computers", "kids_section", "study_area"],
                "hours": {"open": "09:00", "close": "21:00"},
                "noise_level": "quiet",
                "tags": ["public", "large", "study", "community"],
            },
            "library_002": {
                "id": "library_002",
                "name": "Neighborhood Branch Library",
                "type": "library",
                "address": "75 Reading Road, Westside",
                "coordinates": {"lat": 40.7845, "long": -73.9523},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["books", "storytime", "community_room"],
                "hours": {"open": "10:00", "close": "18:00"},
                "noise_level": "quiet",
                "tags": ["branch", "small", "community", "family"],
            },

            # Transit stops
            "transit_001": {
                "id": "transit_001",
                "name": "Downtown Metro Station",
                "type": "transit_stop",
                "address": "Union Square, Downtown",
                "coordinates": {"lat": 40.7359, "long": -73.9911},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["ticket_machine", "shelter", "bike_racks"],
                "hours": {"open": "05:00", "close": "01:00"},
                "noise_level": "busy",
                "tags": ["metro", "subway", "major", "accessible"],
            },
            "transit_002": {
                "id": "transit_002",
                "name": "Westside Bus Terminal",
                "type": "transit_stop",
                "address": "500 Transit Way, Westside",
                "coordinates": {"lat": 40.7989, "long": -73.9487},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["waiting_area", "restrooms", "coffee_shop"],
                "hours": {"open": "05:00", "close": "23:00"},
                "noise_level": "moderate",
                "tags": ["bus", "terminal", "accessible"],
            },
            "transit_003": {
                "id": "transit_003",
                "name": "Eastside Light Rail",
                "type": "transit_stop",
                "address": "200 Rail Avenue, Eastside",
                "coordinates": {"lat": 40.7578, "long": -73.9623},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["platform", "shelter"],
                "hours": {"open": "06:00", "close": "00:00"},
                "noise_level": "moderate",
                "tags": ["light_rail", "accessible", "quick"],
            },
            "transit_004": {
                "id": "transit_004",
                "name": "Maple Street Bus Stop",
                "type": "transit_stop",
                "address": "125 Maple Street, Downtown",
                "coordinates": {"lat": 40.7135, "long": -74.0058},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": False, "has_parking": False, "family_friendly": False},
                "amenities": ["shelter"],
                "hours": {"open": "05:00", "close": "23:00"},
                "noise_level": "moderate",
                "tags": ["bus_stop", "local", "basic"],
            },
            "transit_005": {
                "id": "transit_005",
                "name": "Oak Avenue Station",
                "type": "transit_stop",
                "address": "460 Oak Avenue, Westside",
                "coordinates": {"lat": 40.7592, "long": -73.9848},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["ticket_machine", "waiting_room", "bike_racks"],
                "hours": {"open": "05:00", "close": "01:00"},
                "noise_level": "moderate",
                "tags": ["train", "accessible", "commuter"],
            },
            "transit_006": {
                "id": "transit_006",
                "name": "Midtown Central Station",
                "type": "transit_stop",
                "address": "Grand Central, Midtown",
                "coordinates": {"lat": 40.7527, "long": -73.9772},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["foodCourt", "shops", "restrooms", "waiting_hall"],
                "hours": {"open": "05:00", "close": "02:00"},
                "noise_level": "busy",
                "tags": ["major", "train", "metro", "hub"],
            },

            # Restaurants
            "restaurant_001": {
                "id": "restaurant_001",
                "name": "The Italian Kitchen",
                "type": "restaurant",
                "address": "600 Pasta Place, Downtown",
                "coordinates": {"lat": 40.7412, "long": -73.9987},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["dine_in", "takeout", "delivery"],
                "hours": {"open": "11:00", "close": "22:00"},
                "noise_level": "moderate",
                "tags": ["italian", "dinner", "lunch"],
            },
            "restaurant_002": {
                "id": "restaurant_002",
                "name": "Quick Burger Joint",
                "type": "restaurant",
                "address": "75 Fast Food Lane, Eastside",
                "coordinates": {"lat": 40.7545, "long": -73.9698},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["drive_through", "takeout", "outdoor_seating"],
                "hours": {"open": "10:00", "close": "23:00"},
                "noise_level": "busy",
                "tags": ["fast_food", "burger", "casual"],
            },
            "restaurant_003": {
                "id": "restaurant_003",
                "name": "Sushi Zen",
                "type": "restaurant",
                "address": "200 Sushi Street, Midtown",
                "coordinates": {"lat": 40.7612, "long": -73.9765},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": False},
                "amenities": ["dine_in", "reservations", "sushi_bar"],
                "hours": {"open": "12:00", "close": "22:00"},
                "noise_level": "quiet",
                "tags": ["japanese", "sushi", "upscale"],
            },
            "restaurant_004": {
                "id": "restaurant_004",
                "name": "Family Diner",
                "type": "restaurant",
                "address": "800 Comfort Road, Westside",
                "coordinates": {"lat": 40.8034, "long": -73.9456},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["dine_in", "kids_menu", "breakfast"],
                "hours": {"open": "07:00", "close": "21:00"},
                "noise_level": "moderate",
                "tags": ["american", "family", "breakfast", "comfort"],
            },

            # Additional homes for variety
            "home_004": {
                "id": "home_004",
                "name": "Elm Street Studio",
                "type": "home",
                "address": "50 Elm Street, Eastside",
                "coordinates": {"lat": 40.7567, "long": -73.9712},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": False, "has_parking": False, "family_friendly": False},
                "amenities": ["modern", "bright", "urban"],
                "noise_level": "busy",
                "tags": ["studio", "single", "modern"],
            },
            "home_005": {
                "id": "home_005",
                "name": "Birch Lane Townhouse",
                "type": "home",
                "address": "25 Birch Lane, Midtown",
                "coordinates": {"lat": 40.7698, "long": -73.9801},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["backyard", "modern_kitchen", "garage"],
                "noise_level": "quiet",
                "tags": ["townhouse", "family", "upscale"],
            },

            # Additional transit for coverage
            "transit_007": {
                "id": "transit_007",
                "name": "Pine Road Metro",
                "type": "transit_stop",
                "address": "790 Pine Road, Midtown",
                "coordinates": {"lat": 40.7619, "long": -73.9782},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["escalator", "elevator", "ticket_machine"],
                "hours": {"open": "05:00", "close": "01:00"},
                "noise_level": "moderate",
                "tags": ["metro", "accessible", "midtown"],
            },
            "transit_008": {
                "id": "transit_008",
                "name": "Education Lane Bus",
                "type": "transit_stop",
                "address": "55 Education Lane, Westside",
                "coordinates": {"lat": 40.7895, "long": -73.9648},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["shelter", "bench"],
                "hours": {"open": "06:00", "close": "20:00"},
                "noise_level": "quiet",
                "tags": ["bus_stop", "school_route", "family"],
            },

            # Additional clinics
            "clinic_004": {
                "id": "clinic_004",
                "name": "Downtown Dental",
                "type": "clinic",
                "address": "250 Smile Street, Downtown",
                "coordinates": {"lat": 40.7321, "long": -73.9923},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["dental", "cleanings", "orthodontics"],
                "hours": {"open": "09:00", "close": "18:00"},
                "noise_level": "quiet",
                "tags": ["dental", "specialist", "appointments"],
            },

            # Additional grocery
            "grocery_005": {
                "id": "grocery_005",
                "name": "Metro Supermarket",
                "type": "grocery",
                "address": "550 Metro Plaza, Midtown",
                "coordinates": {"lat": 40.7587, "long": -73.9754},
                "neighborhood": "Midtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["full_selection", "pharmacy", "bakery"],
                "hours": {"open": "07:00", "close": "23:00"},
                "noise_level": "busy",
                "tags": ["grocery", "supermarket", "large", "convenience"],
            },

            # More parks
            "park_004": {
                "id": "park_004",
                "name": "Riverfront Park",
                "type": "park",
                "address": "1 River Walk, Eastside",
                "coordinates": {"lat": 40.7498, "long": -73.9734},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["river_view", "walking_path", "fishing"],
                "hours": {"open": "06:00", "close": "22:00"},
                "noise_level": "quiet",
                "tags": ["river", "nature", "walking"],
            },

            # More libraries
            "library_003": {
                "id": "library_003",
                "name": "Eastside Reading Corner",
                "type": "library",
                "address": "125 Books Way, Eastside",
                "coordinates": {"lat": 40.7589, "long": -73.9698},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["books", "wifi", "quiet_area"],
                "hours": {"open": "10:00", "close": "19:00"},
                "noise_level": "quiet",
                "tags": ["small", "neighborhood", "quiet"],
            },

            # More restaurants
            "restaurant_005": {
                "id": "restaurant_005",
                "name": "Taco Fiesta",
                "type": "restaurant",
                "address": "300 Fiesta Street, Eastside",
                "coordinates": {"lat": 40.7523, "long": -73.9678},
                "neighborhood": "Eastside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["dine_in", "takeout", "outdoor_seating"],
                "hours": {"open": "11:00", "close": "23:00"},
                "noise_level": "busy",
                "tags": ["mexican", "casual", "spicy"],
            },
            "restaurant_006": {
                "id": "restaurant_006",
                "name": "Green Salad Bar",
                "type": "restaurant",
                "address": "400 Health Plaza, Westside",
                "coordinates": {"lat": 40.7912, "long": -73.9567},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["salads", "smoothies", "vegetarian"],
                "hours": {"open": "08:00", "close": "20:00"},
                "noise_level": "quiet",
                "tags": ["healthy", "salad", "vegetarian"],
            },

            # Pharmacies (distinct from clinics)
            "pharmacy_001": {
                "id": "pharmacy_001",
                "name": "City Pharmacy",
                "type": "pharmacy",
                "address": "100 Medicine Lane, Downtown",
                "coordinates": {"lat": 40.7398, "long": -73.9901},
                "neighborhood": "Downtown",
                "accessibility": {"wheelchair_accessible": True, "has_parking": False, "family_friendly": True},
                "amenities": ["prescriptions", "otc", "consultations"],
                "hours": {"open": "08:00", "close": "22:00"},
                "noise_level": "moderate",
                "tags": ["pharmacy", "prescriptions", "health"],
            },
            "pharmacy_002": {
                "id": "pharmacy_002",
                "name": "Neighborhood Pharmacy",
                "type": "pharmacy",
                "address": "200 Pill Street, Westside",
                "coordinates": {"lat": 40.7856, "long": -73.9534},
                "neighborhood": "Westside",
                "accessibility": {"wheelchair_accessible": True, "has_parking": True, "family_friendly": True},
                "amenities": ["prescriptions", "vaccinations", "consultations"],
                "hours": {"open": "09:00", "close": "21:00"},
                "noise_level": "quiet",
                "tags": ["pharmacy", "neighborhood", "family"],
            },
        }

    def _build_route_fixture(self):
        """Build pre-computed routes between key locations."""
        return {
            # Home to work routes
            "home_001_work_001_walk": {
                "origin_id": "home_001",
                "destination_id": "work_001",
                "mode": "walk",
                "distance_km": 2.5,
                "duration_minutes": 30,
                "steps": ["Walk north on Maple Street", "Turn right on Business Blvd", "Arrive at Tech Tower"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_001_work_001_drive": {
                "origin_id": "home_001",
                "destination_id": "work_001",
                "mode": "drive",
                "distance_km": 3.2,
                "duration_minutes": 15,
                "steps": ["Drive north on Maple Street", "Turn right on Main Ave", "Turn left on Business Blvd", "Arrive at Tech Tower"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_001_work_001_transit": {
                "origin_id": "home_001",
                "destination_id": "work_001",
                "mode": "transit",
                "distance_km": 2.8,
                "duration_minutes": 20,
                "steps": ["Walk to Downtown Metro Station", "Take Line 1 to Business Blvd", "Walk 2 min to Tech Tower"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_work_001_drive": {
                "origin_id": "home_002",
                "destination_id": "work_001",
                "mode": "drive",
                "distance_km": 8.5,
                "duration_minutes": 25,
                "steps": ["Drive east on Oak Avenue", "Take highway to Downtown", "Exit at Business Blvd", "Arrive at Tech Tower"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_work_001_transit": {
                "origin_id": "home_002",
                "destination_id": "work_001",
                "mode": "transit",
                "distance_km": 9.0,
                "duration_minutes": 45,
                "steps": ["Walk to Westside Bus Terminal", "Take Bus 42 to Downtown", "Walk 5 min to Tech Tower"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_003_work_001_walk": {
                "origin_id": "home_003",
                "destination_id": "work_001",
                "mode": "walk",
                "distance_km": 1.2,
                "duration_minutes": 15,
                "steps": ["Walk south on Pine Road", "Turn left on Business Blvd", "Arrive at Tech Tower"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Home to school routes
            "home_002_school_001_walk": {
                "origin_id": "home_002",
                "destination_id": "school_001",
                "mode": "walk",
                "distance_km": 1.5,
                "duration_minutes": 18,
                "steps": ["Walk north on Oak Avenue", "Turn left on Education Lane", "Arrive at Central Elementary"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_school_001_drive": {
                "origin_id": "home_002",
                "destination_id": "school_001",
                "mode": "drive",
                "distance_km": 2.0,
                "duration_minutes": 8,
                "steps": ["Drive north on Oak Avenue", "Turn left on Education Lane", "Arrive at Central Elementary"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_001_school_002_transit": {
                "origin_id": "home_001",
                "destination_id": "school_002",
                "mode": "transit",
                "distance_km": 3.5,
                "duration_minutes": 25,
                "steps": ["Walk to Maple Street Bus Stop", "Take Bus 15 to Academic Avenue", "Walk 3 min to Downtown High"],
                "accessibility": {"wheelchair_accessible": False},
            },

            # Home to grocery routes
            "home_001_grocery_001_walk": {
                "origin_id": "home_001",
                "destination_id": "grocery_001",
                "mode": "walk",
                "distance_km": 1.8,
                "duration_minutes": 22,
                "steps": ["Walk north on Maple Street", "Turn right on Market Street", "Arrive at Fresh Market"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_grocery_002_drive": {
                "origin_id": "home_002",
                "destination_id": "grocery_002",
                "mode": "drive",
                "distance_km": 3.5,
                "duration_minutes": 12,
                "steps": ["Drive west on Oak Avenue", "Turn right on Savings Lane", "Arrive at Budget Grocers"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_003_grocery_004_walk": {
                "origin_id": "home_003",
                "destination_id": "grocery_004",
                "mode": "walk",
                "distance_km": 0.8,
                "duration_minutes": 10,
                "steps": ["Walk east on Pine Road", "Turn left on Green Way", "Arrive at Organic Haven"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Home to clinic routes
            "home_001_clinic_001_drive": {
                "origin_id": "home_001",
                "destination_id": "clinic_001",
                "mode": "drive",
                "distance_km": 2.0,
                "duration_minutes": 10,
                "steps": ["Drive east on Maple Street", "Turn right on Health Street", "Arrive at City Medical Center"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_clinic_002_walk": {
                "origin_id": "home_002",
                "destination_id": "clinic_002",
                "mode": "walk",
                "distance_km": 1.2,
                "duration_minutes": 15,
                "steps": ["Walk north on Oak Avenue", "Turn left on Wellness Road", "Arrive at Family Health Clinic"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Home to park routes
            "home_001_park_001_transit": {
                "origin_id": "home_001",
                "destination_id": "park_001",
                "mode": "transit",
                "distance_km": 4.5,
                "duration_minutes": 25,
                "steps": ["Walk to Downtown Metro Station", "Take Line 2 to Midtown", "Walk 5 min to Central Park"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_park_002_walk": {
                "origin_id": "home_002",
                "destination_id": "park_002",
                "mode": "walk",
                "distance_km": 0.5,
                "duration_minutes": 8,
                "steps": ["Walk east on Oak Avenue", "Turn right on Serenity Path", "Arrive at Quiet Garden Park"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Work to restaurant routes (lunch)
            "work_001_restaurant_001_walk": {
                "origin_id": "work_001",
                "destination_id": "restaurant_001",
                "mode": "walk",
                "distance_km": 0.8,
                "duration_minutes": 10,
                "steps": ["Walk south on Business Blvd", "Turn left on Pasta Place", "Arrive at The Italian Kitchen"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "work_001_restaurant_002_walk": {
                "origin_id": "work_001",
                "destination_id": "restaurant_002",
                "mode": "walk",
                "distance_km": 1.5,
                "duration_minutes": 18,
                "steps": ["Walk east on Business Blvd", "Cross to Eastside", "Turn right on Fast Food Lane"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Home to transit routes
            "home_001_transit_001_walk": {
                "origin_id": "home_001",
                "destination_id": "transit_001",
                "mode": "walk",
                "distance_km": 0.6,
                "duration_minutes": 8,
                "steps": ["Walk south on Maple Street", "Arrive at Downtown Metro Station"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_001_transit_004_walk": {
                "origin_id": "home_001",
                "destination_id": "transit_004",
                "mode": "walk",
                "distance_km": 0.1,
                "duration_minutes": 2,
                "steps": ["Walk to corner of Maple Street", "Arrive at Maple Street Bus Stop"],
                "accessibility": {"wheelchair_accessible": False},
            },
            "home_002_transit_002_drive": {
                "origin_id": "home_002",
                "destination_id": "transit_002",
                "mode": "drive",
                "distance_km": 2.5,
                "duration_minutes": 10,
                "steps": ["Drive west on Oak Avenue", "Turn right on Transit Way", "Arrive at Westside Bus Terminal"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_003_transit_006_walk": {
                "origin_id": "home_003",
                "destination_id": "transit_006",
                "mode": "walk",
                "distance_km": 0.4,
                "duration_minutes": 5,
                "steps": ["Walk south on Pine Road", "Arrive at Midtown Central Station"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Home to library routes
            "home_001_library_001_walk": {
                "origin_id": "home_001",
                "destination_id": "library_001",
                "mode": "walk",
                "distance_km": 2.2,
                "duration_minutes": 28,
                "steps": ["Walk north on Maple Street", "Turn right on Book Lane", "Arrive at Central Public Library"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_002_library_002_walk": {
                "origin_id": "home_002",
                "destination_id": "library_002",
                "mode": "walk",
                "distance_km": 0.8,
                "duration_minutes": 10,
                "steps": ["Walk east on Oak Avenue", "Turn left on Reading Road", "Arrive at Neighborhood Branch Library"],
                "accessibility": {"wheelchair_accessible": True},
            },

            # Cross neighborhood routes
            "home_001_home_002_drive": {
                "origin_id": "home_001",
                "destination_id": "home_002",
                "mode": "drive",
                "distance_km": 12.5,
                "duration_minutes": 35,
                "steps": ["Drive west on Maple Street", "Take highway to Westside", "Exit at Oak Avenue", "Arrive at Oak Avenue House"],
                "accessibility": {"wheelchair_accessible": True},
            },
            "home_003_home_004_walk": {
                "origin_id": "home_003",
                "destination_id": "home_004",
                "mode": "walk",
                "distance_km": 2.8,
                "duration_minutes": 35,
                "steps": ["Walk east on Pine Road", "Cross to Eastside", "Turn right on Elm Street", "Arrive at Elm Street Studio"],
                "accessibility": {"wheelchair_accessible": False},
            },
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "search_places",
            "get_place",
            "find_nearby_services",
            "calculate_route",
            "calculate_distance",
            "create_location_plan",
            "get_location_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "search_places": self._search_places,
            "get_place": self._get_place,
            "find_nearby_services": self._find_nearby_services,
            "calculate_route": self._calculate_route,
            "calculate_distance": self._calculate_distance,
            "create_location_plan": self._create_location_plan,
            "get_location_plan": self._get_location_plan,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _search_places(
        self,
        query: str = "",
        place_type: Optional[str] = None,
        neighborhood: Optional[str] = None,
        max_distance_km: Optional[float] = None,
        near_location: Optional[str] = None,
        accessibility_required: Optional[list[str]] = None,
        noise_preference: Optional[str] = None,
    ) -> list[dict]:
        """Search places by query and filters."""
        results = []
        query_lower = query.lower() if query else ""

        # Get reference location for distance filtering
        ref_coords = None
        if near_location and max_distance_km:
            ref_place = self._places.get(near_location)
            if ref_place:
                ref_coords = ref_place["coordinates"]

        for place in self._places.values():
            # Filter by place_type
            if place_type and place.get("type") != place_type:
                continue

            # Filter by neighborhood
            if neighborhood and place.get("neighborhood") != neighborhood:
                continue

            # Filter by query (search in name, address, tags)
            if query_lower:
                searchable = (
                    place.get("name", "").lower() + " " +
                    place.get("address", "").lower() + " " +
                    " ".join(place.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue

            # Filter by distance from reference location
            if ref_coords and max_distance_km:
                dist = self._haversine_distance(
                    ref_coords["lat"], ref_coords["long"],
                    place["coordinates"]["lat"], place["coordinates"]["long"]
                )
                if dist > max_distance_km:
                    continue

            # Filter by accessibility requirements
            if accessibility_required:
                place_access = place.get("accessibility", {})
                if not all(place_access.get(req, False) for req in accessibility_required):
                    continue

            # Filter by noise preference
            if noise_preference and place.get("noise_level") != noise_preference:
                continue

            # Return subset of fields for search results
            results.append({
                "id": place["id"],
                "name": place["name"],
                "type": place["type"],
                "address": place["address"],
                "neighborhood": place["neighborhood"],
                "coordinates": place["coordinates"],
                "noise_level": place.get("noise_level"),
                "tags": place.get("tags", []),
                "accessibility": place.get("accessibility", {}),
            })

        # Sort by distance if near_location specified
        if near_location and ref_coords:
            results.sort(key=lambda p: self._haversine_distance(
                ref_coords["lat"], ref_coords["long"],
                p["coordinates"]["lat"], p["coordinates"]["long"]
            ))

        return results

    def _get_place(self, place_id: str) -> Optional[dict]:
        """Get full place details by ID."""
        return self._places.get(place_id)

    def _find_nearby_services(
        self,
        location: str,
        service_type: Optional[str] = None,
        max_distance_km: float = 2.0,
        mode: str = "walk",
        accessibility_required: Optional[list[str]] = None,
    ) -> list[dict]:
        """Find services near a location."""
        # Get reference place
        ref_place = self._places.get(location)
        if not ref_place:
            return []

        ref_coords = ref_place["coordinates"]
        results = []

        # Mode-based distance limits (walk: typically 2km, drive: 10km, transit: 5km)
        effective_max_distance = max_distance_km
        if mode == "drive" and max_distance_km < 5:
            effective_max_distance = max_distance_km * 2
        elif mode == "transit" and max_distance_km < 3:
            effective_max_distance = max_distance_km * 1.5

        for place in self._places.values():
            # Filter by service type (can be multiple types)
            if service_type:
                valid_types = [service_type] if isinstance(service_type, str) else service_type
                if place.get("type") not in valid_types:
                    continue

            # Calculate distance
            dist = self._haversine_distance(
                ref_coords["lat"], ref_coords["long"],
                place["coordinates"]["lat"], place["coordinates"]["long"]
            )

            if dist > effective_max_distance:
                continue

            # Filter by accessibility
            if accessibility_required:
                place_access = place.get("accessibility", {})
                if not all(place_access.get(req, False) for req in accessibility_required):
                    continue

            # Estimate travel time based on mode
            travel_time = self._estimate_travel_time(dist, mode)

            results.append({
                "id": place["id"],
                "name": place["name"],
                "type": place["type"],
                "distance_km": round(dist, 2),
                "travel_time_minutes": travel_time,
                "mode": mode,
                "address": place["address"],
                "neighborhood": place["neighborhood"],
                "accessibility": place.get("accessibility", {}),
                "hours": place.get("hours", {}),
            })

        # Sort by distance
        results.sort(key=lambda p: p["distance_km"])

        return results

    def _calculate_route(
        self,
        origin: str,
        destination: str,
        mode: str = "walk",
    ) -> Optional[dict]:
        """Calculate route between two locations."""
        # Look for pre-computed route
        route_key = f"{origin}_{destination}_{mode}"
        if route_key in self._routes:
            route = self._routes[route_key]
            # Resolve place names
            origin_place = self._places.get(origin)
            dest_place = self._places.get(destination)
            return {
                "origin": origin_place.get("name") if origin_place else origin,
                "origin_id": origin,
                "destination": dest_place.get("name") if dest_place else destination,
                "destination_id": destination,
                "mode": mode,
                "distance_km": route["distance_km"],
                "duration_minutes": route["duration_minutes"],
                "steps": route["steps"],
                "accessibility": route.get("accessibility", {}),
            }

        # Fall back to distance calculation if no pre-computed route
        origin_place = self._places.get(origin)
        dest_place = self._places.get(destination)
        if not origin_place or not dest_place:
            return None

        dist = self._haversine_distance(
            origin_place["coordinates"]["lat"], origin_place["coordinates"]["long"],
            dest_place["coordinates"]["lat"], dest_place["coordinates"]["long"]
        )

        travel_time = self._estimate_travel_time(dist, mode)

        return {
            "origin": origin_place["name"],
            "origin_id": origin,
            "destination": dest_place["name"],
            "destination_id": destination,
            "mode": mode,
            "distance_km": round(dist, 2),
            "duration_minutes": travel_time,
            "steps": [f"Travel {round(dist, 1)} km from {origin_place['name']} to {dest_place['name']}"],
            "accessibility": {"wheelchair_accessible": True},  # default assumption
        }

    def _calculate_distance(
        self,
        location_a: str,
        location_b: str,
        mode: str = "direct",
    ) -> Optional[dict]:
        """Calculate distance between two locations."""
        place_a = self._places.get(location_a)
        place_b = self._places.get(location_b)

        if not place_a or not place_b:
            return None

        # Direct haversine distance
        direct_dist = self._haversine_distance(
            place_a["coordinates"]["lat"], place_a["coordinates"]["long"],
            place_b["coordinates"]["lat"], place_b["coordinates"]["long"]
        )

        # Adjust distance based on mode
        adjusted_dist = direct_dist
        if mode == "walk":
            adjusted_dist = direct_dist * 1.2  # walking paths are typically longer
        elif mode == "drive":
            adjusted_dist = direct_dist * 1.3  # roads may be longer
        elif mode == "transit":
            adjusted_dist = direct_dist * 1.1  # transit routes may deviate

        travel_time = self._estimate_travel_time(adjusted_dist, mode)

        return {
            "location_a": place_a["name"],
            "location_a_id": location_a,
            "location_b": place_b["name"],
            "location_b_id": location_b,
            "direct_distance_km": round(direct_dist, 2),
            "adjusted_distance_km": round(adjusted_dist, 2),
            "mode": mode,
            "estimated_duration_minutes": travel_time,
        }

    def _create_location_plan(
        self,
        name: str,
        place_ids: Optional[list[str]] = None,
        commute_analysis: Optional[dict] = None,
        constraints_note: str = "",
    ) -> dict:
        """Create a new location plan."""
        plan_id = f"plan_{len(self._location_plans) + 1}"
        self._location_plans[plan_id] = {
            "name": name,
            "place_ids": place_ids or [],
            "commute_analysis": commute_analysis or {},
            "constraints_note": constraints_note,
        }
        return {"plan_id": plan_id, "name": name, "created": True}

    def _get_location_plan(self, plan_id: str) -> Optional[dict]:
        """Get location plan details."""
        plan = self._location_plans.get(plan_id)
        if not plan:
            return None

        # Resolve place details
        resolved_places = []
        for pid in plan.get("place_ids", []):
            place = self._places.get(pid)
            if place:
                resolved_places.append({
                    "id": pid,
                    "name": place["name"],
                    "type": place["type"],
                    "address": place["address"],
                    "neighborhood": place["neighborhood"],
                })

        return {
            "plan_id": plan_id,
            "name": plan["name"],
            "places": resolved_places,
            "commute_analysis": plan["commute_analysis"],
            "constraints_note": plan["constraints_note"],
        }

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates using haversine formula."""
        R = 6371  # Earth radius in kilometers

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _estimate_travel_time(self, distance_km: float, mode: str) -> int:
        """Estimate travel time based on distance and mode."""
        # Approximate speeds: walk 5 km/h, drive 30 km/h (city), transit 20 km/h
        speeds = {
            "walk": 5,
            "drive": 30,
            "transit": 20,
            "direct": 100,  # just for estimation
        }
        speed = speeds.get(mode, 5)
        # Time in minutes = distance / speed * 60
        return int(distance_km / speed * 60)

    def dump_state(self) -> dict:
        """Dump current toolkit state including location plans."""
        return {
            "place_count": len(self._places),
            "route_count": len(self._routes),
            "location_plans": copy.deepcopy(self._location_plans),
            "neighborhoods": list(set(p.get("neighborhood") for p in self._places.values())),
            "place_types": list(set(p.get("type") for p in self._places.values())),
        }

    def clone(self):
        """Create a fresh toolkit instance (default state, no location plans)."""
        return ToolbenchLocationToolkit()

    # Public method wrappers (for invoke_tool compatibility)
    def search_places(
        self,
        query: str = "",
        place_type: Optional[str] = None,
        neighborhood: Optional[str] = None,
        max_distance_km: Optional[float] = None,
        near_location: Optional[str] = None,
        accessibility_required: Optional[list[str]] = None,
        noise_preference: Optional[str] = None,
    ) -> list[dict]:
        return self._search_places(query, place_type, neighborhood, max_distance_km, near_location, accessibility_required, noise_preference)

    def get_place(self, place_id: str) -> Optional[dict]:
        return self._get_place(place_id)

    def find_nearby_services(
        self,
        location: str,
        service_type: Optional[str] = None,
        max_distance_km: float = 2.0,
        mode: str = "walk",
        accessibility_required: Optional[list[str]] = None,
    ) -> list[dict]:
        return self._find_nearby_services(location, service_type, max_distance_km, mode, accessibility_required)

    def calculate_route(
        self,
        origin: str,
        destination: str,
        mode: str = "walk",
    ) -> Optional[dict]:
        return self._calculate_route(origin, destination, mode)

    def calculate_distance(
        self,
        location_a: str,
        location_b: str,
        mode: str = "direct",
    ) -> Optional[dict]:
        return self._calculate_distance(location_a, location_b, mode)

    def create_location_plan(
        self,
        name: str,
        place_ids: Optional[list[str]] = None,
        commute_analysis: Optional[dict] = None,
        constraints_note: str = "",
    ) -> dict:
        return self._create_location_plan(name, place_ids, commute_analysis, constraints_note)

    def get_location_plan(self, plan_id: str) -> Optional[dict]:
        return self._get_location_plan(plan_id)