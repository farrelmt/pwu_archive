FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies:
# - gcc + libpq-dev   → psycopg2
# - nodejs + npm      → django-tailwind
# - cairo/pango/etc   → weasyprint
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libxml2 \
    libxslt1.1 \
    shared-mime-info \
    fonts-dejavu-core \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

EXPOSE 8000

#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD ["gunicorn", "archiveproject.wsgi:application", "--bind", "0.0.0.0:8000"]