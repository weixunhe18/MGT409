# Project Conventions

## Python project setup

- Whenever starting a new Python project, create a virtual environment in the exact project folder before installing dependencies or running project code.
- Use the conventional folder name `.venv` and keep project dependencies isolated from other projects.
- Activate it before working:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

## OpenAI model calls

- Route OpenAI model calls through the Portkey API.
- Read the Portkey API key from the root `.env` file via an environment variable; never hard-code or commit the key.
- Use the model `gpt 5.6 luna` for OpenAI model calls.
- In API syntax, use the exact model ID `gpt-5.6-luna`.
- Use the Responses API pattern `client.responses.create(...)` for Python calls.
- Do not pass a `temperature` parameter to `gpt-5.6-luna`; its official model documentation does not list temperature as a supported control. Omit it rather than guessing or forcing a value.

### Reusable Python + Portkey template

Install the SDKs in the project environment:

```bash
pip install openai python-dotenv
```

Load the Portkey key from the root `.env` file and use Portkey's OpenAI-compatible endpoint:

```python
from pathlib import Path
import os

from dotenv import load_dotenv
from openai import OpenAI


# Adjust parents[1] if this file is nested at a different depth.
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

portkey_api_key = os.environ["PORTKEY_API_KEY"]

client = OpenAI(
    api_key=portkey_api_key,
    base_url="https://api.portkey.ai/v1",
    default_headers={"x-portkey-provider": "openai"},
)

response = client.responses.create(
    model="gpt-5.6-luna",
    input="Your prompt goes here.",
    reasoning={"effort": "none"},
    max_output_tokens=256,
    # Do not add temperature for gpt-5.6-luna.
)

print(response.output_text)
```

Keep API keys out of source files, logs, and commits. Prefer the Responses API for new projects; its basic Python form is `client.responses.create(model=..., input=...)`.

## Spending budget

- Total budget: `$40` over `6 weeks`.
- Track cumulative spending and the remaining budget whenever usage or cost information is available.
- Remind the user of spending progress regularly, including cumulative spend, remaining budget, elapsed time, and projected risk of exceeding the budget when it can be calculated.
