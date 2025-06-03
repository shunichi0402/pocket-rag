import os
from typing import Optional, Dict, List, Any
from openai import OpenAI

api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
client: OpenAI = OpenAI(api_key=api_key)


def ask_chatgpt(prompt: str, *, system_prompt: Optional[str] = None, model: str = "gpt-4.1-mini", response_format: Optional[Dict[str, str]] = None) -> str:
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Assuming response_format is a simple dict like {"type": "json_object"}
    # The actual type for response_format in openai library might be more complex
    # For a more precise annotation, one might need to refer to openai's type stubs or documentation.
    if response_format:
        response: Any = client.chat.completions.create(model=model, messages=messages, response_format=response_format)
    else:
        response: Any = client.chat.completions.create(model=model, messages=messages)

    content: Optional[str] = response.choices[0].message.content
    return content.strip() if content else ""
