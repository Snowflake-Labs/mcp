def create_object_prompt(object_type: str):
    return f"""Create a new Snowflake {object_type} object."""


def drop_object_prompt(object_type: str):
    return f"""Drop a Snowflake {object_type} object."""


def update_object_prompt(object_type: str):
    return f"""Update a Snowflake {object_type} object."""


def describe_object_prompt(object_type: str):
    return f"""Describe a Snowflake {object_type} object."""


def list_objects_prompt(object_type: str):
    return f"""List Snowflake {object_type} objects."""
