import os
import sys

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Load GLM_API_KEY from .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GLM_API_KEY="):
                os.environ["GLM_API_KEY"] = line.split("=", 1)[1].strip()
            elif line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()

import litellm

original_acompletion = litellm.acompletion

async def custom_acompletion(*args, **kwargs):
    # Clamp max_tokens for models that limit max_tokens
    if "max_tokens" in kwargs and kwargs["max_tokens"] and kwargs["max_tokens"] > 16384:
        kwargs["max_tokens"] = 8192
    if "max_completion_tokens" in kwargs and kwargs["max_completion_tokens"] and kwargs["max_completion_tokens"] > 16384:
        kwargs["max_completion_tokens"] = 8192
    
    # Remove unsupported reasoning_effort / extra_body params if present
    if "reasoning_effort" in kwargs:
        kwargs.pop("reasoning_effort", None)
    if "extra_body" in kwargs and isinstance(kwargs["extra_body"], dict):
        kwargs["extra_body"].pop("reasoning_effort", None)

    try:
        return await original_acompletion(*args, **kwargs)
    except Exception as e:
        err_msg = str(e)
        # If GLM 4.7 Flash is temporarily congested (1305 / 1302), seamlessly fall back to GLM 4.5 Flash
        if ("1305" in err_msg or "1302" in err_msg or "429" in err_msg or "该模型当前访问量过大" in err_msg) and "glm-4.7-flash" in str(kwargs.get("model", "")):
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["model"] = "custom_openai/glm-4.5-flash"
            return await original_acompletion(*args, **fallback_kwargs)
        raise

litellm.acompletion = custom_acompletion

if __name__ == "__main__":
    from litellm.proxy.proxy_cli import run_server
    sys.argv = [
        "litellm",
        "--config", os.path.join(os.path.dirname(__file__), "litellm_groq_config.yaml"),
        "--port", "4000"
    ]
    run_server()
