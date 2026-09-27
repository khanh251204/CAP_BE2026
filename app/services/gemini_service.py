from app.ai.llm.gemini_service import GeminiService

# Singleton instance cho Gemini STT service
gemini_service = GeminiService()


def gemini_transcribe(file_path: str) -> str:
    """Helper function gọi transcribe từ singleton service."""
    return gemini_service.transcribe(file_path)


__all__ = ["GeminiService", "gemini_service", "gemini_transcribe"]
