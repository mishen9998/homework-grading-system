# Organization migration d10a00100001

The migration adds organization ownership without changing legacy primary keys.
All old records are assigned to organization code `default`; existing `admin`
accounts remain institution administrators. The reserved `platform` organization
has no automatically generated account or password. Platform administrators must
be created by the separately authorized provisioning command.

`Organization`, `OrganizationClass`, and `AuditLog` are exported from `app.models`.
All pre-existing business models have a non-null, indexed `organization_id`
foreign key. An omitted ID can only be obtained from the verified HTTP request
context; scripts, workers and test fixtures must pass it explicitly. User names
and email addresses are unique inside an organization, rather than globally.
The same email does not merge accounts. Old class display names remain intact;
their organization-local class ID is backfilled for users.

## Explicit migration entry point

Set `DATABASE_URL` to an explicitly prepared database. The migration command does
not read `.env`, import `run.py`, choose a default database or use `db.create_all`.

- `python initialize_database.py --check`: read-only data/schema checks.
- `python initialize_database.py`: initialize an empty database through the complete Alembic revision chain; refuse a non-empty target.
- `python initialize_database.py --upgrade`: preflight then upgrade an existing target.

Take and independently verify database and attachment backups before upgrading a
customer database. Stop writers for the entire preflight/upgrade interval so the
checked rows cannot change between validation and DDL. This task only exercises
synthetic, isolated targets; it does not authorize a real-data migration.

Supported starting points: an empty database; a complete unversioned legacy
schema (including tables previously created by development `create_all`); a
legacy database at revision `c37a9b4102fe` with no `knowledge_chunks`; and a
database already at the new revision. The first revision now bootstraps an empty
database from an explicit frozen legacy schema. It never imports the changing
application metadata to define historical revisions. The new revision adds the
missing chunk table and organization fields through versioned DDL.

Preflight enumerates duplicate submissions/answers, orphan foreign keys,
assignment/course teacher conflicts, assignments without a course, answer
assignment conflicts, existing cross-organization parent links and suspicious
attachment references. Unknown roles and legacy `platform_admin` rows are refused,
as are platform-role/organization or user-class/organization mismatches. It reports table names, record IDs and reason codes,
without passwords, answer bodies or personal information. Ambiguity stops the
upgrade before version-table writes or DDL; no record is deleted or guessed into
a new ownership mapping. Resolve each finding with the data owner in a verified
copy, then re-run `--check`. Never use an unverified `stamp head` to bypass it.

MySQL DDL is not transactional. The organization revision checks existing columns,
constraints and reserved organization rows to support restart after partial DDL,
but a full failed-upgrade recovery must be tested against the captured backup.
Do not advertise database rollback as an ORM transaction rollback. Automated
downgrade of this ownership revision is deliberately refused because it destroys
tenant ownership; restore the verified pre-upgrade backup instead. Later tasks
must add separate revisions chained from `d10a00100001`, never replace this
upgrade with current-model `create_all`.

## Repeatable validation

`python -m pytest tests/test_organization_migrations.py -q` exercises SQLite and
skips MySQL unless `T1_SCHEMA_TEST_MYSQL_URL` is explicitly supplied. To also run
MySQL, set that variable to the URL of a dedicated loopback test server, with no
database component. Tests create random `t1_schema_<uuid>` databases and remove
only the exact databases they created. Tests never load original databases or
attachments, `.env`, real credentials or paid AI providers.

The cases assert empty initialization, unversioned complete history, versioned
history without chunks, repeated upgrade, all table/column nullability and
organization foreign keys, organization-local identity uniqueness, original IDs
and content retention, class mapping, no privilege escalation, offline identity
failure and preflight rejection before schema changes for each ambiguity class.
