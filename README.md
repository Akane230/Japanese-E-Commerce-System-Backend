# Backend README

## Overview

This backend is a Django REST Framework service for a Japan-focused e-commerce platform. It serves user management, authentication, product catalog, cart persistence, orders, payments, inventory, and review workflows.

## Tech Stack

- Python 3.10+
- Django
- Django REST Framework
- MongoDB (MongoEngine)
- SQLite (local metadata)
- Redis (cache/session broker)
- Celery (asynchronous tasks)
- Cloudinary (media)
- JWT Authentication (`rest_framework_simplejwt`)

## API Structure

- `/api/auth/` - user registration, login, logout, profile, password, addresses, wishlist.
- `/api/auth/token/refresh/` - JWT refresh.
- `/api/products/` - listing, featured, search, product detail, admin CRUD.
- `/api/categories/` - category management.
- `/api/cart/` - cart endpoints.
- `/api/orders/` - create/list/detail/admin actions.
- `/api/payments/` - payment instructions/proof/admin confirmation/refund.
- `/api/inventory/` - inventory status (low stock, quantities).
- `/api/reviews/` - user reviews and admin moderation.
- `/api/health/` - health check endpoint.

## Setup

1. Create and activate virtual environment:

```bash
python -m venv .venv
source .venv/Scripts/activate # Windows
pip install -r myproject/requirements.txt
```

2. Copy `.env` from `myproject/.env` template as needed.
3. Configure database and env vars in `.env`:
   - `DJANGO_SECRET_KEY`
   - `DEBUG=True` default for local
   - `MONGO_URI` (e.g. `mongodb://localhost:27017/sakurashop`)
   - `REDIS_URL` (e.g. `redis://localhost:6379/0`)
   - `CLOUDINARY_*`, optional
   - `STRIPE_*` / `PAYPAL_*` optional
4. Run migrations and start:

```bash
cd myproject
python manage.py migrate
python manage.py runserver
```

## Environment & Config

- `config/settings.py` central config.
- Uses `decouple.config` for env loading.
- CORS origins controlled with `CORS_ALLOWED_ORIGINS`.

## Running

From `backend/myproject`:

```bash
python manage.py runserver 0.0.0.0:8000
```

- Developer monitor: `python manage.py runserver_plus` (optional with django-extensions)

## Notes

- Authentication uses JWT with refresh and blacklist.
- User model stores data in MongoDB with bcrypt password hashing.
- Uploads a resolved through Cloudinary storage if credentials are set.
