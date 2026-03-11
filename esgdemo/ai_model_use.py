import requests
import json
import ast
import os

BASE_URL = os.getenv("AI_BACKEND_URL", "http://127.0.0.1:8000")

def get_network_config(user_input, mode="test"):
    """
    Fetch and display raw LLM JSON result.
    Args:
        user_input (str): The prompt message to send.
        mode (str): Execution mode (default: "test").
    Returns:
        tuple: (result_string, final_commands_string, saving_string)
    """
    try:
        payload = {
            "message": user_input
        }

        # Send POST request to backend
        response = requests.post(f"{BASE_URL}/output", json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract relevant fields from response
        result_string = data["llm_result"]
        commands_string = data["restconf_commands"]
        saving_string = data["energy_saving_percentage"]

        # Parse commands string from list format
        start_idx = commands_string.find('[')
        end_idx = commands_string.rfind(']') + 1
        prefix_string = commands_string[:start_idx]
        commands_list_str = commands_string[start_idx:end_idx]
        print(commands_list_str)
        # Convert string to actual Python list
        commands_list = ast.literal_eval(commands_list_str)

        # Format command output
        final_commands_string = prefix_string.strip() + "\n"
        for cmd in commands_list:
            formatted_cmd = cmd.encode('utf-8').decode('unicode_escape')
            final_commands_string += formatted_cmd + "\n\n"

        return result_string, final_commands_string, saving_string

    except requests.RequestException as e:
        print(f"Error fetching LLM output: {e}")
        return None
