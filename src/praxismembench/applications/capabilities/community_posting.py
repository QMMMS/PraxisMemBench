from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_community_posting_toolkit() -> "TrainingCommunityPostingToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingCommunityPostingToolkit()


class TrainingCommunityPostingToolkit:
    """Mock community posting toolkit for training-only benchmark domains."""

    DEFAULT_BOARDS: dict[str, dict[str, Any]] = {
        "board_neighbors": {"board_ref": "board_neighbors", "audience_group": "neighbors", "visibility": "local", "tags": ["practical"]},
        "board_volunteers": {"board_ref": "board_volunteers", "audience_group": "volunteers", "visibility": "group", "tags": ["coordination"]},
        "board_creators": {"board_ref": "board_creators", "audience_group": "creators", "visibility": "public", "tags": ["community"]},
    }

    def __init__(
        self,
        boards: dict[str, dict[str, Any]] | None = None,
        posts: dict[str, dict[str, Any]] | None = None,
        comment_log: list[dict[str, Any]] | None = None,
    ) -> None:
        self._boards = copy.deepcopy(boards) if boards is not None else copy.deepcopy(self.DEFAULT_BOARDS)
        self._posts = copy.deepcopy(posts) if posts is not None else {}
        self._comment_log = copy.deepcopy(comment_log) if comment_log is not None else []

    def clone(self) -> "TrainingCommunityPostingToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingCommunityPostingToolkit(copy.deepcopy(self._boards), copy.deepcopy(self._posts), copy.deepcopy(self._comment_log))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_boards", "inspect_board", "create_community_post", "add_post_comment", "get_community_post"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"community_posting": {"boards": copy.deepcopy(self._boards), "posts": copy.deepcopy(self._posts), "comment_log": copy.deepcopy(self._comment_log)}}

    def search_boards(self, audience_group: str | None = None, visibility: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search community boards.

        Args:
            audience_group: Optional audience group filter.
            visibility: Optional visibility filter.
            required_tag: Optional tag filter.
        """
        boards = []
        for board in self._boards.values():
            if audience_group and board.get("audience_group") != audience_group:
                continue
            if visibility and board.get("visibility") != visibility:
                continue
            if required_tag and required_tag not in board.get("tags", []):
                continue
            boards.append(copy.deepcopy(board))
        return {"boards": boards, "count": len(boards)}

    def inspect_board(self, board_ref: str) -> dict[str, Any]:
        """Inspect one board.

        Args:
            board_ref: Board reference.
        """
        return copy.deepcopy(self._boards.get(board_ref, {"error": f"Board not found: {board_ref}"}))

    def create_community_post(self, board_ref: str, post_title: str, post_body: str, audience_note: str | None = None) -> dict[str, Any]:
        """Create a community board post.

        Args:
            board_ref: Board reference.
            post_title: Post title.
            post_body: Post body.
            audience_note: Optional personalized audience note.
        """
        if board_ref not in self._boards:
            return {"error": f"Board not found: {board_ref}"}
        post_ref = f"community_post_{len(self._posts) + 1:03d}"
        post = {"post_ref": post_ref, "board_ref": board_ref, "post_title": post_title, "post_body": post_body, "audience_note": audience_note or "", "created_at": _now_iso()}
        self._posts[post_ref] = post
        return copy.deepcopy(post)

    def add_post_comment(self, post_ref: str, comment_body: str, mention_group: str | None = None) -> dict[str, Any]:
        """Add a comment to a post.

        Args:
            post_ref: Post reference.
            comment_body: Comment body.
            mention_group: Optional mention group.
        """
        if post_ref not in self._posts:
            return {"error": f"Post not found: {post_ref}"}
        comment = {"comment_ref": f"community_comment_{len(self._comment_log) + 1:03d}", "post_ref": post_ref, "comment_body": comment_body, "mention_group": mention_group or "", "created_at": _now_iso()}
        self._comment_log.append(comment)
        return copy.deepcopy(comment)

    def get_community_post(self, post_ref: str) -> dict[str, Any]:
        """Get a community post.

        Args:
            post_ref: Post reference.
        """
        return copy.deepcopy(self._posts.get(post_ref, {"error": f"Post not found: {post_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
