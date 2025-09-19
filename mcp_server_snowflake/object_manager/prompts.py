def get_object_mgmt_prompt(action: str, object_types: list[str]):
    return f"""Generic tool to {action.lower()} a Snowflake object including {", ".join(object_types)}."""
