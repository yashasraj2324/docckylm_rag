# Re-export RAGPipeline so existing code (`from pipeline import RAGPipeline`)
# continues to work unchanged.
from pipeline.base import RAGPipeline

__all__ = ["RAGPipeline"]
