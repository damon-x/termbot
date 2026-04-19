"""
Prompts module for managing agent prompt templates.

Provides template loading, rendering, and management for
dynamic prompt generation based on context and tools.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class PromptTemplate:
    """Prompt template with variable substitution."""

    def __init__(self, name: str, content: str):
        """
        Initialize prompt template.

        Args:
            name: Template name
            content: Template content with {{variable}} placeholders
        """
        self.name = name
        self.content = content
        self._variables = self._extract_variables(content)

    def _extract_variables(self, content: str) -> set:
        """Extract variable names from template."""
        variables = set()
        start = 0
        while True:
            start = content.find("{{", start)
            if start == -1:
                break
            end = content.find("}}", start)
            if end == -1:
                break
            var_name = content[start + 2:end].strip()
            variables.add(var_name)
            start = end + 2
        return variables

    def render(self, **kwargs) -> str:
        """
        Render template with provided variables.

        Args:
            **kwargs: Variable values

        Returns:
            Rendered template
        """
        result = self.content
        for var_name, var_value in kwargs.items():
            placeholder = "{{" + var_name + "}}"
            result = result.replace(placeholder, str(var_value))
        return result

    def get_required_variables(self) -> set:
        """Get set of required variable names."""
        return self._variables.copy()


class PromptManager:
    """
    Manager for prompt templates.

    Loads and manages prompt templates from templates file.
    """

    def __init__(self, template_file: Optional[str] = None):
        """
        Initialize prompt manager.

        Args:
            template_file: Path to template file (defaults to templates.txt)
        """
        if template_file is None:
            # Find templates.txt in agent/prompts/
            base_dir = Path(__file__).parent
            template_file = base_dir / "templates.txt"

        self.template_file = Path(template_file)
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load templates from file."""
        if not self.template_file.exists():
            return

        with open(self.template_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse templates
        # Format: ::prompt\nname\n::content\ncontent\n::end
        sections = content.split("::prompt")
        for section in sections[1:]:  # Skip empty first section
            lines = section.strip().split("\n")
            if len(lines) < 3:
                continue

            name = lines[0].strip()
            if lines[1].strip() != "::content":
                continue

            # Content starts from line 2
            template_content = "\n".join(lines[2:]).strip()
            self._templates[name] = PromptTemplate(name, template_content)

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """
        Get a template by name.

        Args:
            name: Template name

        Returns:
            PromptTemplate or None if not found
        """
        return self._templates.get(name)

    def render(self, name: str, **kwargs) -> str:
        """
        Render a template by name.

        Args:
            name: Template name
            **kwargs: Variable values

        Returns:
            Rendered template

        Raises:
            ValueError: If template not found
        """
        template = self.get_template(name)
        if template is None:
            raise ValueError(f"Template '{name}' not found")
        return template.render(**kwargs)

    def has_template(self, name: str) -> bool:
        """Check if template exists."""
        return name in self._templates

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self._templates.keys())


class PromptBuilder:
    """
    Builder for constructing dynamic prompts.

    Provides convenient methods for building prompts
    with common sections like tools, terminal content, etc.
    """

    def __init__(self):
        """Initialize prompt builder."""
        self._sections: List[str] = []

    def add_section(self, title: str, content: str = "") -> None:
        """
        Add a section to the prompt.

        Args:
            title: Section title
            content: Section content
        """
        self._sections.append(f"## {title}")
        if content:
            self._sections.append(content)

    def add_tools(self, tools: List[Any]) -> None:
        """
        Add tools section to prompt.

        Args:
            tools: List of tool objects with schema property
        """
        self._sections.append("## Available Tools")
        for i, tool in enumerate(tools, 1):
            schema = tool.schema
            self._sections.append(f"{i}. {schema.name}")
            self._sections.append(f"   {schema.description}")
            if schema.parameters:
                for param in schema.parameters:
                    req = "required" if param.required else "optional"
                    self._sections.append(f"   - {param.name} ({param.type.value}, {req})")

    def add_terminal_content(self, content: str) -> None:
        """
        Add terminal content section.

        Args:
            content: Terminal output
        """
        self._sections.append("## Terminal Content")
        if content.strip():
            self._sections.append(f"```\n{content}\n```")
        else:
            self._sections.append("(empty)")

    def add_instructions(self, instructions: List[str]) -> None:
        """
        Add instructions section.

        Args:
            instructions: List of instruction strings
        """
        self._sections.append("## Instructions")
        for i, instruction in enumerate(instructions, 1):
            self._sections.append(f"{i}. {instruction}")

    def build(self) -> str:
        """
        Build the final prompt.

        Returns:
            Complete prompt string
        """
        return "\n\n".join(self._sections)

    def clear(self) -> None:
        """Clear all sections."""
        self._sections.clear()


# Global prompt manager instance
_default_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create global prompt manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = PromptManager()
    return _default_manager


def render_prompt(name: str, **kwargs) -> str:
    """
    Convenience function to render a prompt.

    Args:
        name: Template name
        **kwargs: Variable values

    Returns:
        Rendered prompt
    """
    return get_prompt_manager().render(name, **kwargs)
