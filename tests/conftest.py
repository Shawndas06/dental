import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_dental_bot.db")
os.environ.setdefault("NATS_URL", "nats://localhost:4222")
os.environ.setdefault("CORE_API_URL", "http://test-core")
os.environ.setdefault("AI_ORCHESTRATOR_URL", "http://test-ai")
os.environ.setdefault("CRM_MOCK_URL", "http://test-crm")
os.environ.setdefault("AI_MODE", "rules")
