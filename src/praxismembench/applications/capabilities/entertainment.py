"""
ToolbenchEntertainmentToolkit - Mock entertainment domain toolkit for SOP workbench.

Provides unified content database (movies, TV, documentaries, music, variety, games)
with recommendation and watchlist capabilities.
"""

from typing import Optional
import copy


def load_default_entertainment_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchEntertainmentToolkit()


class ToolbenchEntertainmentToolkit:
    """
    Mock entertainment toolkit supporting:
    - Unified content search (movies, TV, docs, music, variety, games)
    - Mood/constraint-based recommendations
    - Watchlist state management
    """

    def __init__(self, content_db: Optional[dict] = None, watchlists: Optional[dict] = None):
        self._content_db = copy.deepcopy(content_db) if content_db is not None else self._build_default_fixture()
        self._watchlists = copy.deepcopy(watchlists) if watchlists is not None else {}

    def _build_default_fixture(self):
        """Build ~15 content items covering required test scenarios."""
        return {
            "movie_001": {
                "id": "movie_001",
                "title": "The Shawshank Redemption",
                "content_type": "movie",
                "year": 1994,
                "genres": ["drama"],
                "tags": ["classic", "mentally_demanding", "prison"],
                "moods": ["reflective", "serious"],
                "rating": 9.3,
                "runtime_minutes": 142,
                "synopsis": "Two imprisoned men bond over years, finding hope.",
                "director": "Frank Darabont",
            },
            "movie_002": {
                "id": "movie_002",
                "title": "Finding Nemo",
                "content_type": "movie",
                "year": 2003,
                "genres": ["animation", "family"],
                "tags": ["family-friendly", "light", "underwater"],
                "moods": ["cheerful", "relaxing"],
                "rating": 8.2,
                "runtime_minutes": 100,
                "synopsis": "A clownfish father searches for his son.",
                "director": "Andrew Stanton",
            },
            "movie_003": {
                "id": "movie_003",
                "title": "The Grand Budapest Hotel",
                "content_type": "movie",
                "year": 2014,
                "genres": ["comedy", "drama"],
                "tags": ["stylish", "light", "artistic"],
                "moods": ["entertaining", "quirky"],
                "rating": 8.1,
                "runtime_minutes": 99,
                "synopsis": "A concierge and his lobby boy become embroiled in theft.",
                "director": "Wes Anderson",
            },
            "movie_004": {
                "id": "movie_004",
                "title": "Inception",
                "content_type": "movie",
                "year": 2010,
                "genres": ["sci-fi", "action", "thriller"],
                "tags": ["mentally_demanding", "complex", "suspenseful"],
                "moods": ["intense", "thought-provoking"],
                "rating": 8.8,
                "runtime_minutes": 148,
                "synopsis": "A thief enters dreams to plant an idea.",
                "director": "Christopher Nolan",
            },
            "tv_001": {
                "id": "tv_001",
                "title": "Planet Earth",
                "content_type": "documentary",
                "year": 2006,
                "genres": ["nature", "documentary"],
                "tags": ["educational", "visually_stunning", "family-friendly"],
                "moods": ["calm", "awe-inspiring"],
                "rating": 9.4,
                "runtime_minutes": 50,  # per episode
                "synopsis": "Documentary series exploring Earth's habitats.",
                "creator": "BBC",
                "seasons": 1,
            },
            "tv_002": {
                "id": "tv_002",
                "title": "Friends",
                "content_type": "tv_show",
                "year": 1994,
                "genres": ["comedy", "sitcom"],
                "tags": ["light", "background-friendly", "comfort"],
                "moods": ["relaxing", "cheerful"],
                "rating": 8.9,
                "runtime_minutes": 22,
                "synopsis": "Six friends navigate life in New York.",
                "seasons": 10,
            },
            "tv_003": {
                "id": "tv_003",
                "title": "Cosmos: A Spacetime Odyssey",
                "content_type": "documentary",
                "year": 2014,
                "genres": ["science", "documentary"],
                "tags": ["educational", "mentally_engaging"],
                "moods": ["curious", "awe-inspiring"],
                "rating": 9.3,
                "runtime_minutes": 45,
                "synopsis": "Exploring the universe with Neil deGrasse Tyson.",
                "seasons": 1,
            },
            "tv_004": {
                "id": "tv_004",
                "title": "Running Man",
                "content_type": "variety",
                "year": 2010,
                "genres": ["variety", "game_show"],
                "tags": ["light", "entertaining", "background-friendly"],
                "moods": ["fun", "energetic"],
                "rating": 8.5,
                "runtime_minutes": 60,
                "synopsis": "Korean variety show with games and challenges.",
                "seasons": None,  # ongoing
            },
            "music_001": {
                "id": "music_001",
                "title": "Abbey Road",
                "content_type": "music",
                "year": 1969,
                "genres": ["rock", "pop"],
                "tags": ["classic", "album"],
                "moods": ["energetic", "nostalgic"],
                "rating": 9.5,
                "runtime_minutes": 47,
                "synopsis": "The Beatles' eleventh studio album.",
                "artist": "The Beatles",
            },
            "music_002": {
                "id": "music_002",
                "title": "Raindrops Keep Fallin' on My Head",
                "content_type": "music",
                "year": 1969,
                "genres": ["pop", "easy_listen"],
                "tags": ["relaxing", "short", "background-friendly"],
                "moods": ["calm", "cheerful"],
                "rating": 7.8,
                "runtime_minutes": 3,
                "synopsis": "Classic upbeat pop song.",
                "artist": "B.J. Thomas",
            },
            "game_001": {
                "id": "game_001",
                "title": "Stardew Valley",
                "content_type": "game",
                "year": 2016,
                "genres": ["simulation", "farming"],
                "tags": ["relaxing", "low-stress", "frugal_entertainment"],
                "moods": ["calm", "cozy"],
                "rating": 9.2,
                "runtime_minutes": None,  # variable
                "synopsis": "Farming simulation with community building.",
                "platforms": ["PC", "Switch", "Mobile"],
            },
            "game_002": {
                "id": "game_002",
                "title": "Portal 2",
                "content_type": "game",
                "year": 2011,
                "genres": ["puzzle", "puzzle-platformer"],
                "tags": ["mentally_demanding", "short_sessions", "single_player"],
                "moods": ["curious", "challenged"],
                "rating": 9.4,
                "runtime_minutes": None,
                "synopsis": "Puzzle game with portal mechanics.",
                "platforms": ["PC", "PS3", "Xbox 360"],
            },
            "game_003": {
                "id": "game_003",
                "title": "Mario Kart 8 Deluxe",
                "content_type": "game",
                "year": 2017,
                "genres": ["racing", "party"],
                "tags": ["family-friendly", "short_sessions", "multiplayer"],
                "moods": ["fun", "competitive"],
                "rating": 9.0,
                "runtime_minutes": None,
                "synopsis": "Fun racing game for groups.",
                "platforms": ["Nintendo Switch"],
            },
            "variety_001": {
                "id": "variety_001",
                "title": "TED Talks Daily",
                "content_type": "variety",
                "year": 2006,
                "genres": ["talk", "educational"],
                "tags": ["educational", "short", "mentally_engaging"],
                "moods": ["curious", "inspired"],
                "rating": 8.5,
                "runtime_minutes": 15,
                "synopsis": "Daily short talks on ideas worth spreading.",
            },
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "list_genres",
            "search_content",
            "get_content",
            "recommend_content",
            "create_watchlist",
            "add_to_watchlist",
            "get_watchlist",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "list_genres": self._list_genres,
            "search_content": self._search_content,
            "get_content": self._get_content,
            "recommend_content": self._recommend_content,
            "create_watchlist": self._create_watchlist,
            "add_to_watchlist": self._add_to_watchlist,
            "get_watchlist": self._get_watchlist,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _list_genres(self, content_type: Optional[str] = None) -> list[str]:
        """List available genres, optionally filtered by content type."""
        genres = set()
        for item in self._content_db.values():
            if content_type and item.get("content_type") != content_type:
                continue
            genres.update(item.get("genres", []))
        return sorted(genres)

    def _search_content(
        self,
        query: str = "",
        content_type: Optional[str] = None,
        genre: Optional[str] = None,
        max_runtime_minutes: Optional[int] = None,
    ) -> list[dict]:
        """Search content by query, type, genre, and runtime."""
        results = []
        query_lower = query.lower() if query else ""
        for item in self._content_db.values():
            if content_type and item.get("content_type") != content_type:
                continue
            if genre and genre not in item.get("genres", []):
                continue
            if max_runtime_minutes:
                runtime = item.get("runtime_minutes")
                if runtime and runtime > max_runtime_minutes:
                    continue
            if query_lower:
                # Match title, synopsis, or tags
                searchable = (
                    item.get("title", "").lower() + " " +
                    item.get("synopsis", "").lower() + " " +
                    " ".join(item.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            # Return subset of fields for search results
            results.append({
                "id": item["id"],
                "title": item["title"],
                "content_type": item["content_type"],
                "year": item["year"],
                "genres": item.get("genres", []),
                "rating": item.get("rating", 0.0),
                "runtime_minutes": item.get("runtime_minutes"),
            })
        return results

    def _get_content(self, content_id: str) -> Optional[dict]:
        """Get full content details by ID."""
        return self._content_db.get(content_id)

    def _recommend_content(
        self,
        preferred_genres: Optional[list[str]] = None,
        content_types: Optional[list[str]] = None,
        max_runtime_minutes: Optional[int] = None,
        avoid_tags: Optional[list[str]] = None,
        mood: Optional[str] = None,
        min_rating: float = 0.0,
        limit: int = 5,
    ) -> list[dict]:
        """Recommend content based on preferences and constraints."""
        candidates = []
        for item in self._content_db.values():
            # Filter by content type
            if content_types and item.get("content_type") not in content_types:
                continue
            # Filter by runtime
            if max_runtime_minutes:
                runtime = item.get("runtime_minutes")
                if runtime and runtime > max_runtime_minutes:
                    continue
            # Filter by rating
            if item.get("rating", 0.0) < min_rating:
                continue
            # Filter by avoid_tags
            if avoid_tags:
                item_tags = item.get("tags", [])
                if any(tag in item_tags for tag in avoid_tags):
                    continue
            # Filter by mood
            if mood:
                item_moods = item.get("moods", [])
                if mood not in item_moods:
                    continue

            # Score by preferred genres (optional boost)
            score = item.get("rating", 0.0)
            if preferred_genres:
                item_genres = item.get("genres", [])
                genre_matches = sum(1 for g in preferred_genres if g in item_genres)
                score += genre_matches * 0.5  # boost for genre match

            candidates.append((score, item))

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Return top N (subset of fields)
        results = []
        for score, item in candidates[:limit]:
            results.append({
                "id": item["id"],
                "title": item["title"],
                "content_type": item["content_type"],
                "genres": item.get("genres", []),
                "rating": item.get("rating", 0.0),
                "runtime_minutes": item.get("runtime_minutes"),
                "moods": item.get("moods", []),
                "tags": item.get("tags", []),
            })
        return results

    def _create_watchlist(self, name: str) -> dict:
        """Create a new watchlist."""
        watchlist_id = f"wl_{len(self._watchlists) + 1}"
        self._watchlists[watchlist_id] = {
            "name": name,
            "items": [],
        }
        return {"watchlist_id": watchlist_id, "name": name}

    def _add_to_watchlist(
        self, watchlist_id: str, content_id: str, note: str = ""
    ) -> dict:
        """Add content to a watchlist."""
        if watchlist_id not in self._watchlists:
            raise ValueError(f"Watchlist not found: {watchlist_id}")
        if content_id not in self._content_db:
            raise ValueError(f"Content not found: {content_id}")
        self._watchlists[watchlist_id]["items"].append({
            "content_id": content_id,
            "note": note,
        })
        return {
            "watchlist_id": watchlist_id,
            "content_id": content_id,
            "note": note,
            "added": True,
        }

    def _get_watchlist(self, watchlist_id: str) -> Optional[dict]:
        """Get watchlist details with items."""
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return None
        # Resolve content details for each item
        resolved_items = []
        for entry in wl["items"]:
            content = self._content_db.get(entry["content_id"])
            if content:
                resolved_items.append({
                    "content_id": entry["content_id"],
                    "title": content["title"],
                    "content_type": content["content_type"],
                    "note": entry["note"],
                })
        return {
            "watchlist_id": watchlist_id,
            "name": wl["name"],
            "items": resolved_items,
        }

    def dump_state(self) -> dict:
        """Dump current toolkit state including watchlists."""
        return {
            "content_count": len(self._content_db),
            "watchlists": copy.deepcopy(self._watchlists),
        }

    def clone(self):
        """Create a fresh toolkit instance (default state, no watchlists)."""
        return ToolbenchEntertainmentToolkit()

    # Public method wrappers (for invoke_tool compatibility)
    def list_genres(self, content_type: Optional[str] = None) -> list[str]:
        return self._list_genres(content_type)

    def search_content(
        self,
        query: str = "",
        content_type: Optional[str] = None,
        genre: Optional[str] = None,
        max_runtime_minutes: Optional[int] = None,
    ) -> list[dict]:
        return self._search_content(query, content_type, genre, max_runtime_minutes)

    def get_content(self, content_id: str) -> Optional[dict]:
        return self._get_content(content_id)

    def recommend_content(
        self,
        preferred_genres: Optional[list[str]] = None,
        content_types: Optional[list[str]] = None,
        max_runtime_minutes: Optional[int] = None,
        avoid_tags: Optional[list[str]] = None,
        mood: Optional[str] = None,
        min_rating: float = 0.0,
        limit: int = 5,
    ) -> list[dict]:
        return self._recommend_content(
            preferred_genres, content_types, max_runtime_minutes,
            avoid_tags, mood, min_rating, limit
        )

    def create_watchlist(self, name: str) -> dict:
        return self._create_watchlist(name)

    def add_to_watchlist(
        self, watchlist_id: str, content_id: str, note: str = ""
    ) -> dict:
        return self._add_to_watchlist(watchlist_id, content_id, note)

    def get_watchlist(self, watchlist_id: str) -> Optional[dict]:
        return self._get_watchlist(watchlist_id)
