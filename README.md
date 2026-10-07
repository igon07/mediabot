# mediabot

A Discord bot that fetches and displays user-saved images from an art community site. A companion downloader script mirrors an account's saved images to local disk, and the bot serves that archive through an interactive menu.

> **Heads up: this project is self-hosted only.** It currently runs on my own machine against a local disk. There is no hosted version and no cloud storage, and it isn't set up to be deployed anywhere else out of the box.

## Files

| File | What it does |
|---|---|
| `main.py` | The downloader. Pulls saved images from the site's REST API into a local archive. |
| `danbot.py` | The Discord bot. Serves files from the archive and tracks usage. |
| `db.py` | Database functions (SQLite) shared by the downloader and the bot. |
| `fillingoldscript.py` | One-time backfill that fetches tag and score data for items downloaded before database logging existed. |
| `extra.py` | Scratch/testing file. Not needed to run anything. |
| `.gitignore` | Keeps `.env`, the database, logs, and archive files out of the repo. |

### What the downloader does

- Handles parent/child/sibling post families recursively and groups them into family subfolders
- Skips already-downloaded posts via a `downloaded_ids.json` archive
- Converts animated (ugoira) posts to GIFs using the frame timing in the bundled zip JSON
- Logs everything to SQLite as it goes

### What the bot does

- `$menu` opens an interactive button-based menu (tags, files, stats). Commands are prefix-based, not slash commands.
- Browse by tag category, sort by request count, and send single files or whole multi-file posts
- Stats embed with total files, total requests, and total archive size

## Requirements

- Python 3
- A Discord bot token
- An account (with API key) on the source site
- A local disk or folder to store the archive
- Libraries: `discord.py`, `requests`, `Pillow`, `python-dotenv`

```bash
pip install discord.py requests Pillow python-dotenv
```

## Configuration: you need your own `.env`

Nothing works without a `.env` file in the project root. It is **not** included in the repo (it's in `.gitignore`), so anyone who wants to run this has to create their own with their own credentials and paths.

```env
# Downloader (main.py)
MAINURL=https://your-source-site.example   # base URL of the site's API
MYLOGIN=your_username                      # used as both username and login
MYAPI=your_api_key
THEPATH=/path/to/your/archive/disk         # where images are saved (the bot reads from here too)
ARCHPATH=/path/to/downloaded_ids.json      # dedup archive file; use an absolute path

# Discord bot (danbot.py)
BOTTOKEN=your_discord_bot_token
THEPATH=/path/to/your/archive/disk         # same value as above
```

Notes:

- `THEPATH` is the location of the disk/folder images are saved to. It must exist on the machine running the scripts, and both the downloader and the bot must point at the same place. It only needs to appear once in the `.env`.
- `ARCHPATH` should be an absolute path, otherwise deduplication can silently fail when the working directory changes.
- `MAINURL`: the downloader appends the slash itself when building API requests, so leave off the trailing slash.
- Keep `.env` private. Never commit it.

## Running it

The downloader and the bot run as **separate processes**.

```bash
# 1. Download / update the archive (also records total archive size in the DB)
python main.py

# 2. (One time, for pre-existing content) backfill tags and scores
python fillingoldscript.py

# 3. Start the Discord bot
python danbot.py
```

Run the downloader at least once before using the bot's stats. The `meta` table that holds total size is created by the downloader, not the bot.

The bot uses `$` as its command prefix. To change it, edit the `command_prefix` argument where the bot is created in `danbot.py` (`commands.Bot(command_prefix='$', ...)`). It also needs the message content and members intents enabled in the Discord developer portal, and it writes logs to `discord.log`.

## Database

SQLite (`mediabot.db`, not committed). Main tables:

- `files`: `id` is the numeric post ID (no extension), `filepath` is the full ready-to-send path, `score` is the max across the post's family
- `requests`: one row per file/folder sent through the bot
- `tags` / `post_tags`: many-to-many, with tag category; tags are aggregated across every downloadable member of a family
- `meta`: key-value store (e.g. total archive size), needed because the bot and downloader are separate processes

## Known limitations

- Self-hosted only; requires local disk access and a personal `.env`
- Tag sorting by requests and category filtering can't be combined in the tag list view
- Family resync is not automatic (API cost scales with archive size); an opt-in resync flag is planned

## Roadmap

- REST API layer (FastAPI) for the archive data
- Opt-in family resync flag
- Web dashboard on top of the API
- More polish and features for the Discord menu system
