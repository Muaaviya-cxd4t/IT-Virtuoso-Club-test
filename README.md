# ITV Event Registration Portal

Flask event and team-registration website for IT Virtuoso Club, Department of Computer Science & Engineering.

## Features
- Dark-blue ITV/CSE branded responsive homepage
- Event highlight slider and event cards
- Event data and poster paths controlled by `events.json`
- Office bearer cards controlled by `members.json`
- Dynamic team registration with event-specific min/max members
- USN, phone and duplicate-member validation
- Atomic Supabase registration transaction
- Database-level duplicate team/USN protection
- Razorpay order creation and server-side payment verification
- Confirmation page and downloadable PDF
- Vercel-ready Flask entry point

## Run locally

```bash
python -m pip install -r requirements.txt
python -m flask --app app run --debug
```

Open `http://127.0.0.1:5000`.

## Environment

1. Copy `.env.example` to `.env`.
2. Put your **server-only Supabase secret key** in `SUPABASE_SECRET_KEY`.
3. Put your Razorpay test/live credentials in the Razorpay variables.
4. Generate a long random `FLASK_SECRET_KEY`.

Never commit `.env`.

## Supabase

Run `supabase_schema.sql` in the Supabase SQL Editor before using registrations. The SQL creates the tables, uniqueness constraints and the atomic `register_event_team` RPC used by Flask.

## Event posters

Use 1080x1080 Instagram-post artwork and place it in:

`app/static/images/events/`

Then set the path in `events.json`.

## Office bearers

Edit `members.json`. Replace the placeholder names/photos with the actual club team before launch.

## Deployment

Vercel uses `api/index.py` as the Python entry point. Add all environment variables from `.env` to the Vercel project settings instead of uploading `.env`.
