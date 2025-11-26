#!/usr/bin/env python3
"""
Reddit Historical Scraper using Pushshift API

This script scrapes historical Reddit data using the Pushshift API and stores 
the content in a ZIP file with JSON format. The JSON hierarchy is:
subreddit -> post -> comments, with user information for posts and comments.
"""

import json
import os
import time
import zipfile
from datetime import datetime
from typing import Optional

import requests


class PushshiftRedditScraper:
    """Scrapes historical Reddit data using the Pushshift API."""

    # Pushshift API base URLs
    PUSHSHIFT_SUBMISSIONS_URL = "https://api.pushshift.io/reddit/search/submission"
    PUSHSHIFT_COMMENTS_URL = "https://api.pushshift.io/reddit/search/comment"

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the scraper.

        Args:
            rate_limit_delay: Delay between API requests in seconds to avoid rate limiting.
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PushshiftRedditScraper/1.0"
        })

    def _make_request(self, url: str, params: dict) -> Optional[dict]:
        """
        Make a request to the Pushshift API with error handling.

        Args:
            url: The API endpoint URL.
            params: Query parameters for the request.

        Returns:
            JSON response data or None if request failed.
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return None

    def fetch_submissions(
        self,
        subreddit: str,
        before: Optional[int] = None,
        after: Optional[int] = None,
        size: int = 100
    ) -> list:
        """
        Fetch submissions (posts) from a subreddit.

        Args:
            subreddit: Name of the subreddit to scrape.
            before: Unix timestamp - fetch posts before this time.
            after: Unix timestamp - fetch posts after this time.
            size: Number of posts to fetch (max 100 per request).

        Returns:
            List of submission dictionaries.
        """
        params = {
            "subreddit": subreddit,
            "size": min(size, 100),
            "sort": "desc",
            "sort_type": "created_utc"
        }

        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after

        data = self._make_request(self.PUSHSHIFT_SUBMISSIONS_URL, params)

        if data and "data" in data:
            return data["data"]
        return []

    def fetch_comments_for_post(self, post_id: str, size: int = 500) -> list:
        """
        Fetch comments for a specific post.

        Args:
            post_id: The Reddit post ID (without t3_ prefix).
            size: Maximum number of comments to fetch.

        Returns:
            List of comment dictionaries.
        """
        params = {
            "link_id": post_id,
            "size": min(size, 500),
            "sort": "desc",
            "sort_type": "created_utc"
        }

        data = self._make_request(self.PUSHSHIFT_COMMENTS_URL, params)

        if data and "data" in data:
            return data["data"]
        return []

    def format_submission(self, submission: dict) -> dict:
        """
        Format a submission into a structured dictionary with user info.

        Args:
            submission: Raw submission data from Pushshift.

        Returns:
            Formatted submission dictionary.
        """
        return {
            "id": submission.get("id"),
            "title": submission.get("title"),
            "selftext": submission.get("selftext", ""),
            "url": submission.get("url"),
            "score": submission.get("score"),
            "num_comments": submission.get("num_comments"),
            "created_utc": submission.get("created_utc"),
            "permalink": submission.get("permalink"),
            "user": {
                "username": submission.get("author"),
                "author_fullname": submission.get("author_fullname")
            },
            "comments": []
        }

    def format_comment(self, comment: dict) -> dict:
        """
        Format a comment into a structured dictionary with user info.

        Args:
            comment: Raw comment data from Pushshift.

        Returns:
            Formatted comment dictionary.
        """
        return {
            "id": comment.get("id"),
            "body": comment.get("body"),
            "score": comment.get("score"),
            "created_utc": comment.get("created_utc"),
            "parent_id": comment.get("parent_id"),
            "permalink": comment.get("permalink"),
            "user": {
                "username": comment.get("author"),
                "author_fullname": comment.get("author_fullname")
            }
        }

    def scrape_subreddit(
        self,
        subreddit: str,
        max_posts: int = 100,
        before: Optional[int] = None,
        after: Optional[int] = None,
        include_comments: bool = True
    ) -> dict:
        """
        Scrape a subreddit and return structured data.

        Args:
            subreddit: Name of the subreddit to scrape.
            max_posts: Maximum number of posts to scrape.
            before: Unix timestamp - fetch posts before this time.
            after: Unix timestamp - fetch posts after this time.
            include_comments: Whether to also fetch comments for each post.

        Returns:
            Dictionary with subreddit data in the required hierarchy.
        """
        print(f"Scraping subreddit: r/{subreddit}")

        subreddit_data = {
            "subreddit": subreddit,
            "scraped_at": datetime.utcnow().isoformat(),
            "posts": []
        }

        # Fetch submissions
        posts_fetched = 0
        current_before = before

        while posts_fetched < max_posts:
            batch_size = min(100, max_posts - posts_fetched)
            submissions = self.fetch_submissions(
                subreddit=subreddit,
                before=current_before,
                after=after,
                size=batch_size
            )

            if not submissions:
                break

            for submission in submissions:
                if posts_fetched >= max_posts:
                    break

                formatted_post = self.format_submission(submission)
                post_id = submission.get("id")

                # Fetch comments for this post if requested
                if include_comments and post_id:
                    print(f"  Fetching comments for post: {post_id}")
                    comments = self.fetch_comments_for_post(post_id)
                    formatted_post["comments"] = [
                        self.format_comment(c) for c in comments
                    ]

                subreddit_data["posts"].append(formatted_post)
                posts_fetched += 1

                # Update cursor for pagination
                if "created_utc" in submission:
                    current_before = submission["created_utc"]

            print(f"  Fetched {posts_fetched}/{max_posts} posts")

        return subreddit_data

    def scrape_multiple_subreddits(
        self,
        subreddits: list,
        max_posts_per_subreddit: int = 100,
        before: Optional[int] = None,
        after: Optional[int] = None,
        include_comments: bool = True
    ) -> dict:
        """
        Scrape multiple subreddits and return combined data.

        Args:
            subreddits: List of subreddit names to scrape.
            max_posts_per_subreddit: Maximum number of posts per subreddit.
            before: Unix timestamp - fetch posts before this time.
            after: Unix timestamp - fetch posts after this time.
            include_comments: Whether to also fetch comments for each post.

        Returns:
            Dictionary with all scraped data organized by subreddit.
        """
        result = {
            "metadata": {
                "scraped_at": datetime.utcnow().isoformat(),
                "total_subreddits": len(subreddits),
                "subreddits_list": subreddits
            },
            "subreddits": {}
        }

        for subreddit in subreddits:
            subreddit_data = self.scrape_subreddit(
                subreddit=subreddit,
                max_posts=max_posts_per_subreddit,
                before=before,
                after=after,
                include_comments=include_comments
            )
            result["subreddits"][subreddit] = subreddit_data

        return result

    def save_to_zip(self, data: dict, output_path: str) -> str:
        """
        Save scraped data to a ZIP file containing JSON.

        Args:
            data: The scraped data dictionary.
            output_path: Path for the output ZIP file.

        Returns:
            Path to the created ZIP file.
        """
        # Ensure the output path ends with .zip
        if not output_path.endswith('.zip'):
            output_path = output_path + '.zip'

        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        json_filename = os.path.basename(output_path).replace('.zip', '.json')

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            zipf.writestr(json_filename, json_content)

        print(f"Data saved to: {output_path}")
        return output_path


def main():
    """Main function to demonstrate the scraper usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape historical Reddit data using Pushshift API"
    )
    parser.add_argument(
        "-s", "--subreddits",
        nargs="+",
        required=True,
        help="List of subreddits to scrape (without r/ prefix)"
    )
    parser.add_argument(
        "-n", "--max-posts",
        type=int,
        default=10,
        help="Maximum number of posts per subreddit (default: 10)"
    )
    parser.add_argument(
        "-o", "--output",
        default="reddit_data.zip",
        help="Output ZIP file path (default: reddit_data.zip)"
    )
    parser.add_argument(
        "--before",
        type=int,
        default=None,
        help="Unix timestamp - fetch posts before this time"
    )
    parser.add_argument(
        "--after",
        type=int,
        default=None,
        help="Unix timestamp - fetch posts after this time"
    )
    parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip fetching comments for posts"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Delay between API requests in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    # Create scraper and run
    scraper = PushshiftRedditScraper(rate_limit_delay=args.rate_limit)

    data = scraper.scrape_multiple_subreddits(
        subreddits=args.subreddits,
        max_posts_per_subreddit=args.max_posts,
        before=args.before,
        after=args.after,
        include_comments=not args.no_comments
    )

    # Save to ZIP
    scraper.save_to_zip(data, args.output)

    # Print summary
    total_posts = sum(
        len(sub_data.get("posts", []))
        for sub_data in data.get("subreddits", {}).values()
    )
    total_comments = sum(
        len(post.get("comments", []))
        for sub_data in data.get("subreddits", {}).values()
        for post in sub_data.get("posts", [])
    )

    print(f"\nScraping complete!")
    print(f"Total subreddits: {len(data.get('subreddits', {}))}")
    print(f"Total posts: {total_posts}")
    print(f"Total comments: {total_comments}")


if __name__ == "__main__":
    main()
