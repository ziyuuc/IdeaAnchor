#!/usr/bin/env python3
"""Keep the title, abstract, main text, and references of each paper Markdown file; drop the rest.

Text between the title and the abstract (authors, affiliations) and sections after the references
(appendices, supplementary material) are removed.
"""

import argparse
import re
from pathlib import Path


def clean_paper(input_path):
    """
    Clean a single paper Markdown file.
    
    Args:
        input_path: Path to the paper Markdown file
        
    Returns:
        Processed content as string, or None if processing fails
    """
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {input_path}: {e}")
        return None
    
    if not lines:
        return None
    
    # Find title (first line starting with "# " or first non-empty line if no "# " found)
    title_idx = None
    first_nonempty_idx = None
    
    for i, line in enumerate(lines):
        if line.strip() and first_nonempty_idx is None:
            first_nonempty_idx = i
        if line.startswith("# "):
            title_idx = i
            break
    
    # If no "# " title found, use first non-empty line as title
    if title_idx is None:
        if first_nonempty_idx is not None:
            title_idx = first_nonempty_idx
            print(f"Warning: No '# ' title found in {input_path}, using first non-empty line")
        else:
            print(f"Warning: No title found in {input_path}")
            return None
    
    # Find abstract start (line containing "Abstract" with # prefix)
    # Can be "## Abstract", "### Abstract", "###### Abstract", etc.
    # Case-insensitive matching
    abstract_idx = None
    for i in range(title_idx + 1, len(lines)):
        line_stripped = lines[i].strip()
        # Match any number of # followed by optional space and "Abstract" (case-insensitive)
        if re.match(r'^#+\s*abstract\s*$', line_stripped, re.IGNORECASE):
            abstract_idx = i
            break
    
    if abstract_idx is None:
        print(f"Warning: No abstract found in {input_path}")
        return None
    
    # Find references section (line with "References" - case-insensitive, any number of #)
    references_idx = None
    for i in range(abstract_idx + 1, len(lines)):
        line_stripped = lines[i].strip()
        # Match any number of # followed by optional space and "References" (case-insensitive)
        if re.match(r'^#+\s*references\s*$', line_stripped, re.IGNORECASE):
            references_idx = i
            break
    
    if references_idx is None:
        print(f"Warning: No references section found in {input_path}")
        # If no references, take everything from abstract to end
        result_lines = lines[title_idx:abstract_idx + 1] + lines[abstract_idx + 1:]
        return ''.join(result_lines)
    
    # Find the end of references
    # Look for: 1) Any line starting with # (header), or 2) Common appendix keywords
    references_end_idx = len(lines)  # Default to end of file
    
    for i in range(references_idx + 1, len(lines)):
        line = lines[i].strip()
        
        # Skip empty lines and reference items
        if not line or line.startswith("* "):
            continue
        
        # Check if this is a section header (starts with any number of #)
        if line.startswith("#"):
            references_end_idx = i
            break
        
        # Check if this is an appendix or supplementary section (common keywords)
        # These might not have # prefix
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ['appendix', 'supplementary', 'supplement']):
            # Make sure it's a standalone line (likely a section header)
            if len(line.split()) <= 3:  # Short line, likely a header
                references_end_idx = i
                break
    
    # Build the output: title + abstract + content (from abstract to references end)
    # We want to skip everything between title and abstract (author info, etc.)
    
    # Normalize title
    title_line = lines[title_idx]
    if not title_line.startswith("#"):
        # Title without #, add single #
        normalized_title = "# " + title_line
    elif title_line.startswith("# "):
        # Already has single #, keep it
        normalized_title = title_line
    else:
        # Has multiple #, normalize to single #
        title_text = re.sub(r'^#+\s*', '', title_line)
        normalized_title = "# " + title_text
    
    # Ensure title ends with newline
    if not normalized_title.endswith('\n'):
        normalized_title += '\n'
    
    # Build result: title + blank line + abstract section onwards
    result_parts = [normalized_title, '\n']
    
    # Add abstract and everything after it, normalizing the abstract header
    for i in range(abstract_idx, references_end_idx):
        line = lines[i]
        # Normalize abstract header to use single #
        if i == abstract_idx and re.match(r'^#+\s*abstract\s*$', line.strip(), re.IGNORECASE):
            result_parts.append("# Abstract\n")
        else:
            result_parts.append(line)
    
    return ''.join(result_parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", required=True, help="Folder of Markdown papers")
    parser.add_argument("-o", "--output", required=True, help="Folder for cleaned papers")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    papers = sorted(Path(args.input).glob("*.md"))
    cleaned = 0
    for paper in papers:
        content = clean_paper(paper)
        if content is not None:
            (output / paper.name).write_text(content, encoding="utf-8")
            cleaned += 1
    print(f"Cleaned {cleaned}/{len(papers)} papers -> {output}")


if __name__ == "__main__":
    main()
