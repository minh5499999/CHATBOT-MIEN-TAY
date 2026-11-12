"""Chatbot truy hồi kiến thức và trích xuất/template qua LangChain, không LLM sinh."""
import os

# Không gửi trace/câu hỏi ra dịch vụ ngoài, kể cả khi máy bật LangSmith sẵn.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
