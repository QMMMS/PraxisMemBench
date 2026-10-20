from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Union


# BFCL DEFAULT_STATE
DEFAULT_STATE = {
    "username": "john",
    "password": "john123",
    "authenticated": False,
    "tweets": {},
    "comments": {},
    "retweets": {},
    "following_list": ["alice", "bob"],
    "tweet_counter": 0,
}


class BFCLPostingToolkit:
    """Standardized wrapper for BFCL TwitterAPI tools.

    Faithfully reproduces BFCL posting_api.py behavior including:
    - Authentication with username/password
    - Tweet posting, retweeting, commenting
    - User following/unfollowing
    - Tweet and user statistics
    """

    def __init__(
        self,
        username: str = "john",
        password: str = "john123",
        authenticated: bool = False,
        tweets: Optional[Dict[int, Dict[str, Any]]] = None,
        comments: Optional[Dict[int, List[Dict[str, str]]]] = None,
        retweets: Optional[Dict[str, List[int]]] = None,
        following_list: Optional[List[str]] = None,
        tweet_counter: int = 0,
    ) -> None:
        """Initialize posting toolkit with optional state.

        Args:
            tweet_counter: BFCL explicit counter. New tweet uses current counter,
                           then counter increments.
        """
        self.username: str = username
        self.password: str = password
        self.authenticated: bool = authenticated
        self.tweets: Dict[int, Dict[str, Any]] = tweets if tweets is not None else {}
        # Convert string keys to int if needed (from scenario load)
        self.tweets = {int(k) if isinstance(k, str) and str(k).isdigit() else k: v for k, v in self.tweets.items()}
        self.comments: Dict[int, List[Dict[str, str]]] = comments if comments is not None else {}
        self.retweets: Dict[str, List[int]] = retweets if retweets is not None else {}
        self.following_list: List[str] = following_list if following_list is not None else ["alice", "bob"]
        self.tweet_counter: int = tweet_counter

    def clone(self) -> "BFCLPostingToolkit":
        """Return toolkit reset to default BFCL state."""
        return BFCLPostingToolkit()

    def dump_state(self) -> Dict[str, Any]:
        """Export current state in BFCL format."""
        return {
            "username": self.username,
            "password": self.password,
            "authenticated": self.authenticated,
            "tweets": deepcopy(self.tweets),
            "comments": deepcopy(self.comments),
            "retweets": deepcopy(self.retweets),
            "following_list": deepcopy(self.following_list),
            "tweet_counter": self.tweet_counter,
        }

    def list_tools(self) -> List[str]:
        """Return available tool names."""
        return [
            "authenticate_twitter",
            "posting_get_login_status",
            "post_tweet",
            "retweet",
            "comment",
            "mention",
            "follow_user",
            "list_all_following",
            "unfollow_user",
            "get_tweet",
            "get_user_tweets",
            "search_tweets",
            "get_tweet_comments",
            "get_user_stats",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke tool by name."""
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown posting tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    # === Authentication ===

    def authenticate_twitter(self, username: str, password: str) -> Dict[str, bool]:
        """Authenticate user.

        Args:
            username: Username.
            password: Password.

        Returns:
            authentication_status.
        """
        if username == self.username and password == self.password:
            self.authenticated = True
            return {"authentication_status": True}
        return {"authentication_status": False}

    def posting_get_login_status(self) -> Dict[str, bool]:
        """Get login status.

        Returns:
            login_status.
        """
        return {"login_status": bool(self.authenticated)}

    # === Tweets ===

    def post_tweet(
        self, content: str, tags: List[str] = [], mentions: List[str] = []
    ) -> Dict[str, Any]:
        """Post a tweet.

        Args:
            content: Tweet content.
            tags: List of tags (starting with #).
            mentions: List of mentioned users (starting with @).

        Returns:
            id, username, content, tags, mentions.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before posting."}

        # BFCL semantics: use current tweet_counter as id, then increment
        tweet_id = self.tweet_counter
        self.tweet_counter += 1

        tweet = {
            "id": tweet_id,
            "username": self.username,
            "content": content,
            "tags": tags,
            "mentions": mentions,
        }
        self.tweets[tweet_id] = tweet
        return tweet

    def retweet(self, tweet_id: int) -> Dict[str, str]:
        """Retweet a tweet.

        Args:
            tweet_id: ID of tweet to retweet.

        Returns:
            retweet_status.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before retweeting."}

        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        if self.username not in self.retweets:
            self.retweets[self.username] = []

        if tweet_id in self.retweets[self.username]:
            return {"retweet_status": "Already retweeted"}

        self.retweets[self.username].append(tweet_id)
        return {"retweet_status": "Successfully retweeted"}

    def comment(self, tweet_id: int, comment_content: str) -> Dict[str, str]:
        """Comment on a tweet.

        Args:
            tweet_id: ID of tweet to comment on.
            comment_content: Comment content.

        Returns:
            comment_status.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before commenting."}

        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        if tweet_id not in self.comments:
            self.comments[tweet_id] = []

        self.comments[tweet_id].append({
            "username": self.username,
            "content": comment_content,
        })
        return {"comment_status": "Comment added successfully"}

    def mention(self, tweet_id: int, mentioned_usernames: List[str]) -> Dict[str, str]:
        """Mention users in a tweet.

        Args:
            tweet_id: ID of tweet.
            mentioned_usernames: List of usernames to mention.

        Returns:
            mention_status.
        """
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        tweet = self.tweets[tweet_id]
        tweet["mentions"].extend(mentioned_usernames)

        return {"mention_status": "Users mentioned successfully"}

    # === Following ===

    def follow_user(self, username_to_follow: str) -> Dict[str, Union[bool, str]]:
        """Follow a user.

        Args:
            username_to_follow: Username to follow.

        Returns:
            follow_status.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before following."}

        if username_to_follow in self.following_list:
            return {"follow_status": False}

        self.following_list.append(username_to_follow)
        return {"follow_status": True}

    def list_all_following(self) -> Dict[str, Union[List[str], str]]:
        """List all following users.

        Returns:
            following_list.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before listing following."}

        return {"following_list": deepcopy(self.following_list)}

    def unfollow_user(self, username_to_unfollow: str) -> Dict[str, Union[bool, str]]:
        """Unfollow a user.

        Args:
            username_to_unfollow: Username to unfollow.

        Returns:
            unfollow_status.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before unfollowing."}

        if username_to_unfollow not in self.following_list:
            return {"unfollow_status": False}

        self.following_list.remove(username_to_unfollow)
        return {"unfollow_status": True}

    # === Retrieval ===

    def get_tweet(self, tweet_id: int) -> Dict[str, Any]:
        """Get a specific tweet.

        Args:
            tweet_id: ID of tweet.

        Returns:
            Tweet details.
        """
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        return deepcopy(self.tweets[tweet_id])

    def get_user_tweets(self, username: str) -> List[Dict[str, Any]]:
        """Get all tweets from a user.

        Args:
            username: Username.

        Returns:
            List of tweets.
        """
        return [
            deepcopy(tweet) for tweet in self.tweets.values()
            if tweet["username"] == username
        ]

    def search_tweets(self, keyword: str) -> List[Dict[str, Any]]:
        """Search tweets by keyword.

        Args:
            keyword: Keyword to search.

        Returns:
            List of matching tweets.
        """
        return [
            deepcopy(tweet) for tweet in self.tweets.values()
            if keyword.lower() in tweet["content"].lower()
            or keyword.lower() in [tag.lower() for tag in tweet["tags"]]
        ]

    def get_tweet_comments(self, tweet_id: int) -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Get comments for a tweet.

        Args:
            tweet_id: ID of tweet.

        Returns:
            List of comments, or error dict.
        """
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}
        return deepcopy(self.comments.get(tweet_id, []))

    def get_user_stats(self, username: str) -> Dict[str, int]:
        """Get user statistics.

        Args:
            username: Username.

        Returns:
            tweet_count, following_count, retweet_count.
        """
        tweet_count = len([
            tweet for tweet in self.tweets.values()
            if tweet["username"] == username
        ])
        following_count = len(self.following_list) if username == self.username else 0
        retweet_count = len(self.retweets.get(username, []))

        return {
            "tweet_count": tweet_count,
            "following_count": following_count,
            "retweet_count": retweet_count,
        }


def load_default_posting_toolkit() -> BFCLPostingToolkit:
    """Load toolkit with default BFCL state."""
    return BFCLPostingToolkit()