def extract_json(content):
    import json
    import logging
    
    logging.basicConfig(level=logging.ERROR)
    content = content.strip()  
    
    if content.startswith('```json') and content.endswith('```'):
        content = content[8:-3].strip()  
    elif content.startswith('```') and content.endswith('```'):
        content = content[3:-3].strip()  
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


def _parse_json(response):
    # Old implementation replaced
    return extract_json(response)  
