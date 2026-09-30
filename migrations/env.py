from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType

from pharma_intel.config import get_settings
from pharma_intel.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))


class RDKitMol(UserDefinedType[object]):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "mol"


class RDKitBitFingerprint(UserDefinedType[object]):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "bfp"


ischema_names.setdefault("mol", RDKitMol)
ischema_names.setdefault("bfp", RDKitBitFingerprint)

SERVER_MANAGED_CHEMISTRY_COLUMNS = {"rdkit_mol", "morgan_bfp"}
SERVER_MANAGED_CHEMISTRY_INDEXES = {
    "ix_compound_structures_rdkit_mol_gist",
    "ix_compound_structures_morgan_bfp_gist",
}


def include_object(object_: object, name: str | None, type_: str, reflected: bool, compare_to: object | None) -> bool:
    if not reflected or compare_to is not None:
        return True
    if type_ == "column" and name in SERVER_MANAGED_CHEMISTRY_COLUMNS:
        table = getattr(object_, "table", None)
        return getattr(table, "name", None) != "compound_structures"
    if type_ == "index" and name in SERVER_MANAGED_CHEMISTRY_INDEXES:
        return False
    return True


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
