import json
import logging

logging.basicConfig(level=logging.INFO)


def extract_json(markdown: str) -> dict:
    """
    Extracts JSON data from markdown content.
    Strips markdown code blocks and handles nested JSON.
    Returns a dictionary representation of the JSON.
    """
    try:
        # Split the markdown into lines to filter out code blocks
        lines = markdown.split('\n')
        json_lines = []
        in_code_block = False

        for line in lines:
            # Check for code block start and end
            if line.startswith('```'):
                in_code_block = not in_code_block
                continue
            if not in_code_block:
                json_lines.append(line)

        # Join the filtered lines and attempt to parse JSON
        json_data = '\n'.join(json_lines)
        logging.info('Stripped markdown and prepared JSON data.')

        # Attempt to parse the stripped JSON data
        return json.loads(json_data)

    except json.JSONDecodeError as e:
        logging.error('JSON decoding error: %s', e)
        # Fallback strategy: try to extract any JSON like patterns
        fallback_data = extract_fallback_json(markdown)
        return fallback_data


def extract_fallback_json(markdown: str) -> dict:
    """
    Fallback strategy to extract JSON from markdown content.
    May not handle all cases but attempts to retrieve some JSON-like structures.
    """
    # Attempt to strip non-JSON content and parse
    try:
        # Basic pattern matching for JSON-like structures
        json_string = re.search(r'{.*}', markdown, re.DOTALL)
        if json_string:
            return json.loads(json_string.group(0))
        else:
            logging.warning('No JSON-like structure found in fallback extraction.')
            return {}
    except Exception as e:
        logging.error('Fallback extraction error: %s', e)
        return {}