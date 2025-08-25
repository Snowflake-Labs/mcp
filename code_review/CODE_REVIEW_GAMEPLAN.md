# MCP Snowflake Server - Tool Testing Strategy

Comprehensive testing approach for Snowflake MCP Server tools.

## 🎯 Testing Philosophy

**Start simple. Build confidence. Increase complexity.**

Each phase builds on the previous. Test systematically across all object types and operations.

---

## 📋 What We're Testing

### Implemented Objects (10 total):
- Database, Schema, Table, View
- Warehouse, ComputePool, Role, User  
- Stage, ImageRepository

### Available Operations (50+ tools):
- `create_{object}`, `drop_{object}`, `update_{object}`
- `describe_{object}`, `list_{object}s`

---

## 🧪 Testing Phases

### Phase 1: Basic Connectivity
*Goal: Ensure tools can be called and respond*

**Setup:**
```bash
npx @modelcontextprotocol/inspector uvx --from . mcp-server-snowflake \
  --service-config-file services/tools_config.yaml
```

**Tests:**
1. [ ] Server starts without errors
2. [ ] All 50+ tools appear in inspector (10 objects × 5 operations)
3. [ ] Simple `list_databases` call works
4. [ ] Response format is valid JSON

**Success Criteria:** Basic connectivity established, tools discoverable

---

### Phase 2: Individual Tool Testing
*Goal: Test each tool type in isolation*

**Setup Requirements:**
- MCP server running in Cursor
- Snowflake connection active
- Test database 'MCP_TEST' can be created

**Test Categories:**

#### Database Operations
- Create database (object input)
- Create database (JSON string input)
- List databases with filtering
- Describe database details
- Update database (add comment)
- Drop database cleanup

#### Warehouse Operations  
- Create warehouse with configuration
- List warehouses with patterns
- Update warehouse size
- Drop warehouse cleanup

#### User/Role Operations
- Create role (test permissions)
- Create user (test permissions)
- Handle privilege errors gracefully

**Documentation Format:**
| Tool | Test Case | Result | Response Time | Issues Found | Notes |
|------|-----------|---------|---------------|--------------|-------|
| create_database | Object input | ✅/❌ | 1.2s | None/Description | Notes |

**Success Criteria:** All core CRUD operations working, clear error handling

---

### Phase 3: Pydantic Validation Testing
*Goal: Test validation boundaries and edge cases*

**Field Validation Tests:**
- Data retention maximum (90 days) - should work
- Data retention over maximum (91 days) - should fail
- Invalid warehouse sizes - should show valid options
- Transient database retention limits

**JSON String Parsing Tests:**
- Valid JSON string input
- Invalid/malformed JSON handling
- Non-JSON string error messages
- Null/empty input validation

**Type Coercion Tests:**
- String to integer conversion (`"30"` → `30`)
- String to boolean conversion (`"true"` → `true`)

**Success Criteria:** Robust validation with helpful error messages

---

### Phase 4: List Operations Testing
*Goal: Test filtering, patterns, and list boundaries*

**Setup:** Create 10+ test databases with patterns:
- MCP_LIST_TEST_001 through MCP_LIST_TEST_010
- MCP_LIST_A_001, MCP_LIST_B_001 (different prefixes)

**Filter Pattern Tests:**
- LIKE wildcards (`MCP_LIST_%`)
- Complex patterns (`%_TEST_%`)
- Pattern accuracy verification

**Return Format Tests:**
- Verify proper object format (not string representations)
- Check performance with large result sets
- Confirm 100-result internal limit working

**Success Criteria:** Filtering works, performance good, proper object format

---

### Phase 5: Complex Dependencies Testing
*Goal: Test object relationships and cascading*

**Parent-Child Relationship Tests:**
```
Database → Schema → Table → View
```

**Complex Object Tests:**
- Tables with multiple columns (different data types, nullable, comments)
- Views referencing tables (with column definitions)
- Stages with configurations

**Error Scenario Tests:**
- Create schema in non-existent database
- Create table in non-existent schema
- Verify clear error messages

**Success Criteria:** All hierarchical relationships work, complex objects supported

---

### Phase 6: Error Recovery Testing
*Goal: Test error handling and recovery scenarios*

**Permission Error Tests:**
- Try to drop system database (SNOWFLAKE)
- Test insufficient privilege handling
- Verify clear permission error messages

**Concurrent Operation Tests:**
- Race condition handling (duplicate creation)
- Conflict resolution (409 errors)

**Connection Resilience Tests:**
- Large list operations
- Multiple rapid operations
- Timeout handling

**Success Criteria:** Excellent error handling, system protection, graceful degradation

---

## 📊 Success Metrics

### Per Phase:
- **Test Count:** Number of tests executed
- **Success Rate:** Percentage passing
- **Issues Found:** Bugs discovered and documented

---

## 📝 Testing Notes

**Environment Setup:**
- Use dedicated test database/schema
- Clean up test objects after each phase
- Document any permission requirements

**Error Documentation:**
- Capture exact error messages
- Note HTTP status codes
- Document reproduction steps
- Assess error message helpfulness

**Performance Tracking:**
- Record response times
- Note any slow operations (>2s)
- Test with realistic data volumes
- Monitor resource usage

---

**Testing Strategy:** Systematic, phase-based approach ensuring comprehensive coverage of all MCP server functionality before production deployment.