from pydantic import BaseModel


class SemanticExpression(BaseModel):
    table: str
    name: str
    # sql_expr: str
    # synonyms: list[str]
    # comment: str = None


# class LogicalTable(BaseModel):
#     table_alias: str
#     name: str
#     primary_keys: list[str] = []
#     unique_keys: list[str] = []
#     synonyms: list[str] = []
#     comment: str = None


# class WindowMetric(SemanticExpression):
#     partition_by: list[SemanticExpression]
#     order_by: list[SemanticExpression]
#     asc: bool = True


# class SemanticRelationship(BaseModel):
#     name: str
#     left_table_alias: str
#     right_table_alias: str
#     left_table_columns: list[str]
#     right_table_columns: list[str]


# class SemanticView(BaseModel):
#     database_name: str
#     schema_name: str
#     name: str
#     comment: str = None
#     tables: list[LogicalTable]
#     relationships: list[SemanticRelationship] = []
#     facts: list[SemanticExpression] = []
#     dimensions: list[SemanticExpression] = []
#     metrics: list[SemanticExpression|WindowMetric] = []
