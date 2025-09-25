# Copyright 2025 Snowflake Inc.
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
def get_cortex_agent_description(agent_services: list[dict]) -> str:
    return f"""Cortex Agent tool that combines structured and unstructured data querying and may include additional custom tools in a configured Cortex Agent object in Snowflake.

    Each service service can be identified by its database_name, schema_name, and service_name.
    The user's query string is passed to the agent service as the query parameter.

    Available agent services include:
    {agent_services}
    """


def get_cortex_search_description(search_services: list[dict]) -> str:
    return f"""Search tool that performs semantic search against a configured Cortex Search service using Snowflake's REST API.
    Supports filtering, column selection, and limit for refined search results.

    Each service service can be identified by its database_name, schema_name, and service_name.
    Columns and filters are optional.
    The  user's query string is passed to the search service as the query parameter.

    Available search services include:
    {search_services}
    """


def get_cortex_analyst_description(analyst_services: list[dict]) -> str:
    return f"""Analyst tool that performs natural language to SQL conversion against a configured Cortex Analyst service using Snowflake's REST API.
    Supports semantic model or semantic view.

    Each service service can be identified by its service_name and semantic_model.
    The value of the semantic_model should be a fully-qualified path to a YAML semantic file or Snowflake Semantic View.
    For example, "@my_db.my_schema.my_stage/my_semantic_file.yaml" or "MY_DB.MY_SCH.MY_SEMANTIC_VIEW".
    The user's query string is passed to the analyst service as the query parameter.

    Available analyst services include:
    {analyst_services}
    """


cortex_search_filter_description = """Optional filter query dictionary.
Cortex Search supports filtering on the ATTRIBUTES columns.

Cortex Search supports four matching operators:

1. TEXT or NUMERIC equality: @eq
2. ARRAY contains: @contains
3. NUMERIC or DATE/TIMESTAMP greater than or equal to: @gte
4. NUMERIC or DATE/TIMESTAMP less than or equal to: @lte

These matching operators can be composed with various logical operators:

- @and
- @or
- @not

The following usage notes apply:

Matching against NaN ('not a number') values in the source query are handled as
described in Special values. Fixed-point numeric values with more than 19 digits (not
including leading zeroes) do not work with @eq, @gte, or @lte and will not be returned
by these operators (although they could still be returned by the overall query with the
use of @not).

TIMESTAMP and DATE filters accept values of the form: YYYY-MM-DD and, for timezone
aware dates: YYYY-MM-DD+HH:MM. If the timezone offset is not specified, the date is
interpreted in UTC.

These operators can be combined into a single filter object.

Example:
Filtering on rows where NUMERIC column numeric_col is between 10.5 and 12.5 (inclusive):

{ "@and": [
  { "@gte": { "numeric_col": 10.5 } },
  { "@lte": { "numeric_col": 12.5 } }
]}
"""
