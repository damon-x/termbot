"""
Unit tests for SkillManager.

Tests for skill discovery, loading, and hot-reload functionality.
"""
import tempfile
import unittest
from pathlib import Path

from agent.skills import SkillManager


class TestSkillManagerEmptyDir(unittest.TestCase):
    """Test skill manager with empty directory."""

    def test_empty_dir(self):
        """Test skill manager returns empty list for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SkillManager(Path(tmpdir))
            self.assertEqual(manager.list_skill_basics(), [])


class TestSkillManagerLoad(unittest.TestCase):
    """Test skill loading from directory."""

    def test_load_skill(self):
        """Test skill loading from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test skill
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
---

# Test

This is a test skill.
""")

            manager = SkillManager(Path(tmpdir))

            # Test list_skill_basics
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 1)
            self.assertEqual(basics[0]["name"], "test")
            self.assertEqual(basics[0]["description"], "Test skill")

            # Test get_skill_by_name
            skill = manager.get_skill_by_name("test")
            self.assertIsNotNone(skill)
            self.assertEqual(skill.name, "test")
            self.assertEqual(skill.description, "Test skill")
            self.assertEqual(skill.content, "# Test\n\nThis is a test skill.")
            self.assertEqual(skill.path, skill_dir)


class TestSkillManagerHotReload(unittest.TestCase):
    """Test hot-reload functionality."""

    def test_hot_reload(self):
        """Test hot-reload functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"

            # Initial content
            skill_md.write_text("""---
name: test
description: Original
---

Original content
""")

            manager = SkillManager(Path(tmpdir))

            # First load
            skill1 = manager.get_skill_by_name("test")
            self.assertIsNotNone(skill1)
            self.assertEqual(skill1.description, "Original")
            self.assertEqual(skill1.content, "Original content")

            # Modify file
            skill_md.write_text("""---
name: test
description: Modified
---

Modified content
""")

            # Second load (hot-reload)
            skill2 = manager.get_skill_by_name("test")
            self.assertIsNotNone(skill2)
            self.assertEqual(skill2.description, "Modified")
            self.assertEqual(skill2.content, "Modified content")


class TestSkillManagerMissingSkillMd(unittest.TestCase):
    """Test skill manager ignores directories without SKILL.md."""

    def test_missing_skill_md(self):
        """Test skill manager ignores directories without SKILL.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "incomplete-skill"
            skill_dir.mkdir()
            # No SKILL.md created

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 0)


class TestSkillManagerInvalidFrontmatter(unittest.TestCase):
    """Test skill manager handles invalid YAML frontmatter."""

    def test_invalid_frontmatter(self):
        """Test skill manager handles invalid YAML frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "invalid-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
invalid yaml [[[
---
""")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 0)


class TestSkillManagerMissingRequiredFields(unittest.TestCase):
    """Test skill manager requires name and description."""

    def test_missing_required_fields(self):
        """Test skill manager requires name and description."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Missing description
            skill_dir1 = Path(tmpdir) / "skill-no-desc"
            skill_dir1.mkdir()
            (skill_dir1 / "SKILL.md").write_text("""---
name: test
---
""")

            # Missing name
            skill_dir2 = Path(tmpdir) / "skill-no-name"
            skill_dir2.mkdir()
            (skill_dir2 / "SKILL.md").write_text("""---
description: Test
---
""")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 0)


class TestSkillManagerSubdirectories(unittest.TestCase):
    """Test skill manager detects optional subdirectories."""

    def test_subdirectories(self):
        """Test skill manager detects optional subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()

            # Create subdirectories
            (skill_dir / "scripts").mkdir()
            (skill_dir / "references").mkdir()
            # assets not created

            (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
---
""")

            manager = SkillManager(Path(tmpdir))
            skill = manager.get_skill_by_name("test")

            self.assertIsNotNone(skill)
            self.assertIsNotNone(skill.scripts_dir)
            self.assertEqual(skill.scripts_dir, skill_dir / "scripts")
            self.assertIsNotNone(skill.references_dir)
            self.assertEqual(skill.references_dir, skill_dir / "references")
            self.assertIsNone(skill.assets_dir)


class TestSkillManagerNonDirItems(unittest.TestCase):
    """Test skill manager ignores non-directory items."""

    def test_non_dir_items(self):
        """Test skill manager ignores non-directory items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file (not a directory)
            (Path(tmpdir) / "not-a-dir.txt").write_text("test")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 0)


class TestSkillManagerGetSkillNotFound(unittest.TestCase):
    """Test get_skill_by_name returns None for non-existent skill."""

    def test_get_skill_not_found(self):
        """Test get_skill_by_name returns None for non-existent skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SkillManager(Path(tmpdir))
            skill = manager.get_skill_by_name("nonexistent")
            self.assertIsNone(skill)


class TestSkillManagerDisableEnable(unittest.TestCase):
    """Test skill disable/enable functionality."""

    def test_skill_disabled_by_default(self):
        """Test skills are enabled by default (when enabled field is missing)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
---
# Test
This is a test skill.
""")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 1)
            self.assertEqual(basics[0]["name"], "test")

    def test_skill_explicitly_enabled(self):
        """Test skills with enabled: true are listed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
enabled: true
---
# Test
This is a test skill.
""")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 1)
            self.assertEqual(basics[0]["name"], "test")

    def test_skill_disabled(self):
        """Test skills with enabled: false are not listed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
enabled: false
---
# Test
This is a test skill.
""")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()
            self.assertEqual(len(basics), 0)

    def test_skill_enabled_field_parsing(self):
        """Test that enabled field is correctly parsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()

            # Create skill with enabled: false
            (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
enabled: false
---
# Test
This is a test skill.
""")

            manager = SkillManager(Path(tmpdir))
            skill = manager.get_skill_by_name("test")

            self.assertIsNotNone(skill)
            self.assertEqual(skill.name, "test")
            self.assertFalse(skill.enabled)

    def test_mix_enabled_disabled_skills(self):
        """Test that only enabled skills are listed when mixed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create enabled skill
            skill_dir1 = Path(tmpdir) / "enabled-skill"
            skill_dir1.mkdir()
            (skill_dir1 / "SKILL.md").write_text("""---
name: enabled-skill
description: Enabled skill
enabled: true
---
# Enabled
""")

            # Create disabled skill
            skill_dir2 = Path(tmpdir) / "disabled-skill"
            skill_dir2.mkdir()
            (skill_dir2 / "SKILL.md").write_text("""---
name: disabled-skill
description: Disabled skill
enabled: false
---
# Disabled
""")

            # Create skill without enabled field (should be enabled by default)
            skill_dir3 = Path(tmpdir) / "default-skill"
            skill_dir3.mkdir()
            (skill_dir3 / "SKILL.md").write_text("""---
name: default-skill
description: Default skill
---
# Default
""")

            manager = SkillManager(Path(tmpdir))
            basics = manager.list_skill_basics()

            # Should only list enabled-skill and default-skill
            self.assertEqual(len(basics), 2)
            skill_names = [s["name"] for s in basics]
            self.assertIn("enabled-skill", skill_names)
            self.assertIn("default-skill", skill_names)
            self.assertNotIn("disabled-skill", skill_names)
