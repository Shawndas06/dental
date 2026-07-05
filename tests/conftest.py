import os

os.environ["DATABASE_URL"] = "sqlite:///./test_dental_bot.db"
os.environ.setdefault("NATS_URL", "nats://localhost:4222")
os.environ.setdefault("CORE_API_URL", "http://test-core")
os.environ.setdefault("AI_ORCHESTRATOR_URL", "http://test-ai")
os.environ.setdefault("CRM_MOCK_URL", "http://test-crm")
os.environ["AI_MODE"] = "rules"
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["INTERNAL_SERVICE_TOKEN"] = "test-internal-token"
os.environ["DEBUG_API_ENABLED"] = "true"
os.environ["DEBUG_API_TOKEN"] = "test-admin-token"
os.environ.setdefault("NOTIFY_TELEGRAM_USERNAME", "")
