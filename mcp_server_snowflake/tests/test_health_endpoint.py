#!/usr/bin/env python
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
"""
Test for the health endpoint of the MCP server.
"""
import unittest
import requests
import subprocess
import time
import os
import signal
import sys
from pathlib import Path


class TestHealthEndpoint(unittest.TestCase):
    """Test the health endpoint of the MCP server."""

    @classmethod
    def setUpClass(cls):
        """Start the MCP server before running tests."""
        # Path to the configuration file
        config_file = Path(__file__).parent.parent.parent / "services" / "configuration.yaml"
        
        # Start the server with HTTP transport
        cls.server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mcp_server_snowflake.server",
                "--transport",
                "http",
                "--service-config-file",
                str(config_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        # Wait for the server to start
        time.sleep(2)
    
    @classmethod
    def tearDownClass(cls):
        """Stop the MCP server after running tests."""
        if cls.server_process:
            os.kill(cls.server_process.pid, signal.SIGTERM)
            cls.server_process.wait()
    
    def test_health_endpoint(self):
        """Test that the health endpoint returns a 200 OK response."""
        response = requests.get("http://localhost:9000/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
