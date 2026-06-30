"""List the Gemini models available to your API key (and whether they support
function calling / tools).

Usage:
    GEMINI_API_KEY=your_key  python list_models.py
    # or set it in backend/.env
"""

import os


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        try:
            from app.config import settings  # picks up backend/.env

            api_key = settings.gemini_api_key
        except Exception:
            pass
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (env var or backend/.env) first.")

    from google import genai

    client = genai.Client(api_key=api_key)
    print(f"{'MODEL':45}  GENERATE  FUNCTION-CALLING(via generateContent)")
    for m in client.models.list():
        actions = set(getattr(m, "supported_actions", []) or [])
        gen = "generateContent" in actions
        # Function calling is exposed through generateContent on supported models.
        print(f"{m.name:45}  {'yes' if gen else '-':7}  {'yes' if gen else '-'}")


if __name__ == "__main__":
    main()
