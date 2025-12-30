# Event Ticketing & Reservation System

Quick-start guide for running the full stack (Gateway, Auth, Catalog, Booking, Inventory, Payment, Postgres, Redis) via Docker Compose.

## Prerequisites
- Docker and Docker Compose
- Stripe keys: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`

## use those key for stripe
<!-- 
STRIPE_SECRET_KEY="sk_test_51Shc7A0cnOHdddfoyiuqXQHHW44gg0pF6Y2qHBvD2OeElVuf0yZsRRPJlQmz6BWaXRpFy3IEKtlHvIo0jq8eyA5800TwCYE9mu"
STRIPE_PUBLISHABLE_KEY="pk_test_51Shc7A0cnOHdddfowoE5zsGqBf6xZeL2aS479B3xMpzS86noPWuSCB1oUWvMY1H7nuN3MR6eywa5nl4MHtYiIGTx00T9FPVtwT"
STRIPE_WEBHOOK_SECRET="whsec_e7463f2aafdcdc46ed4fd4b36ab5c5518d7ec565110948f5753a95381e32b832" 
-->

## Clone
```bash
git clone -b features --single-branch https://github.com/enkutatash/distributed_system.git
cd ds
```

## Environment
Create a `.env` in the project root (same level as `docker-compose.yml`):
```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Run
```bash
docker compose up -d --build
```
The containers install deps, run migrations, and start servers.

## Services & Ports
- Gateway/Auth (Django): http://localhost:8000
- Booking (Django): http://localhost:8001
- Catalog (Django + gRPC): http://localhost:8002
- Inventory (Django + gRPC): http://localhost:8003
- Payment (Django): http://localhost:8004
- Postgres: dpg-d591o8h5pdvs73a4ieag-a.oregon-postgres.render.com
- Redis: localhost:6379

## Common Commands
- View logs: `docker compose logs -f <service>` (e.g., `gateway`, `booking`, `catalog`, `inventory`, `payment`)
- Stop stack: `docker compose down`
- Reset data: `docker compose down -v` (removes Postgres/Redis volumes)

## Basic Flow (happy-path)
1) Register/login via Gateway: POST http://localhost:8000/register/ then /login/ to get Bearer token.
2) Create event (admin token) via Gateway → Catalog: POST http://localhost:8000/api/v1/events/.
3) List events (public): GET http://localhost:8000/api/v1/events/.
4) Create reservation (Bearer): POST http://localhost:8000/api/v1/reservations/ with `event_id`, `quantity`.
5) Create payment session: POST http://localhost:8000/api/v1/payments/ with `reservation_id`; redirect to returned `checkout_url`.
6) Stripe webhook calls Payment → Booking confirm; reservation becomes CONFIRMED if inventory sell succeeds.

## Notes
- The compose file points to a managed Postgres instance; adjust env vars if you want local Postgres.
- Ensure Stripe CLI or Dashboard is configured to send webhooks to `http://localhost:8004/api/v1/payments/webhook/` when running locally.