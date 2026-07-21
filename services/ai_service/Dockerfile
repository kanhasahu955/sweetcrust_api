# Build from backend_v2/:
#   docker build -f services/ai_service/Dockerfile -t sweetcrust-ai .
FROM python:3.12-slim
WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "sqlmodel>=0.0.22" \
    "sqlalchemy>=2.0.36" "greenlet>=3.0.0" "pymysql>=1.1.1" "asyncmy>=0.2.9" "cryptography>=43.0.0" \
    "pydantic-settings>=2.6.0" "python-jose[cryptography]>=3.3.0" \
    "passlib[bcrypt]>=1.7.4" "bcrypt>=4.0.1,<4.1" "redis>=5.0.0" \
    "httpx>=0.27.0" "python-multipart>=0.0.12" "email-validator>=2.2.0" \
    "twilio>=9.0.0" "langchain>=0.3.0" "langchain-core>=0.3.0" \
    "langchain-community>=0.3.0" "langchain-groq>=0.2.0" \
    "langchain-openai>=0.2.0" "langgraph>=0.2.0" "rank-bm25>=0.2.2"

COPY package ./package
COPY services/ai_service ./services/ai_service

ENV PYTHONPATH=/workspace:/workspace/services/ai_service
ENV PORT=8006
EXPOSE 8006
WORKDIR /workspace/services/ai_service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
