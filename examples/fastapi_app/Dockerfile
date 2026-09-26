FROM python:3.13-slim

WORKDIR /app

# Install packages
RUN pip install --no-cache-dir bcrypt dotenv py-auth-fastapi py-auth-sqlalchemy asyncpg

# Create non-root user
RUN useradd -m app

# Copy ONLY the 'app' folder into our container's /app directory
COPY --chown=app:app app /app/

EXPOSE 8000
USER app

# Run FastAPI directly since main.py is now inside /app/main.py
CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]