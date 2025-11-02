Sure! Here’s a comprehensive `README.md` for your **`alx_travel_app_0x00`** project, reflecting what you’ve done so far (project setup, models, serializers, migrations, and seeding). You can place this in the project root.

---

````markdown
# ALX Travel App 0x00

## Overview
ALX Travel App is a Django-based web application for managing travel listings, bookings, and reviews. This iteration focuses on:

- Django project setup with REST API and Swagger documentation
- MySQL (or SQLite for development) database configuration
- Models for Listings, Bookings, and Reviews
- Serializers for API data representation
- Seeder command to populate sample listings data

---

## Project Setup

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/alx_travel_app_0x00.git
cd alx_travel_app_0x00
````

### 2. Create a virtual environment and activate

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

Example `.env` for MySQL:

```
SECRET_KEY=your-secret-key
DEBUG=True
DB_NAME=alx_travel
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
```

> If MySQL is not installed, you can temporarily use SQLite by updating `DATABASES` in `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

---

## Database Models

### Listing

* `title` (CharField)
* `description` (TextField)
* `price_per_night` (DecimalField)
* `location` (CharField)
* `created_at` (DateTimeField)

### Booking

* `listing` (ForeignKey to Listing)
* `user` (ForeignKey to Django User)
* `check_in` (DateField)
* `check_out` (DateField)
* `guests` (PositiveIntegerField)
* `created_at` (DateTimeField)

### Review

* `listing` (ForeignKey to Listing)
* `user` (ForeignKey to Django User)
* `rating` (1-5)
* `comment` (TextField)
* `created_at` (DateTimeField)
* Unique constraint on (`listing`, `user`) to prevent duplicate reviews

---

## API Serializers

* `ListingSerializer` → Serializes all Listing fields
* `BookingSerializer` → Serializes all Booking fields

---

## Running Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

This will create tables for:

* Django built-in apps: auth, admin, sessions, contenttypes
* Listings app: Listing, Booking, Review

---

## Seeding Sample Data

Run the custom management command to populate sample listings:

```bash
python manage.py seed
```

Check in Django shell:

```python
from listings.models import Listing
for l in Listing.objects.all():
    print(l.title, l.location, l.price_per_night)
```

---

## API Documentation

Swagger documentation is available at:

```
http://127.0.0.1:8000/swagger/
```

---

## Background Tasks with Celery

1. Install dependencies: `pip install celery django-celery-beat`
2. Ensure RabbitMQ is installed and running.
3. Start Celery worker: `celery -A alx_travel_app worker -l info`
4. Booking creation triggers an asynchronous email notification.
