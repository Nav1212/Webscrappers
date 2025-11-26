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
- **Daily scraping mode**: Scrape top N posts per day from top 1000 subreddits
- Rate limiting to avoid API restrictions

### Installation

```bash
pip install -r requirements.txt
```

### Usage

The scraper has three commands: `scrape`, `daily`, and `list-subreddits`.

#### Basic Scraping

```bash
# Scrape a single subreddit
python reddit_scraper.py scrape -s python -n 10 -o output.zip

# Scrape multiple subreddits
python reddit_scraper.py scrape -s python programming -n 20 -o reddit_data.zip

# Scrape with time range (Unix timestamps)
python reddit_scraper.py scrape -s python --after 1609459200 --before 1640995200

# Skip fetching comments
python reddit_scraper.py scrape -s python --no-comments

# Custom rate limiting (2 seconds between requests)
python reddit_scraper.py scrape -s python --rate-limit 2.0
```

#### Daily Top Posts Scraping

Scrape the top N posts per day from subreddits over a date range. This is ideal for building a comprehensive historical dataset.

```bash
# Scrape top 10 posts per day from top 1000 subreddits (full history)
python reddit_scraper.py daily --top-subreddits 1000 -n 10

# Scrape from specific subreddits with date range
python reddit_scraper.py daily -s python programming --start-date 2020-01-01 --end-date 2023-12-31

# Scrape top 100 subreddits for the last year
python reddit_scraper.py daily --top-subreddits 100 --start-date 2023-01-01 --end-date 2023-12-31

# Custom output directory and save interval
python reddit_scraper.py daily --top-subreddits 1000 -o my_reddit_data --save-interval 7
```

#### List Top Subreddits

```bash
# List top 100 subreddits (default)
python reddit_scraper.py list-subreddits

# List top 1000 subreddits
python reddit_scraper.py list-subreddits -n 1000
```

### Output Format

#### Basic Scrape Output

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

#### Daily Scrape Output

The daily scrape creates multiple ZIP files (one per save interval) in the output directory, plus a summary JSON file:

```json
{
  "subreddits": {
    "python": {
      "subreddit": "python",
      "daily_posts": {
        "2024-01-01": [
          { "id": "abc123", "title": "Top post of the day", "score": 5000, ... }
        ],
        "2024-01-02": [...]
      }
    }
  }
}
```

### Command Line Options

#### `scrape` Command

| Option | Description |
|--------|-------------|
| `-s, --subreddits` | List of subreddits to scrape (required) |
| `-n, --max-posts` | Maximum posts per subreddit (default: 10) |
| `-o, --output` | Output ZIP file path (default: reddit_data.zip) |
| `--before` | Unix timestamp - fetch posts before this time |
| `--after` | Unix timestamp - fetch posts after this time |
| `--no-comments` | Skip fetching comments for posts |
| `--rate-limit` | Delay between API requests in seconds (default: 1.0) |

#### `daily` Command

| Option | Description |
|--------|-------------|
| `-s, --subreddits` | List of subreddits (if not using --top-subreddits) |
| `--top-subreddits` | Use top N subreddits (max 1000) |
| `-n, --posts-per-day` | Top posts per day per subreddit (default: 10) |
| `--start-date` | Start date YYYY-MM-DD (default: 2005-06-23) |
| `--end-date` | End date YYYY-MM-DD (default: yesterday) |
| `-o, --output-dir` | Output directory (default: reddit_daily_data) |
| `--save-interval` | Save every N days (default: 30) |
| `--no-comments` | Skip fetching comments |
| `--rate-limit` | Delay between API requests (default: 1.0) |

#### `list-subreddits` Command

| Option | Description |
|--------|-------------|
| `-n, --count` | Number of subreddits to list (default: 100, max: 1000) |

### Note

The Pushshift API may have rate limits or availability issues. If you encounter errors, try increasing the `--rate-limit` value or reducing the number of posts to scrape.