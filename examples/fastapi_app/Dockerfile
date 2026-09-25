FROM python:3.13-slim
WORKDIR /app

# Install packages
RUN pip install --no-cache-dir bcrypt dotenv py-auth-fastapi py-auth-sqlalchemy uvicorn

# Create the non-root user with a home directory
RUN useradd -m app

# Copy source code AND give ownership to the app user
COPY --chown=app:app . /app

# Expose the application port
EXPOSE 8000

# Switch to the non-root user for execution
USER app

# Start the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
