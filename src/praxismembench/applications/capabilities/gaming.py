"""
ToolbenchGamingToolkit - Mock gaming domain toolkit for SOP workbench.

Provides game database (platforms, genres, session constraints) with
recommendation and game shortlist capabilities.
"""

from typing import Optional
import copy


def load_default_gaming_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchGamingToolkit()


class ToolbenchGamingToolkit:
    """
    Mock gaming toolkit supporting:
    - Platform listing (Switch, PC, Mobile, PS5, Xbox)
    - Game search with genre/platform/session filters
    - Recommendation with social_mode and avoid_tags
    - Character search by game and role
    - Game shortlist state management
    """

    def __init__(
        self,
        games_db: Optional[dict] = None,
        characters_db: Optional[dict] = None,
        shortlists: Optional[dict] = None,
    ):
        self._games_db = copy.deepcopy(games_db) if games_db is not None else self._build_default_games_fixture()
        self._characters_db = (
            copy.deepcopy(characters_db) if characters_db is not None else self._build_default_characters_fixture()
        )
        self._shortlists = copy.deepcopy(shortlists) if shortlists is not None else {}

    def _build_default_games_fixture(self):
        """Build ~14 games covering required test scenarios."""
        return {
            "game_001": {
                "id": "game_001",
                "title": "Stardew Valley",
                "platforms": ["PC", "Switch", "Mobile"],
                "genres": ["simulation", "farming"],
                "tags": ["cozy", "relaxing", "low-stress", "single_player"],
                "social_modes": ["solo"],
                "typical_session_minutes": 30,
                "difficulty": "easy",
                "rating": 9.2,
                "summary": "Peaceful farming simulation with community building.",
            },
            "game_002": {
                "id": "game_002",
                "title": "Animal Crossing: New Horizons",
                "platforms": ["Switch"],
                "genres": ["simulation", "life_sim"],
                "tags": ["cozy", "casual", "family-friendly", "relaxing"],
                "social_modes": ["solo", "family"],
                "typical_session_minutes": 20,
                "difficulty": "easy",
                "rating": 9.0,
                "summary": "Charming island life simulator with cute characters.",
            },
            "game_003": {
                "id": "game_003",
                "title": "Portal 2",
                "platforms": ["PC", "PS3", "Xbox 360"],
                "genres": ["puzzle", "puzzle-platformer"],
                "tags": ["single_player", "mentally_engaging", "short_sessions"],
                "social_modes": ["solo", "co_op"],
                "typical_session_minutes": 45,
                "difficulty": "medium",
                "rating": 9.4,
                "summary": "Puzzle game with portal mechanics and witty humor.",
            },
            "game_004": {
                "id": "game_004",
                "title": "Mario Kart 8 Deluxe",
                "platforms": ["Switch"],
                "genres": ["racing", "party"],
                "tags": ["family-friendly", "short_sessions", "multiplayer"],
                "social_modes": ["competitive", "family", "co_op"],
                "typical_session_minutes": 15,
                "difficulty": "easy",
                "rating": 9.0,
                "summary": "Fun kart racing for groups and families.",
            },
            "game_005": {
                "id": "game_005",
                "title": "Overcooked 2",
                "platforms": ["PC", "Switch", "PS4", "Xbox One"],
                "genres": ["co_op", "simulation"],
                "tags": ["chaotic", "teamwork", "stressful", "multiplayer"],
                "social_modes": ["co_op"],
                "typical_session_minutes": 30,
                "difficulty": "medium",
                "rating": 8.7,
                "summary": "Chaotic kitchen co-op game requiring teamwork.",
            },
            "game_006": {
                "id": "game_006",
                "title": "League of Legends",
                "platforms": ["PC"],
                "genres": ["moba", "strategy"],
                "tags": ["competitive", "stressful", "mentally_demanding", "multiplayer"],
                "social_modes": ["competitive", "co_op"],
                "typical_session_minutes": 40,
                "difficulty": "hard",
                "rating": 8.5,
                "summary": "Team-based strategy game with champions.",
            },
            "game_007": {
                "id": "game_007",
                "title": "Minecraft",
                "platforms": ["PC", "Switch", "Mobile", "PS4", "Xbox One"],
                "genres": ["sandbox", "survival", "creative"],
                "tags": ["creative", "exploration", "family-friendly"],
                "social_modes": ["solo", "co_op", "family"],
                "typical_session_minutes": 60,
                "difficulty": "easy",
                "rating": 9.1,
                "summary": "Open-world sandbox for building and exploring.",
            },
            "game_008": {
                "id": "game_008",
                "title": "The Legend of Zelda: Breath of the Wild",
                "platforms": ["Switch", "Wii U"],
                "genres": ["action_adventure", "open_world"],
                "tags": ["exploration", "single_player", "immersive"],
                "social_modes": ["solo"],
                "typical_session_minutes": 90,
                "difficulty": "medium",
                "rating": 9.7,
                "summary": "Open-world adventure with exploration and puzzles.",
            },
            "game_009": {
                "id": "game_009",
                "title": "Celeste",
                "platforms": ["PC", "Switch", "PS4", "Xbox One"],
                "genres": ["platformer", "indie"],
                "tags": ["difficult", "single_player", "mentally_demanding", "stressful"],
                "social_modes": ["solo"],
                "typical_session_minutes": 30,
                "difficulty": "hard",
                "rating": 9.3,
                "summary": "Challenging platformer about climbing a mountain.",
            },
            "game_010": {
                "id": "game_010",
                "title": "Among Us",
                "platforms": ["PC", "Mobile", "Switch"],
                "genres": ["social_deduction", "party"],
                "tags": ["multiplayer", "social", "short_sessions"],
                "social_modes": ["competitive", "co_op"],
                "typical_session_minutes": 15,
                "difficulty": "easy",
                "rating": 8.3,
                "summary": "Social deduction game about finding impostors.",
            },
            "game_011": {
                "id": "game_011",
                "title": "Hades",
                "platforms": ["PC", "Switch", "PS5", "Xbox Series X"],
                "genres": ["roguelike", "action"],
                "tags": ["single_player", "fast-paced", "mentally_engaging"],
                "social_modes": ["solo"],
                "typical_session_minutes": 45,
                "difficulty": "medium",
                "rating": 9.5,
                "summary": "Roguelike action game escaping from underworld.",
            },
            "game_012": {
                "id": "game_012",
                "title": "Pokemon Sword",
                "platforms": ["Switch"],
                "genres": ["rpg", "collection"],
                "tags": ["single_player", "collection", "family-friendly"],
                "social_modes": ["solo", "competitive"],
                "typical_session_minutes": 60,
                "difficulty": "easy",
                "rating": 8.0,
                "summary": "Pokemon adventure catching and battling creatures.",
            },
            "game_013": {
                "id": "game_013",
                "title": "Tetris Effect",
                "platforms": ["PC", "Switch", "PS4"],
                "genres": ["puzzle"],
                "tags": ["relaxing", "short_sessions", "single_player"],
                "social_modes": ["solo"],
                "typical_session_minutes": 10,
                "difficulty": "easy",
                "rating": 9.0,
                "summary": "Classic puzzle game with immersive visuals.",
            },
            "game_014": {
                "id": "game_014",
                "title": "Fortnite",
                "platforms": ["PC", "Switch", "Mobile", "PS4", "Xbox One"],
                "genres": ["battle_royale", "action"],
                "tags": ["competitive", "stressful", "multiplayer", "fast-paced"],
                "social_modes": ["competitive", "co_op"],
                "typical_session_minutes": 20,
                "difficulty": "medium",
                "rating": 7.8,
                "summary": "Battle royale shooter with building mechanics.",
            },
        }

    def _build_default_characters_fixture(self):
        """Build ~10 characters linked to games."""
        return {
            "char_001": {
                "id": "char_001",
                "name": "Mario",
                "game_id": "game_004",
                "role": "main_character",
                "tags": ["hero", "iconic", "family-friendly"],
                "summary": "Plumber hero racing in kart championships.",
            },
            "char_002": {
                "id": "char_002",
                "name": "Link",
                "game_id": "game_008",
                "role": "main_character",
                "tags": ["hero", "adventurer", "iconic"],
                "summary": "Hero exploring Hyrule and solving puzzles.",
            },
            "char_003": {
                "id": "char_003",
                "name": "Pikachu",
                "game_id": "game_012",
                "role": "partner",
                "tags": ["pokemon", "iconic", "cute", "family-friendly"],
                "summary": "Electric mouse Pokemon companion.",
            },
            "char_004": {
                "id": "char_004",
                "name": "Isabelle",
                "game_id": "game_002",
                "role": "support",
                "tags": ["cozy", "cute", "helpful"],
                "summary": "Friendly dog assistant managing island.",
            },
            "char_005": {
                "id": "char_005",
                "name": "Chell",
                "game_id": "game_003",
                "role": "main_character",
                "tags": ["silent", "determined"],
                "summary": "Test subject solving portal puzzles.",
            },
            "char_006": {
                "id": "char_006",
                "name": "Madeline",
                "game_id": "game_009",
                "role": "main_character",
                "tags": ["determined", "relatable", "mental_health"],
                "summary": "Young woman climbing Celeste mountain.",
            },
            "char_007": {
                "id": "char_007",
                "name": "Zagreus",
                "game_id": "game_011",
                "role": "main_character",
                "tags": ["rebellious", "determined", "son_of_god"],
                "summary": "Prince of underworld escaping to surface.",
            },
            "char_008": {
                "id": "char_008",
                "name": "Steve",
                "game_id": "game_007",
                "role": "main_character",
                "tags": ["iconic", "creative", "silent"],
                "summary": "Blocky miner building and crafting.",
            },
            "char_009": {
                "id": "char_009",
                "name": "Ahri",
                "game_id": "game_006",
                "role": "champion",
                "tags": ["mage", "mobile", "popular"],
                "summary": "Nine-tailed fox spirit champion.",
            },
            "char_010": {
                "id": "char_010",
                "name": "Yoshi",
                "game_id": "game_004",
                "role": "support",
                "tags": ["cute", "family-friendly", "iconic"],
                "summary": "Friendly dinosaur racing companion.",
            },
            "char_011": {
                "id": "char_011",
                "name": "GLaDOS",
                "game_id": "game_003",
                "role": "antagonist",
                "tags": ["robot", "sarcastic", "iconic"],
                "summary": "AI system testing subjects with sarcasm.",
            },
            "char_012": {
                "id": "char_012",
                "name": "Villager",
                "game_id": "game_002",
                "role": "main_character",
                "tags": ["customizable", "cozy", "neutral"],
                "summary": "Customizable character living on island.",
            },
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "list_platforms",
            "search_games",
            "get_game",
            "recommend_games",
            "search_characters",
            "create_game_shortlist",
            "add_to_game_shortlist",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "list_platforms": self._list_platforms,
            "search_games": self._search_games,
            "get_game": self._get_game,
            "recommend_games": self._recommend_games,
            "search_characters": self._search_characters,
            "create_game_shortlist": self._create_game_shortlist,
            "add_to_game_shortlist": self._add_to_game_shortlist,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _list_platforms(self) -> list[str]:
        """List available gaming platforms."""
        platforms = set()
        for game in self._games_db.values():
            platforms.update(game.get("platforms", []))
        return sorted(platforms)

    def _search_games(
        self,
        query: str = "",
        genre: Optional[str] = None,
        platform: Optional[str] = None,
        max_session_minutes: Optional[int] = None,
    ) -> list[dict]:
        """Search games by query, genre, platform, and session length."""
        results = []
        query_lower = query.lower() if query else ""
        for game in self._games_db.values():
            if genre and genre not in game.get("genres", []):
                continue
            if platform and platform not in game.get("platforms", []):
                continue
            if max_session_minutes:
                session = game.get("typical_session_minutes")
                if session and session > max_session_minutes:
                    continue
            if query_lower:
                searchable = (
                    game.get("title", "").lower() + " " +
                    game.get("summary", "").lower() + " " +
                    " ".join(game.get("tags", [])).lower() + " " +
                    " ".join(game.get("genres", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            # Return subset of fields for search results
            results.append({
                "id": game["id"],
                "title": game["title"],
                "platforms": game.get("platforms", []),
                "genres": game.get("genres", []),
                "rating": game.get("rating", 0.0),
                "typical_session_minutes": game.get("typical_session_minutes"),
                "social_modes": game.get("social_modes", []),
            })
        return results

    def _get_game(self, game_id: str) -> Optional[dict]:
        """Get full game details by ID."""
        return self._games_db.get(game_id)

    def _recommend_games(
        self,
        preferred_genres: Optional[list[str]] = None,
        platforms: Optional[list[str]] = None,
        max_session_minutes: Optional[int] = None,
        social_mode: Optional[str] = None,
        avoid_tags: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Recommend games based on preferences and constraints."""
        candidates = []
        for game in self._games_db.values():
            # Filter by platform
            if platforms:
                game_platforms = game.get("platforms", [])
                if not any(p in game_platforms for p in platforms):
                    continue
            # Filter by session length
            if max_session_minutes:
                session = game.get("typical_session_minutes")
                if session and session > max_session_minutes:
                    continue
            # Filter by social mode
            if social_mode:
                game_social_modes = game.get("social_modes", [])
                if social_mode not in game_social_modes:
                    continue
            # Filter by avoid_tags
            if avoid_tags:
                game_tags = game.get("tags", [])
                if any(tag in game_tags for tag in avoid_tags):
                    continue

            # Score by preferred genres (optional boost)
            score = game.get("rating", 0.0)
            if preferred_genres:
                game_genres = game.get("genres", [])
                genre_matches = sum(1 for g in preferred_genres if g in game_genres)
                score += genre_matches * 0.5

            candidates.append((score, game))

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Return top N (subset of fields)
        results = []
        for score, game in candidates[:limit]:
            results.append({
                "id": game["id"],
                "title": game["title"],
                "platforms": game.get("platforms", []),
                "genres": game.get("genres", []),
                "rating": game.get("rating", 0.0),
                "typical_session_minutes": game.get("typical_session_minutes"),
                "social_modes": game.get("social_modes", []),
                "tags": game.get("tags", []),
            })
        return results

    def _search_characters(
        self,
        query: str = "",
        game_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> list[dict]:
        """Search characters by query, game, and role."""
        results = []
        query_lower = query.lower() if query else ""
        for char in self._characters_db.values():
            if game_id and char.get("game_id") != game_id:
                continue
            if role and char.get("role") != role:
                continue
            if query_lower:
                searchable = (
                    char.get("name", "").lower() + " " +
                    char.get("summary", "").lower() + " " +
                    " ".join(char.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            # Return subset of fields for search results
            results.append({
                "id": char["id"],
                "name": char["name"],
                "game_id": char.get("game_id"),
                "role": char.get("role"),
                "tags": char.get("tags", []),
            })
        return results

    def _create_game_shortlist(self, name: str) -> dict:
        """Create a new game shortlist."""
        shortlist_id = f"sl_{len(self._shortlists) + 1}"
        self._shortlists[shortlist_id] = {
            "name": name,
            "games": [],
        }
        return {"shortlist_id": shortlist_id, "name": name}

    def _add_to_game_shortlist(
        self, shortlist_id: str, game_id: str, note: str = ""
    ) -> dict:
        """Add game to a shortlist."""
        if shortlist_id not in self._shortlists:
            raise ValueError(f"Shortlist not found: {shortlist_id}")
        if game_id not in self._games_db:
            raise ValueError(f"Game not found: {game_id}")
        self._shortlists[shortlist_id]["games"].append({
            "game_id": game_id,
            "note": note,
        })
        return {
            "shortlist_id": shortlist_id,
            "game_id": game_id,
            "note": note,
            "added": True,
        }

    def _get_game_shortlist(self, shortlist_id: str) -> Optional[dict]:
        """Get shortlist details with resolved game info."""
        sl = self._shortlists.get(shortlist_id)
        if not sl:
            return None
        # Resolve game details for each entry
        resolved_games = []
        for entry in sl["games"]:
            game = self._games_db.get(entry["game_id"])
            if game:
                resolved_games.append({
                    "game_id": entry["game_id"],
                    "title": game["title"],
                    "platforms": game.get("platforms", []),
                    "note": entry["note"],
                })
        return {
            "shortlist_id": shortlist_id,
            "name": sl["name"],
            "games": resolved_games,
        }

    def dump_state(self) -> dict:
        """Dump current toolkit state including shortlists."""
        return {
            "games_count": len(self._games_db),
            "characters_count": len(self._characters_db),
            "shortlists": copy.deepcopy(self._shortlists),
        }

    def clone(self):
        """Create a fresh toolkit instance (default state, no shortlists)."""
        return ToolbenchGamingToolkit()

    # Public method wrappers (for invoke_tool compatibility)
    def list_platforms(self) -> list[str]:
        return self._list_platforms()

    def search_games(
        self,
        query: str = "",
        genre: Optional[str] = None,
        platform: Optional[str] = None,
        max_session_minutes: Optional[int] = None,
    ) -> list[dict]:
        return self._search_games(query, genre, platform, max_session_minutes)

    def get_game(self, game_id: str) -> Optional[dict]:
        return self._get_game(game_id)

    def recommend_games(
        self,
        preferred_genres: Optional[list[str]] = None,
        platforms: Optional[list[str]] = None,
        max_session_minutes: Optional[int] = None,
        social_mode: Optional[str] = None,
        avoid_tags: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[dict]:
        return self._recommend_games(
            preferred_genres, platforms, max_session_minutes,
            social_mode, avoid_tags, limit
        )

    def search_characters(
        self,
        query: str = "",
        game_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> list[dict]:
        return self._search_characters(query, game_id, role)

    def create_game_shortlist(self, name: str) -> dict:
        return self._create_game_shortlist(name)

    def add_to_game_shortlist(
        self, shortlist_id: str, game_id: str, note: str = ""
    ) -> dict:
        return self._add_to_game_shortlist(shortlist_id, game_id, note)

    def get_game_shortlist(self, shortlist_id: str) -> Optional[dict]:
        return self._get_game_shortlist(shortlist_id)
