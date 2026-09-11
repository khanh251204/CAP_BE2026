from app.ai.llm.groq_service import GroqService

# Singleton instance cho STT service
groq_service = GroqService()

__all__ = ["GroqService", "groq_service"]
