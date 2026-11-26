"""Prompt3A: offline calculation only. No chatbot integration or source approval."""
from .engine import NutritionEngine
from .trust import KnowledgeCatalog, TrustStore, NutritionError

__all__=['NutritionEngine','KnowledgeCatalog','TrustStore','NutritionError']
