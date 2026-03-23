from mcp_server_snowflake.semantic_manager.tools import parse_semantic_view_context

# Trimmed from real NOTION_AGENT.SALES.DOMAIN__SEMANTIC GET_DDL() output.
# All tag values are verbatim; columns trimmed for readability.
DDL_DOMAIN_SEMANTIC = (
    "create or replace semantic view NOTION_AGENT.SALES.DOMAIN__SEMANTIC\n"
    "\ttables (\n"
    "\t\tNOTION_AGENT.SALES.DOMAIN primary key (DOMAIN,AGGREGATION_TYPE_ID,DS)"
    " comment='Main sales domain metrics and attributes (DS-partitioned)'\n"
    "\t)\n"
    "\tfacts (\n"
    "\t\tDOMAIN.TOTAL_ARR as total_arr"
    " comment='Total Annual Recurring Revenue (pre-aggregated at domain level)',\n"
    "\t\tDOMAIN.TOTAL_SPACES as total_spaces comment='Total workspace count'\n"
    "\t)\n"
    "\tdimensions (\n"
    "\t\tDOMAIN.DS as ds comment='Date partition for time-series analysis',\n"
    "\t\tDOMAIN.DOMAIN as domain comment='Primary domain identifier',\n"
    "\t\tDOMAIN.AGGREGATION_TYPE as aggregation_type"
    " comment='Aggregation scope: ''all'' (all workspaces)"
    " vs ''sales_assisted'' (sales-assisted workspaces only)'\n"
    "\t)\n"
    "\tmetrics (\n"
    "\t\tDOMAIN.SUM_TOTAL_ARR as SUM(total_arr)"
    " comment='Total Annual Recurring Revenue',\n"
    "\t\tDOMAIN.COUNT_DOMAIN_COUNT as COUNT(DISTINCT domain)"
    " comment='Count of distinct domains'\n"
    "\t)\n"
    "\tcomment='\U0001f3af USE FOR DOMAIN-LEVEL QUESTIONS:"
    " How many workspaces does domain X have?"
    " What is domain Y total ARR?"
    " Domain growth trends and cross-domain comparisons.\n"
    "\n"
    "\U0001f4ca GRAIN: One row per domain per date per aggregation_type\n"
    "\n"
    "\U0001f4a1 KEY METRICS: total_workspaces, sum_total_arr,"
    " monthly_active_members, total_lifetime_ai_actions,"
    " daily/weekly/monthly/quarterly engagement metrics\n"
    "\n"
    "(DS-partitioned table - ALWAYS filter by DS for correct results)'\n"
    "\tai_sql_generation '\n"
    "\u26a0\ufe0f  CRITICAL DS FILTERING REQUIREMENT:"
    " This table contains historical snapshots across multiple dates.\n"
    "YOU MUST ALWAYS filter by DS to prevent metric inflation:\n"
    "- \u2705 Latest snapshot: First get max date externally,"
    " then WHERE ds = ''YYYY-MM-DD'' (handles data delays)\n"
    "- \u2705 Specific date: WHERE ds = ''YYYY-MM-DD''\n"
    "- \u2705 Date range: WHERE ds BETWEEN start_date AND end_date\n"
    "- \u274c DO NOT USE: WHERE ds = (SELECT MAX(ds) FROM this view)"
    " - subqueries not supported in semantic views\n"
    '\U0001f50d ADDITIONAL FILTER: Always specify aggregation_type = "all"'
    " (unless you specifically need sales_assisted data)\n"
    "\n"
    "\u26a0\ufe0f  WITHOUT DS FILTERING:"
    " Metrics will be inflated by summing across multiple historical snapshots!\n"
    "'\n"
    "\tai_question_categorization '\n"
    "\u274c WRONG USE: Individual workspace breakdowns"
    " (use SALES_WORKSPACE__SEMANTIC instead),"
    " member-level analysis (use SALES_WORKSPACE_MEMBER__SEMANTIC)\n"
    "'\n"
    '\twith extension (CA=\'{"tables": [{"name": "DOMAIN",'
    ' "dimensions": [{"name": "SEGMENT",'
    ' "sample_values": ["Enterprise", "Mid-Market", "SMB"]},'
    ' {"name": "AGGREGATION_TYPE",'
    ' "sample_values": ["all", "sales_assisted"]}]}],'
    ' "verified_queries": [{"name": "Domain Workspace Count",'
    ' "question": "How many workspaces does safetyculture.io have?",'
    ' "sql": "SELECT __domain.domain, __domain.total_spaces, __domain.ds'
    " FROM __domain WHERE __domain.ds = CURRENT_DATE() - 1"
    " AND LOWER(__domain.domain) = LOWER($safetyculture.io$)"
    ' AND __domain.aggregation_type = $all$",'
    ' "verified_at": 1710806400,'
    ' "verified_by": "Megha Gupta",'
    ' "use_as_onboarding_question": true}]}\');\n'
)

# Trimmed from real NOTION_AGENT.CS_CX.ZENDESK_TICKETS_CX_REPORTING__SEMANTIC.
# Comment-only view (no ai_sql_generation, ai_question_categorization, or extension).
DDL_ZENDESK_SEMANTIC = (
    "create or replace semantic view"
    " NOTION_AGENT.CS_CX.ZENDESK_TICKETS_CX_REPORTING__SEMANTIC\n"
    "\ttables (\n"
    "\t\tNOTION_AGENT.CS_CX.ZENDESK_TICKETS_CX_REPORTING"
    " primary key (TICKET_ID)"
    " comment='Zendesk CX reporting mart. One row per ticket.'\n"
    "\t)\n"
    "\tfacts (\n"
    "\t\tZENDESK_TICKETS_CX_REPORTING.SLA_TARGET_MINUTES as SLA_TARGET"
    " comment='SLA target threshold in minutes.',\n"
    "\t\tZENDESK_TICKETS_CX_REPORTING.CSAT_SCORE as CSAT_SCORE"
    " comment='CSAT survey score (numeric). Only ~10% populated. Use AVG.'\n"
    "\t)\n"
    "\tdimensions (\n"
    "\t\tZENDESK_TICKETS_CX_REPORTING.TICKET_ID as TICKET_ID"
    " comment='Unique Zendesk ticket ID.',\n"
    "\t\tZENDESK_TICKETS_CX_REPORTING.TICKET_STATUS as TICKET_STATUS"
    " comment='Current status: new, open, pending, hold, solved, closed, deleted.'\n"
    "\t)\n"
    "\tmetrics (\n"
    "\t\tZENDESK_TICKETS_CX_REPORTING.TOTAL_TICKETS"
    " as COUNT(DISTINCT TICKET_ID)"
    " comment='Total unique ticket count.'\n"
    "\t)\n"
    "\tcomment='\n"
    "\U0001f3af USE FOR: CX ticket volume, CSAT, SLA compliance,"
    " contact reason trending,\n"
    "           agent performance, plan-type segmentation.\n"
    "\n"
    "\U0001f4ca GRAIN: One row per ticket in base table.\n"
    "\n"
    "';\n"
)

# Synthetic: no tags at all (18 of 41 real views have this pattern)
DDL_NO_TAGS = (
    "create or replace semantic view NOTION_AGENT.CORE.PLAIN__SEMANTIC\n"
    "\ttables (\n"
    "\t\tNOTION_AGENT.CORE.SOME_TABLE primary key (ID)\n"
    "\t)\n"
    "\tdimensions (\n"
    "\t\tSOME_TABLE.ID as id,\n"
    "\t\tSOME_TABLE.DS as ds\n"
    "\t)\n"
)

# Synthetic: malformed JSON in extension
DDL_MALFORMED_EXTENSION = (
    "create or replace semantic view NOTION_AGENT.CORE.BAD_EXT__SEMANTIC\n"
    "\ttables (\n"
    "\t\tNOTION_AGENT.CORE.SOME_TABLE primary key (ID)\n"
    "\t)\n"
    "\tdimensions (\n"
    "\t\tSOME_TABLE.ID as id\n"
    "\t)\n"
    "\twith extension (CA='this is not valid json {{{');\n"
)


class TestDomainSemanticAllTags:
    """Parse real DOMAIN__SEMANTIC DDL -- all 4 tags present."""

    def test_comment_extracted(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        assert "USE FOR DOMAIN-LEVEL QUESTIONS" in result["comment"]
        assert "ALWAYS filter by DS" in result["comment"]

    def test_ai_sql_generation_extracted(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        assert "CRITICAL DS FILTERING REQUIREMENT" in result["ai_sql_generation"]
        assert "aggregation_type" in result["ai_sql_generation"]

    def test_ai_question_categorization_extracted(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        assert "SALES_WORKSPACE__SEMANTIC" in result["ai_question_categorization"]

    def test_extension_parsed_as_dict(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        ext = result["extension"]
        assert isinstance(ext, dict)
        assert "tables" in ext
        assert "verified_queries" in ext
        assert ext["tables"][0]["name"] == "DOMAIN"

    def test_extension_sample_values(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        dims = result["extension"]["tables"][0]["dimensions"]
        segment_dim = next(d for d in dims if d["name"] == "SEGMENT")
        assert "Enterprise" in segment_dim["sample_values"]

    def test_extension_verified_query(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        q = result["extension"]["verified_queries"][0]
        assert q["question"] == "How many workspaces does safetyculture.io have?"
        assert q["verified_by"] == "Megha Gupta"


class TestZendeskSemanticCommentOnly:
    """Parse real ZENDESK_TICKETS_CX_REPORTING__SEMANTIC DDL -- comment only."""

    def test_comment_extracted(self):
        result = parse_semantic_view_context(DDL_ZENDESK_SEMANTIC)
        assert "CX ticket volume" in result["comment"]
        assert "CSAT" in result["comment"]

    def test_no_ai_tags(self):
        result = parse_semantic_view_context(DDL_ZENDESK_SEMANTIC)
        assert result["ai_sql_generation"] is None
        assert result["ai_question_categorization"] is None
        assert result["extension"] is None


class TestNoTags:
    """Views with no metadata tags return all None."""

    def test_all_none(self):
        result = parse_semantic_view_context(DDL_NO_TAGS)
        assert result == {
            "comment": None,
            "ai_sql_generation": None,
            "ai_question_categorization": None,
            "extension": None,
        }


class TestColumnCommentNotConfused:
    """Column-level comment= must NOT be captured as view-level comment."""

    def test_no_tags_despite_column_comments(self):
        """DDL_NO_TAGS has no view-level comment even though it has columns."""
        result = parse_semantic_view_context(DDL_NO_TAGS)
        assert result["comment"] is None

    def test_table_comment_not_captured(self):
        """Table-level comment (on same line as primary key) must not leak."""
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        # Table comment is 'Main sales domain metrics and attributes...'
        # View comment starts with the target emoji
        assert result["comment"].startswith("\U0001f3af")


class TestEscapedQuotes:
    """Escaped single quotes ('') in DDL are unescaped to (')."""

    def test_ai_sql_generation_unescaped(self):
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        # DDL has ''YYYY-MM-DD'' which should become 'YYYY-MM-DD'
        assert "'YYYY-MM-DD'" in result["ai_sql_generation"]

    def test_column_escaped_quotes_dont_leak(self):
        """Column-level escaped ''all'' doesn't appear in view comment."""
        result = parse_semantic_view_context(DDL_DOMAIN_SEMANTIC)
        assert "''all''" not in (result["comment"] or "")


class TestMalformedExtension:
    """Malformed JSON in extension returns parse_error dict."""

    def test_parse_error_returned(self):
        result = parse_semantic_view_context(DDL_MALFORMED_EXTENSION)
        ext = result["extension"]
        assert isinstance(ext, dict)
        assert ext["parse_error"] is True
        assert "raw" in ext
        assert "this is not valid json" in ext["raw"]


class TestMultilineComment:
    """Multiline comments with emoji are parsed correctly (real Zendesk DDL)."""

    def test_multiline_preserved(self):
        result = parse_semantic_view_context(DDL_ZENDESK_SEMANTIC)
        assert "\n" in result["comment"]

    def test_emoji_preserved(self):
        result = parse_semantic_view_context(DDL_ZENDESK_SEMANTIC)
        assert "\U0001f3af" in result["comment"]
        assert "\U0001f4ca" in result["comment"]
