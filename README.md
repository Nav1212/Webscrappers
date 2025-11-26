# Webscrappers

A collection of web scraping tools.

## Reddit Historical Scraper

A Python script that uses the Pushshift API to scrape historical Reddit records and store them in ZIP format.

### Features

- Scrapes historical Reddit posts and comments using Pushshift API
- Organizes data in JSON format with hierarchy: subreddit -> post -> comments
- Includes user information for posts and comments
- Saves output as a compressed ZIP file
- Supports multiple subreddits in a single run
- Rate limiting to avoid API restrictions

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```bash
# Scrape a single subreddit
python reddit_scraper.py -s python -n 10 -o output.zip

# Scrape multiple subreddits
python reddit_scraper.py -s python programming -n 20 -o reddit_data.zip

# Scrape with time range (Unix timestamps)
python reddit_scraper.py -s python --after 1609459200 --before 1640995200

# Skip fetching comments
python reddit_scraper.py -s python --no-comments

# Custom rate limiting (2 seconds between requests)
python reddit_scraper.py -s python --rate-limit 2.0
```

### Output Format

The output is a ZIP file containing a JSON file with the following structure:

```json
{
  "metadata": {
    "scraped_at": "2024-01-01T12:00:00",
    "total_subreddits": 1,
    "subreddits_list": ["python"]
  },
  "subreddits": {
    "python": {
      "subreddit": "python",
      "scraped_at": "2024-01-01T12:00:00",
      "posts": [
        {
          "id": "abc123",
          "title": "Post Title",
          "selftext": "Post content...",
          "url": "https://...",
          "score": 100,
          "num_comments": 10,
          "created_utc": 1609459200,
          "permalink": "/r/python/comments/...",
          "user": {
            "username": "author_name",
            "author_fullname": "t2_xxxxx"
          },
          "comments": [
            {
              "id": "xyz789",
              "body": "Comment text...",
              "score": 50,
              "created_utc": 1609459300,
              "parent_id": "t3_abc123",
              "permalink": "/r/python/comments/.../xyz789",
              "user": {
                "username": "commenter_name",
                "author_fullname": "t2_yyyyy"
              }
            }
          ]
        }
      ]
    }
  }
}
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `-s, --subreddits` | List of subreddits to scrape (required) |
| `-n, --max-posts` | Maximum posts per subreddit (default: 10) |
| `-o, --output` | Output ZIP file path (default: reddit_data.zip) |
| `--before` | Unix timestamp - fetch posts before this time |
| `--after` | Unix timestamp - fetch posts after this time |
| `--no-comments` | Skip fetching comments for posts |
| `--rate-limit` | Delay between API requests in seconds (default: 1.0) |

### Note

The Pushshift API may have rate limits or availability issues. If you encounter errors, try increasing the `--rate-limit` value or reducing the number of posts to scrape