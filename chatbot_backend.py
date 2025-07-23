import os
import requests
from openai import OpenAI
from dotenv import load_dotenv
from openai import AzureOpenAI
load_dotenv()
import json

WEATHER_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
NEWS_API_KEY = os.getenv("NEWSAPI_API_KEY")
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version= os.getenv("AZURE_OPENAI_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )

deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
# API tools
def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    resp = requests.get(url).json()
    print(url)
    return {"temp": resp["main"]["temp"], "desc": resp["weather"][0]["description"]} if "main" in resp else {"error": "City not found"}

def get_news(topic):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={NEWS_API_KEY}"
    resp = requests.get(url).json()
    print(url)

    headlines = [art["title"] for art in resp.get("articles", [])[:3]]
    return {"headlines": headlines} if headlines else {"error": "No news found"}

def get_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    resp = requests.get(url).json()
    print(url)

    if isinstance(resp, list):
        return {"definition": resp[0]["meanings"][0]["definitions"][0]["definition"]}
    return {"error": "Definition not found"}

# LLM orchestration
def llm_chat(user_query):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_news",
                "description": "Get news headlines about a topic",
                "parameters": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": ["topic"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_definition",
                "description": "Get definition of an English word",
                "parameters": {
                    "type": "object",
                    "properties": {"word": {"type": "string"}},
                    "required": ["word"]
                }
            }
        }
    ]

    messages = [
        {"role": "system", "content": "Use tools to answer questions about weather, news, and word definitions. Always respond concisely from tool output."},
        {"role": "user", "content": user_query}
    ]

    response = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    assistant_msg = response.choices[0].message
    if getattr(assistant_msg, "tool_calls", None):

        messages.append(assistant_msg)  # ✅ Add the assistant message that triggers the tool call

        for call in assistant_msg.tool_calls:
            function_result = run_function_tool(call)            # Use json.loads(), not eval()
            messages.append({
                "role": "tool",
                "content": json.dumps(function_result),          # Use json.dumps()
                "tool_call_id": call.id
            })
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=tools,
        )
        assistant_msg = response.choices[0].message
        messages.append(assistant_msg)  # ✅ Important for tool-call response context

    assistant_reply = assistant_msg.content or "[No response]"
    print("LLM:", assistant_reply)
    return {"response": assistant_reply}

def run_function_tool(tool_call):
    import json
    func_name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)       # Use json.loads(), not eval()
    except json.JSONDecodeError:
        args = {}
    if func_name == "get_weather":
        return get_weather(args.get("city", ""))
    elif func_name == "get_news":
        return get_news(args.get("topic", ""))
    elif func_name == "get_definition":
        return get_definition(args.get("word", ""))
    return {"error": "Unknown function"}
