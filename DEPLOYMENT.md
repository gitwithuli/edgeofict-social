# Deployment

## Recommended free-tier path

Use:

- Render free web service for the Flask app
- Neon Postgres free tier for persistent storage

This keeps the web app stateless and avoids relying on local SQLite files, which are not a good fit for hosted free web instances.

## Required environment variables

- `DATABASE_URL`
- `FLASK_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH` or `ADMIN_PASSWORD`
- `ANTHROPIC_API_KEY` for quote extraction and AI post formatting
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_SECRET`
- `TWITTER_BEARER_TOKEN`
- `FACEBOOK_PAGE_ID`
- `FACEBOOK_PAGE_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

## Render

1. Push this repo to GitHub.
2. Create a Neon database and copy its `DATABASE_URL`.
3. In Render, create a new Blueprint or Web Service from the repo.
4. Apply the environment variables above.
5. Deploy. Render will use `render.yaml` and expose `/healthz` for health checks.

## Cloud Run

If you want a more robust stateless runtime than free Render web instances, use the included `Dockerfile`:

```bash
gcloud run deploy edgeofict-social \
  --source . \
  --region us-east1 \
  --allow-unauthenticated
```

Set the same environment variables in Cloud Run and point `DATABASE_URL` at Neon Postgres.

## Password hashing

Generate a password hash with:

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('replace-me'))"
```

Use the output as `ADMIN_PASSWORD_HASH`.

## Automatic daily Stoic posting

Do not rely on an in-process scheduler inside the Render free web service. It sleeps when idle.

Use the included GitHub Actions workflow instead:

- File: `.github/workflows/daily-stoic.yml`
- Schedule: hourly
- Guard: only runs when local hour matches `AUTO_STOIC_HOUR`
- Default timezone: `America/New_York`
- Default hour: `9`

Add these GitHub repository secrets:

- `DATABASE_URL`
- `ANTHROPIC_API_KEY`
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_SECRET`
- `TWITTER_BEARER_TOKEN`
