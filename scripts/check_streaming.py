#!/usr/bin/env python3
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

openai = OpenAI()

response = openai.responses.create(model="gpt-5-mini", input="Hello world", stream=True)
for chunk in response:
    print(chunk)
