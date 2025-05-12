import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


def ask_chatgpt(prompt, *, system_prompt=None, model="gpt-4.1-mini", response_format=None):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    if response_format:
        response = client.chat.completions.create(model=model, messages=messages, response_format=response_format)
    else:
        response = client.chat.completions.create(model=model, messages=messages)

    return response.choices[0].message.content.strip()
