import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from snowflake.core import Root
from snowflake.core.compute_pool import ComputePool
from snowflake.core.database import Database
from snowflake.core.image_repository import ImageRepository
from snowflake.core.role import Role
from snowflake.core.schema import Schema
from snowflake.core.stage import Stage, StageDirectoryTable
from snowflake.core.table import Table, TableColumn
from snowflake.core.user import User
from snowflake.core.view import View, ViewColumn
from snowflake.core.warehouse import Warehouse


class ObjectMetadata(BaseModel):
    name: str | None = Field(
        default=None,  # We don't use name when listing objects
        description="The name of the object",
    )
    comment: str | None = Field(
        default=None, description="The description of the object"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_json_string(cls, data):
        """
        Automatically parse JSON strings when creating instances.
        This allows passing either a dict or a JSON string to any ObjectMetadata subclass.
        """
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")
        return data


class SnowflakeDatabase(ObjectMetadata):
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )
    data_retention_time_in_days: int = Field(
        ge=0,
        lt=90,
        default=None,
        description="Specifies the number of days for which Time Travel actions (CLONE and UNDROP)"
        "can be performed on the database, as well as specifying the default"
        "Time Travel retention time for all schemas created in the database.",
    )

    def get_core_object(self):
        return Database.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases


class SnowflakeSchema(ObjectMetadata):
    database_name: str = Field(description="The database the schema belongs to")
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )
    data_retention_time_in_days: int = Field(
        ge=0,
        lt=90,
        default=None,
        description="Specifies the number of days for which Time Travel actions (CLONE and UNDROP)"
        "can be performed on the schema, as well as specifying the default"
        "Time Travel retention time for all tables created in the schema.",
    )

    def get_core_object(self):
        return Schema.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases[self.database_name].schemas


class SnowflakeColumn(BaseModel):
    name: str = Field(description="The name of the column")
    datatype: str = Field(description="The data type of the column")
    comment: str = Field(default=None, description="The comment for the column")


class SnowflakeTableColumn(SnowflakeColumn):
    nullable: bool = Field(default=None, description="Whether the column can be null")


class SnowflakeTable(ObjectMetadata):
    database_name: str = Field(description="The database the table belongs to")
    schema_name: str = Field(description="The schema the table belongs to")
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of table"
    )
    # Columns only used if creating a table
    columns: list[SnowflakeTableColumn] = Field(
        default=None,
        description="The columns of the table. Should be a list of SnowflakeTableColumn objects.",
    )
    data_retention_time_in_days: int = Field(
        ge=0,
        lt=90,
        default=None,
        description="Specifies the retention period for the table so that Time Travel actions "
        "SELECT, CLONE, UNDROP can be performed on historical data in the table.",
    )

    def get_core_object(self):
        if self.columns is not None:
            self.columns = [TableColumn.from_dict(col.__dict__) for col in self.columns]

        return Table.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases[self.database_name].schemas[self.schema_name].tables


class SnowflakeViewColumn(SnowflakeColumn):
    pass


class SnowflakeView(ObjectMetadata):
    database_name: str = Field(description="The database the view belongs to")
    schema_name: str = Field(description="The schema the view belongs to")
    query: str = Field(description="The SELECT query that defines the view")
    kind: Literal["TEMPORARY", "PERMANENT"] = Field(
        default=None, description="The kind of view as PERMANENT or TEMPORARY"
    )
    # Columns only used if creating a view
    columns: list[SnowflakeViewColumn] = Field(
        default=None,
        description="The columns of the view. Should be a list of SnowflakeViewColumn objects.",
    )
    secure: bool = Field(default=None, description="Whether the view is secure")

    def get_core_object(self):
        if self.columns is not None:
            self.columns = [ViewColumn.from_dict(col.__dict__) for col in self.columns]

        return View.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases[self.database_name].schemas[self.schema_name].views


class SnowflakeWarehouse(ObjectMetadata):
    warehouse_type: Literal["STANDARD", "SNOWPARK-OPTIMIZED"] = Field(
        default="STANDARD", description="The type of warehouse"
    )
    warehouse_size: Literal[
        "X-SMALL",
        "SMALL",
        "MEDIUM",
        "LARGE",
        "X-LARGE",
        "2X-LARGE",
        "3X-LARGE",
        "4X-LARGE",
    ] = Field(default=None, description="The size of the warehouse")
    auto_suspend: int = Field(
        default=None,
        description="The number of minutes of inactivity before the warehouse is automatically suspended",
    )
    auto_resume: Literal["true", "false"] = Field(
        default=None, description="Whether the warehouse is automatically resumed"
    )
    initially_suspended: Literal["true", "false"] = Field(
        default=None, description="Whether the warehouse is initially suspended"
    )
    max_cluster_count: int = Field(
        default=None,
        description="Specifies the maximum number of clusters for a multi-cluster warehouse",
    )
    min_cluster_count: int = Field(
        default=None,
        description="Specifies the minimum number of clusters for a multi-cluster warehouse",
    )
    scaling_policy: Literal["STANDARD", "ECONOMY"] = Field(
        default=None,
        description="Scaling policy of warehouse, possible scaling policies: STANDARD, ECONOMY",
    )
    statement_timeout_in_seconds: int = Field(
        default=None,
        description="Object parameter that specifies the time, in seconds, after which a running SQL statement is canceled by the system",
    )

    def get_core_object(self):
        return Warehouse.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.warehouses


class SnowflakeComputePool(ObjectMetadata):
    min_nodes: int = Field(description="Minimum number of nodes for the compute pool.")
    max_nodes: int = Field(description="Maximum number of nodes for the compute pool.")
    instance_family: Literal[
        "CPU_X64_XS",
        "CPU_X64_S",
        "CPU_X64_M",
        "CPU_X64_SL",
        "CPU_X64_L",
        "HIGHMEM_X64_S",
        "HIGHMEM_X64_M",
        "HIGHMEM_X64_SL",
        "HIGHMEM_X64_L",
        "GPU_NV_S",
        "GPU_NV_M",
        "GPU_NV_L",
        "GPU_NV_XS",
        "GPU_NV_SM",
        "GPU_NV_2M",
        "GPU_NV_3M",
        "GPU_NV_SL",
        "GPU_GCP_NV_L4_1_24G",
        "GPU_GCP_NV_L4_4_24G",
        "GPU_GCP_NV_A100_8_40G",
    ] = Field(description="Instance family for the compute pool.")
    auto_resume: bool = Field(
        default=None, description="Whether the warehouse is automatically resumed"
    )
    auto_suspend_secs: int = Field(
        default=None,
        description="Number of seconds until the compute pool automatically suspends.",
    )

    def get_core_object(self):
        return ComputePool.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.compute_pools


class SnowflakeRole(ObjectMetadata):
    owner: str = Field(
        default=None, description="Specifies the role that owns this role."
    )
    is_inherited: bool = Field(
        default=None,
        description="Specifies whether the role used to run the command inherits the specified role.",
    )

    def get_core_object(self):
        return Role.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.roles


class SnowflakeUser(ObjectMetadata):
    password: str = Field(
        default=None, description="Specifies the password for the user."
    )
    login_name: str = Field(
        default=None,
        description="Specifies the login name for the user."
        "If not specified, the name field is used as the login name.",
    )
    display_name: str = Field(
        default=None, description="Specifies the display name for the user."
    )
    email: str = Field(
        default=None, description="Specifies the email address for the user."
    )
    first_name: str = Field(
        default=None, description="Specifies the first name for the user."
    )
    last_name: str = Field(
        default=None, description="Specifies the last name for the user."
    )
    must_change_password: bool = Field(
        default=None,
        description="Specifies whether the user must change their password on next login.",
    )
    disabled: bool = Field(
        default=None, description="Specifies whether the user is disabled."
    )
    default_warehouse: str = Field(
        default=None, description="Specifies the default warehouse for the user."
    )
    default_role: str = Field(
        default=None, description="Specifies the default role for the user."
    )
    network_policy: str = Field(
        default=None,
        description="Specifies an existing network policy is active for the user. Otherwise, use account default.",
    )

    def get_core_object(self):
        return User.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.users


class SnowflakeStage(ObjectMetadata):
    database_name: str = Field(description="The database the stage belongs to")
    schema_name: str = Field(description="The schema the stage belongs to")
    kind: Literal["TEMPORARY", "PERMANENT"] = Field(
        default=None, description="The kind of stage as PERMANENT or TEMPORARY"
    )
    enable_directory_table: bool = Field(
        default=False, description="Whether the stage is enabled for directory table"
    )

    def get_core_object(self):
        data = self.__dict__.copy()
        if self.enable_directory_table:
            data.pop("enable_directory_table", None)
            data["directory_table"] = StageDirectoryTable(enable=True)
        else:
            data.pop("enable_directory_table", None)

        return Stage.from_dict(data)

    def get_core_path(self, root: Root):
        return root.databases[self.database_name].schemas[self.schema_name].stages


class SnowflakeImageRepository(ObjectMetadata):
    database_name: str = Field(
        description="The database the image repository belongs to"
    )
    schema_name: str = Field(description="The schema the image repository belongs to")

    def get_core_object(self):
        return ImageRepository.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return (
            root.databases[self.database_name]
            .schemas[self.schema_name]
            .image_repositories
        )


SnowflakeClasses = [
    SnowflakeDatabase,
    SnowflakeSchema,
    SnowflakeTable,
    SnowflakeView,
    SnowflakeWarehouse,
    SnowflakeComputePool,
    SnowflakeRole,
    SnowflakeStage,
    SnowflakeUser,
    SnowflakeImageRepository,
]
