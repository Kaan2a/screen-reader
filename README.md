# Screen Reader & Commander

A Python development prototype that combines spoken commands, local language-model reasoning and visual understanding to explore Windows desktop and browser automation.

**Status:** Work in progress. The repository contains the application code, but model weights are separate and end-to-end operation needs validation on a configured Windows machine.

## How it works

1. **Listen:** `faster-whisper` transcribes microphone audio; the default language is Turkish.
2. **Interpret:** A local GGUF language model, loaded through `llama-cpp-python`, converts the command into an action, target and parameters.
3. **Route:** The orchestrator selects a media API, Windows UI automation, browser automation or visual interaction.
4. **Locate and act:** Playwright/CDP and `pywinauto` handle supported interfaces; Florence-2 searches screenshots for text or visual targets.
5. **Show status:** A CustomTkinter window displays the current state and provides an active/passive toggle.

## Main components

| Component | File |
| --- | --- |
| Entry point and model configuration | [main.py](main.py) |
| Command orchestration | [src/core/orchestrator.py](src/core/orchestrator.py) |
| Structured command parsing | [src/core/llm_brain.py](src/core/llm_brain.py) |
| Speech recognition | [src/voice/stt_engine.py](src/voice/stt_engine.py) |
| Visual grounding and OCR | [src/vision/florence_engine.py](src/vision/florence_engine.py) |
| Windows interaction | [src/os_control/winauto_layer.py](src/os_control/winauto_layer.py) |
| Browser interaction | [src/web/playwright_layer.py](src/web/playwright_layer.py) |
| Media command routing | [src/api_control/api_layer.py](src/api_control/api_layer.py) |

## Development setup

The code targets **Windows and Python 3.12+**. A microphone and a compatible desktop browser are needed for the corresponding features.

From PowerShell:

```powershell
git clone https://github.com/Kaan2a/screen-reader.git
cd screen-reader
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Before starting, configure `CONFIG` in [main.py](main.py):

- `llm_model_path`: point to a compatible local GGUF model. The default path is `models/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf`; that file is not included.
- `whisper_model`: choose the speech model to load. The default is `large-v3-turbo`.
- `florence_model`: the default is `microsoft/Florence-2-base`.
- `language` and `cdp_port`: the defaults are `tr` and `9222`.

Speech and vision models may download on first use. Model availability, dependency compatibility and hardware requirements must be checked in the target environment.

```powershell
python main.py
```

The application attempts to connect to or launch a compatible browser with CDP enabled. Commands can move the pointer and click interface elements, so development trials should use a separate test browser profile and a controlled desktop.

## Current limitations

- Dependencies are not pinned; installation and model integration still need reproducible environment testing.
- The language-model layer contains limited mock responses when a model is unavailable. These do not validate actual model inference.
- Browser selectors and media integrations cover a limited set of actions.
- There is no documented latency benchmark, accessibility evaluation or complete automated integration test suite.
- The project is a desktop automation experiment; it has not been validated as a replacement for established accessibility software.

## Next development steps

- Record a tested Windows setup and dependency versions.
- Add a short demonstration with explicit input commands and outcomes.
- Separate mock checks from real model and desktop integration checks.
- Add an action confirmation/preview option before executing commands.

The implementation uses **Florence-2, faster-whisper and a local LLM**. Earlier YOLO/EasyOCR descriptions have been superseded by the current code.

