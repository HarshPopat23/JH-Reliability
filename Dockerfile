FROM python:3.12-slim
WORKDIR /app
COPY requirements-lock.txt pyproject.toml ./
COPY README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements-lock.txt && pip install --no-cache-dir --no-deps .
RUN useradd --create-home lab
USER lab
EXPOSE 8000
CMD ["aclab", "serve", "--host", "0.0.0.0", "--port", "8000"]
