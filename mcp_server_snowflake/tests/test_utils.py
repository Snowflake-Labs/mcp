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
from unittest.mock import MagicMock
import json
from mcp_server_snowflake.utils import SnowflakeResponse


def test_parse_llm_response_unstructured():
    events = [
        b'data: {"choices": [{"delta": {"type": "text", "content": "Hello, "}}]}',
        b'data: {"choices": [{"delta": {"type": "text", "content": "world!"}}]}',
    ]
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(events)
    sf = SnowflakeResponse()
    result_json = sf.parse_llm_response(mock_response, structured=False)
    result = json.loads(result_json)
    assert result["results"] == "Hello, world!"


def test_parse_llm_response_structured():
    structured_content = "[{'foo': 1}, {'bar': 2}]"
    event = f'data: {{"choices": [{{"delta": {{"type": "text", "content": "{structured_content}"}}}}]}}'.encode(
        "utf-8"
    )
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter([event])
    sf = SnowflakeResponse()
    result_json = sf.parse_llm_response(mock_response, structured=True)
    result = json.loads(result_json)
    assert isinstance(result["results"], list)
    assert result["results"][0]["foo"] == 1
    assert result["results"][1]["bar"] == 2


def test_parse_llm_response_real_sample():
    sse_lines = [
        b'data: {"id":"a9537c2c-2017-4906-9817-2456168d89fa","model":"claude-3-5-sonnet","choices":[{"delta":{"type":"text","content":"I","content_list":[{"type":"text","text":"I"}],"text":"I"}}],"usage":{}}',
        b'data: {"id":"a9537c2c-2017-4906-9817-2456168d89fa","model":"claude-3-5-sonnet","choices":[{"delta":{"type":"text","content":"\'ll help you check Nvidia\'s current","content_list":[{"type":"text","text":"\'ll help you check Nvidia\'s current"}],"text":"\'ll help you check Nvidia\'s current"}}],"usage":{}}',
        b'data: {"id":"a9537c2c-2017-4906-9817-2456168d89fa","model":"claude-3-5-sonnet","choices":[{"delta":{"type":"tool_use","tool_use_id":"tooluse_FB_nOElDTAOKa-YnVWI5Uw","name":"get_stock_price","content_list":[{"tool_use_id":"tooluse_FB_nOElDTAOKa-YnVWI5Uw","name":"get_stock_price"}],"text":""}}],"usage":{}}',
        b'data: {"id":"a9537c2c-2017-4906-9817-2456168d89fa","model":"claude-3-5-sonnet","choices":[{"delta":{"type":"tool_use","input":"{\\"symbol\\":\\"NVDA\\"}","content_list":[{"input":"{\\"symbol\\":\\"NVDA\\"}"}],"text":""}}],"usage":{"prompt_tokens":397,"completion_tokens":65,"total_tokens":462}}',
    ]
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(sse_lines)
    sf = SnowflakeResponse()
    result_json = sf.parse_llm_response(mock_response, structured=False)
    result = json.loads(result_json)
    assert result["results"] == "I'll help you check Nvidia's current"
