"""
Utility functions for file tools.

Provides common helper functions for file operations including
path normalization, encoding detection, and file validation.
"""
import os
from pathlib import Path
from typing import Optional, Tuple


def normalize_path(file_path: str) -> str:
    """
    Normalize a file path to absolute path.

    Expands user directory (~) and environment variables,
    then converts to absolute path.

    Args:
        file_path: Path to normalize

    Returns:
        Normalized absolute path
    """
    # Expand ~ to user home directory
    expanded = os.path.expanduser(file_path)

    # Convert to absolute path
    absolute = os.path.abspath(expanded)

    # Normalize path (resolve .. and .)
    return os.path.normpath(absolute)


def add_line_numbers(content: str, start_line: int = 1) -> str:
    """
    Add line numbers to file content.

    Args:
        content: File content
        start_line: Starting line number (default: 1)

    Returns:
        Content with line numbers prefixed
    """
    lines = content.split('\n')
    numbered_lines = []

    for i, line in enumerate(lines, start=start_line):
        # Format: "    1→line content" (4 digit padding + arrow)
        numbered_lines.append(f"{i:4d}→{line}")

    return '\n'.join(numbered_lines)


def read_file_range(
    file_path: str,
    offset: int = 0,
    limit: Optional[int] = None
) -> Tuple[str, int, int]:
    """
    Read a specific range of lines from a file.

    Args:
        file_path: Path to the file
        offset: Line number to start from (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        Tuple of (content, lines_read, total_lines)

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            total_lines = len(all_lines)

        # Apply offset and limit
        start = offset
        end = start + limit if limit else total_lines

        # Clamp to file bounds
        start = max(0, min(start, total_lines))
        end = max(start, min(end, total_lines))

        selected_lines = all_lines[start:end]
        content = ''.join(selected_lines)

        return content, len(selected_lines), total_lines

    except FileNotFoundError:
        raise
    except Exception as e:
        raise IOError(f"Failed to read file: {str(e)}")


def detect_file_encoding(file_path: str) -> str:
    """
    Detect file encoding.

    Args:
        file_path: Path to the file

    Returns:
        Detected encoding (default: utf-8)
    """
    try:
        import chardet

        with open(file_path, 'rb') as f:
            raw_data = f.read(1024)  # Read first 1KB for detection

        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8')

        # Normalize encoding names
        if encoding:
            encoding = encoding.lower().replace('-', '')

        return encoding or 'utf-8'

    except ImportError:
        # chardet not available, default to utf-8
        return 'utf-8'
    except Exception:
        return 'utf-8'


def is_binary_file(file_path: str) -> bool:
    """
    Check if a file is binary.

    Args:
        file_path: Path to the file

    Returns:
        True if file appears to be binary
    """
    # Binary file extensions
    binary_extensions = {
        '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
        '.mp3', '.mp4', '.wav', '.avi', '.mov',
        '.zip', '.tar', '.gz', '.rar', '.7z',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
    }

    ext = Path(file_path).suffix.lower()
    if ext in binary_extensions:
        return True

    # Check content if file exists and is readable
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)

        # If null bytes are present, likely binary
        if b'\x00' in chunk:
            return True

        # Check if high ratio of non-text bytes
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        non_text = sum(1 for byte in chunk if byte not in text_chars)

        # If more than 30% non-text characters, consider it binary
        return non_text / len(chunk) > 0.3 if chunk else False

    except Exception:
        return False


def validate_file_path(file_path: str, must_exist: bool = False) -> Tuple[str, bool]:
    """
    Validate and normalize a file path.

    Args:
        file_path: Path to validate
        must_exist: Whether the file must exist

    Returns:
        Tuple of (normalized_path, is_valid)

    Raises:
        ValueError: If path is invalid and must_exist is True
    """
    if not file_path or not file_path.strip():
        raise ValueError("File path cannot be empty")

    normalized = normalize_path(file_path)

    if must_exist:
        if not os.path.exists(normalized):
            raise ValueError(f"File does not exist: {normalized}")

    return normalized, True


def find_similar_files(file_path: str, max_results: int = 5) -> list:
    """
    Find files with similar names in the same directory.

    Args:
        file_path: Path to the file
        max_results: Maximum number of results to return

    Returns:
        List of similar file paths
    """
    try:
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path).lower()

        if not os.path.exists(dir_path):
            return []

        # Get all files in directory
        files = []
        for f in os.listdir(dir_path):
            full_path = os.path.join(dir_path, f)
            if os.path.isfile(full_path):
                files.append(full_path)

        # Simple similarity check (contains file name)
        similar = []
        for f in files:
            if file_name in f.lower() or f.lower() in file_name:
                if f != file_path:
                    similar.append(f)

        return similar[:max_results]

    except Exception:
        return []


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 KB", "2.3 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def ensure_directory_exists(file_path: str) -> None:
    """
    Ensure the parent directory of a file path exists.

    Args:
        file_path: Path to the file

    Raises:
        OSError: If directory cannot be created
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
