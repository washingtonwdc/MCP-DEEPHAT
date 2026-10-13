"""
API Bridge OpenAI-Compatible para DeepHat AI.
Expõe endpoints /v1/chat/completions e /v1/models na porta 3095
para consumo nativo pelo DeepSeek Harness e qualquer cliente OpenAI.
"""

import asyncio
import json
import time
import uuid
import sys
from typing import AsyncGenerator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from client import DeepHatClient
from config import Config

app = Starlette()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = DeepHatClient()


def sanitize_messages(raw_messages):
    """Garante que todas as mensagens estejam com content em string pura."""
    sanitized = []
    for m in raw_messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", str(item)))
                else:
                    parts.append(str(item))
            content_str = " ".join(parts)
        else:
            content_str = str(content)
        sanitized.append({"role": role, "content": content_str})
    return sanitized


async def list_models(request: Request):
    """GET /v1/models"""
    data = [
        {
            "id": "deephat",
            "object": "model",
            "created": 1728864000,
            "owned_by": "kindo",
            "permission": [],
            "root": "deephat",
            "parent": None,
        },
        {
            "id": "DeepHat/DeepHat-V1-7B",
            "object": "model",
            "created": 1728864000,
            "owned_by": "kindo",
            "permission": [],
            "root": "DeepHat/DeepHat-V1-7B",
            "parent": None,
        },
    ]
    return JSONResponse({"object": "list", "data": data})


async def chat_completions(request: Request):
    """POST /v1/chat/completions"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": {"message": "Invalid JSON"}}, status_code=400)

    raw_messages = body.get("messages", [])
    model = body.get("model", "deephat")
    stream = body.get("stream", False)

    if not raw_messages:
        return JSONResponse({"error": {"message": "Nenhuma mensagem fornecida"}}, status_code=400)

    messages = sanitize_messages(raw_messages)
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    # 1. Modo Streaming (SSE)
    if stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                # Realiza inferência via cliente DeepHat
                res = await client.chat_web(messages)
                
                # Envia o conteúdo em chunks para fluidez no chat
                chunk_size = 6
                words = res.split(" ")
                for i in range(0, len(words), chunk_size):
                    part = " ".join(words[i : i + chunk_size])
                    if i + chunk_size < len(words):
                        part += " "
                    
                    data = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": part},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)

                # Chunk final
                done_data = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                err_data = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": f"\n❌ Erro no DeepHat: {str(e)}"},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # 2. Modo Non-Streaming (JSON padrão)
    try:
        content = await client.chat_web(messages)
        return JSONResponse(
            {
                "id": chat_id,
                "object": "chat.completion",
                "created": created_ts,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(str(messages)) // 4,
                    "completion_tokens": len(content) // 4,
                    "total_tokens": (len(str(messages)) + len(content)) // 4,
                },
            }
        )
    except Exception as e:
        return JSONResponse(
            {
                "error": {
                    "message": f"Erro DeepHat: {str(e)}",
                    "type": "server_error",
                }
            },
            status_code=500,
        )


app.routes.extend(
    [
        Route("/v1/models", list_models, methods=["GET"]),
        Route("/v1/chat/completions", chat_completions, methods=["POST"]),
        Route("/models", list_models, methods=["GET"]),
        Route("/chat/completions", chat_completions, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    port = 3095
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
