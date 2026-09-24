import asyncio
import json
import logging
import os
import shutil
from typing import AsyncGenerator, Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

DEFAULT_MODELS = [
    {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)"},
    {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)"},
    {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Low)"},
    {"id": "gemini-3.7-flash-high", "name": "Gemini 3.7 Flash (High)"},
    {"id": "gemini-3.7-flash-medium", "name": "Gemini 3.7 Flash (Medium)"},
    {"id": "gemini-3.1-pro-high", "name": "Gemini 3.1 Pro (High)"},
    {"id": "gemini-3.1-pro-low", "name": "Gemini 3.1 Pro (Low)"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)"},
    {"id": "claude-opus-4-6-thinking", "name": "Claude Opus 4.6 (Thinking)"},
    {"id": "gpt-oss-120b-medium", "name": "GPT-OSS 120B (Medium)"},
]

def get_model_display_name(model_id: str) -> str:
    for m in DEFAULT_MODELS:
        if m["id"] == model_id:
            return m["name"]
    return model_id


class AgyClient:
    def __init__(self, bin_path: str = Config.AGY_BIN_PATH):
        self.bin_path = bin_path
        self._active_processes: Dict[int, asyncio.subprocess.Process] = {}
        self._cached_models: Optional[List[Dict[str, str]]] = None

    def is_agy_installed(self) -> bool:
        """Check if agy binary exists or is found in PATH."""
        if os.path.isfile(self.bin_path) and os.access(self.bin_path, os.X_OK):
            return True
        return shutil.which(self.bin_path) is not None

    async def list_models(self) -> List[Dict[str, str]]:
        """Fetch available models dynamically from `agy models`."""
        if self._cached_models:
            return self._cached_models

        try:
            proc = await asyncio.create_subprocess_exec(
                self.bin_path, "models",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            
            models = []
            lines = stdout.decode("utf-8", errors="replace").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("Fetching") or line.startswith("Usage:"):
                    continue
                # Typically tab-separated: model-id \t Display Name
                parts = line.split("\t")
                if len(parts) >= 2:
                    models.append({"id": parts[0].strip(), "name": parts[1].strip()})
                elif len(parts) == 1 and " " in parts[0]:
                    # Space separated fallback
                    subparts = parts[0].split(None, 1)
                    models.append({"id": subparts[0].strip(), "name": subparts[1].strip()})
                elif len(parts) == 1:
                    models.append({"id": parts[0].strip(), "name": parts[0].strip()})

            if models:
                self._cached_models = models
                return models
        except Exception as e:
            logger.warning(f"Could not dynamically query `agy models`: {e}")

        self._cached_models = DEFAULT_MODELS
        return DEFAULT_MODELS

    async def cancel_task(self, user_id: int) -> bool:
        """Cancel and terminate any running agy process for this user."""
        proc = self._active_processes.get(user_id)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.sleep(0.5)
                if proc.returncode is None:
                    proc.kill()
                logger.info(f"Terminated agy process for user {user_id}")
                return True
            except Exception as e:
                logger.error(f"Error terminating process for user {user_id}: {e}")
                return False
            finally:
                self._active_processes.pop(user_id, None)
        return False

    def is_task_running(self, user_id: int) -> bool:
        proc = self._active_processes.get(user_id)
        return proc is not None and proc.returncode is None

    async def stream_chat(
        self,
        user_id: int,
        prompt: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        project_dir: Optional[str] = None,
        sandbox: bool = False,
        auto_skip_permissions: bool = True
    ) -> AsyncGenerator[Dict, None]:
        """
        Execute `agy` with stream-json output and yield parsed events.
        """
        # Cancel any previous task for this user
        await self.cancel_task(user_id)

        cmd = [self.bin_path]

        if conversation_id:
            cmd.extend(["--conversation", conversation_id])

        if model:
            cmd.extend(["--model", model])

        if effort:
            cmd.extend(["--effort", effort])

        if project_dir and os.path.isdir(project_dir):
            cmd.extend(["--add-dir", project_dir])

        if sandbox:
            cmd.append("--sandbox")

        if auto_skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        cmd.extend([
            "--output-format", "stream-json",
            "-p", prompt
        ])

        working_cwd = project_dir if (project_dir and os.path.isdir(project_dir)) else None

        logger.info(f"Launching agy for user {user_id}: {' '.join(cmd[:6])}... in cwd={working_cwd}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_cwd
            )
            self._active_processes[user_id] = proc

            accumulated_response = ""
            new_conversation_id = conversation_id

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                    event_type = data.get("event")

                    if event_type == "init":
                        new_conversation_id = data.get("conversation_id")
                        yield {
                            "type": "init",
                            "conversation_id": new_conversation_id,
                            "cwd": data.get("init", {}).get("cwd"),
                            "permission_mode": data.get("init", {}).get("permission_mode")
                        }

                    elif event_type == "step_update":
                        step = data.get("step_update", {})
                        stype = step.get("step_type")
                        sstate = step.get("state")
                        delta = step.get("text_delta", "")
                        
                        if delta:
                            accumulated_response += delta

                        yield {
                            "type": "step_update",
                            "step_type": stype,
                            "state": sstate,
                            "text_delta": delta,
                            "accumulated": accumulated_response,
                            "conversation_id": step.get("conversation_id", new_conversation_id),
                            "duration": step.get("duration_seconds"),
                            "step_index": step.get("step_index"),
                            "usage": step.get("usage"),
                            "raw": step
                        }

                    elif event_type == "result":
                        res = data.get("result", {})
                        final_text = res.get("response", accumulated_response)
                        yield {
                            "type": "result",
                            "status": res.get("status", "SUCCESS"),
                            "response": final_text,
                            "conversation_id": res.get("conversation_id", new_conversation_id),
                            "duration": res.get("duration_seconds"),
                            "usage": res.get("usage"),
                            "num_turns": res.get("num_turns")
                        }

                except json.JSONDecodeError:
                    # Non-json line, log or yield as plain text line
                    logger.debug(f"Non-JSON agy output: {line_str}")
                    yield {
                        "type": "raw_output",
                        "text": line_str
                    }

            returncode = await proc.wait()
            if returncode != 0 and not accumulated_response:
                stderr_bytes = await proc.stderr.read()
                err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
                yield {
                    "type": "error",
                    "code": returncode,
                    "message": err_msg or f"agy exited with code {returncode}"
                }

        except asyncio.CancelledError:
            logger.info(f"Task stream cancelled for user {user_id}")
            raise
        except Exception as e:
            logger.error(f"Error running agy subprocess: {e}", exc_info=True)
            yield {
                "type": "error",
                "code": -1,
                "message": str(e)
            }
        finally:
            self._active_processes.pop(user_id, None)

agy_client = AgyClient()
