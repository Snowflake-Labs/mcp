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
cortex_search_filter_description = """Optional filter query dictionary.
Cortex Search supports filtering on the ATTRIBUTES columns specified in the CREATE CORTEX SEARCH SERVICE command.

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
