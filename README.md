# EdgeOfICT Social Media Automation

Social media automation system for EdgeOfICT trading edge tracking software, now with a hosted Flask control panel for quote intake, queue management, approval, and publishing.

## Setup

```bash
# Create .env from template
cp .env.example .env

# Add your Anthropic API key to .env
# Used for quote extraction and AI post formatting
# ANTHROPIC_API_KEY=sk-ant-...

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Control Panel

The new web control panel is served by `app.py`.

```bash
# Start the hosted-style dashboard locally
python app.py
```

Open `http://localhost:5001` and sign in with:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`

For local-only testing you can set `DISABLE_AUTH=true`, but do not use that in production.

## Quick Start

```bash
# 1. Initialize database
python main.py init

# 2. Extract quotes from a document
python main.py extract docs/your_document.docx

# 3. Review and approve quotes
python main.py quotes           # List pending quotes
python main.py review-quotes    # Interactive approval

# 4. Generate posts from approved quotes
python main.py generate --days 7

# 5. Review and approve posts
python main.py posts            # List posts
python main.py review           # Interactive approval

# 6. Dry-run (test without posting)
python main.py dry-run --all

# 7. Post to Twitter (when ready)
python main.py post --next --dry-run  # Test first
python main.py post --next            # Actually post
```

## Hosted Deployment

- `render.yaml` is wired to the new control panel entrypoint: `gunicorn app:app`
- `Dockerfile` is included for generic platforms like Cloud Run
- Use external Postgres in production via `DATABASE_URL`; local SQLite is only a fallback for development
- See `DEPLOYMENT.md` for the free-tier hosting path

## Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize database and check config |
| `extract <file>` | Extract quotes from document |
| `quotes` | List quotes |
| `review-quotes` | Interactive quote approval |
| `approve-quote <id>` | Approve specific quote |
| `batch-approve` | Approve all quotes above threshold |
| `generate` | Generate posts from approved quotes |
| `posts` | List posts |
| `review` | Interactive post approval |
| `approve-post <id>` | Approve specific post |
| `schedule` | Show posting schedule |
| `dry-run` | Test posting without actually posting |
| `post` | Post to Twitter |
| `status` | Show system status |

## Supported Document Formats

- `.docx` - Word documents
- `.pdf` - PDF files
- `.txt` - Plain text

## Project Structure

```
/edgeofict-social
├── /core                   # Core functionality
│   ├── models.py           # Database models
│   ├── document_parser.py  # Document parsing
│   ├── content_extractor.py # Quote extraction
│   ├── approval_system.py  # Approval workflow
│   └── post_planner.py     # Post generation
├── /integrations
│   └── twitter_client.py   # Twitter API client
├── /config
│   └── settings.yaml       # Configuration
├── /data                   # SQLite database
├── /docs                   # Place ICT documents here
├── /tests                  # Test suite
└── main.py                 # CLI entry point
```

## Safety Features

- All posts require manual approval
- Dry-run mode for testing
- Confirmation prompts before posting
- No auto-posting without explicit command
- Password-protected web dashboard for hosted use
