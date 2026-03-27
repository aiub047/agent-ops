"""
Agent Definition Repository.

Responsible for locating, reading, and validating agent definition YAML files
from the agent-definition directory. Raises domain exceptions on failures so
that callers never have to deal with raw I/O or YAML exceptions.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.core.exceptions import AgentDefinitionNotFoundError, AgentDefinitionParseError
from app.core.logging import get_logger
from app.schemas.agent_definition import AgentDefinition

logger = get_logger(__name__)


class AgentDefinitionRepository:
    """
    Reads and validates agent definition YAML files from the filesystem.

    Args:
        definition_dir: Absolute or relative path to the agent-definition directory.
    """

    _YAML_SUFFIXES = (".yaml", ".yml")
    _AGENT_FILE_PATTERN = ".agent.yaml"

    def __init__(self, definition_dir: str | Path) -> None:
        self._dir = Path(definition_dir).resolve()

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, name: str) -> AgentDefinition:
        """
        Load and validate the agent definition identified by *name*.

        Tries ``<name>.agent.yaml`` first, then ``<name>.yaml`` / ``<name>.yml``.

        Args:
            name: Agent definition filename without extension, e.g.
                  ``'senior-software-architect'``.

        Returns:
            AgentDefinition: Validated Pydantic model.

        Raises:
            AgentDefinitionNotFoundError: If no matching file is found.
            AgentDefinitionParseError: If the file cannot be parsed or fails validation.
        """
        path = self._resolve_path(name)
        return self._load(path)

    def list_definitions(self) -> list[str]:
        """
        Return the names of all agent definition files in the directory.

        Returns:
            list[str]: Sorted list of definition names (without extensions).
        """
        if not self._dir.exists():
            logger.warning("Agent definition directory not found: %s", self._dir)
            return []

        names: list[str] = []
        for path in sorted(self._dir.iterdir()):
            if path.is_file() and path.suffix in self._YAML_SUFFIXES:
                names.append(self._strip_suffix(path.name))
        return names

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_path(self, name: str) -> Path:
        candidates = [
            self._dir / f"{name}.agent.yaml",
            self._dir / f"{name}.yaml",
            self._dir / f"{name}.yml",
        ]
        for path in candidates:
            if path.exists():
                logger.debug("Resolved definition '%s' → %s", name, path)
                return path
        raise AgentDefinitionNotFoundError(
            f"No agent definition file found for '{name}' in {self._dir}"
        )

    def _load(self, path: Path) -> AgentDefinition:
        logger.info("Loading agent definition from %s", path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise AgentDefinitionParseError(
                f"Failed to read or parse YAML file '{path.name}': {exc}"
            ) from exc

        try:
            return AgentDefinition.model_validate(raw)
        except ValidationError as exc:
            raise AgentDefinitionParseError(
                f"Agent definition '{path.name}' failed schema validation: {exc}"
            ) from exc

    @staticmethod
    def _strip_suffix(filename: str) -> str:
        """Remove .agent.yaml, .yaml, or .yml suffix."""
        for suffix in (".agent.yaml", ".agent.yml", ".yaml", ".yml"):
            if filename.endswith(suffix):
                return filename[: -len(suffix)]
        return filename

