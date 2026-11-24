# Tests

Self-check scripts for `--code` mode. Each one loads the real model
(`harims95/hobbylm-embed-140m`) and needs sentence-transformers:

```
python tests/test_reorder.py
python tests/test_sql_check.py
python tests/test_ignore_format_join.py
```

- `test_reorder.py` shuffles the lines of a real Laravel config, renames
  2 keys and changes exactly 2 values, and checks the report shows only
  those 4 changes, with the renamed keys paired to their own old lines.
- `test_sql_check.py` runs the 4 SELECT equivalence pairs in
  `fixtures/sql_equivalence_pairs.csv` (BETWEEN vs two comparisons, IN vs
  an OR chain, explicit JOIN vs a comma join, double negation) against the
  SQLite database built from `fixtures/sql_check_schema.sql`, so --sql-check
  should report "same rows" for all 4; a control pair in the script reports
  "different rows". The same CSV carries 3 write pairs - two equivalent
  UPDATEs written differently, a DELETE whose new WHERE clause is wider
  (deletes more rows), and an UPDATE that changes a different column.
  UPDATE/DELETE pairs run against a temporary copy of the database, each in
  its own rolled-back transaction, and report "same effect" or "different
  effect" with the row counts. The test also checks the original database
  file is byte-identical after every check.
- `test_ignore_format_join.py` runs the Django auth 0001_initial.py
  reformatting sweep (3.2 -> 5.0) through `--code --ignore-format` and
  checks the report gets down to the one real change, with no Added or
  Removed rows from the rewrapping.

## Fixtures

The fixtures under `fixtures/` are real third-party files, used to test
against code that was not written to flatter the tool:

- `laravel_database_v10.php` - `config/database.php` from the
  laravel/laravel skeleton at tag v10.0.0. MIT licence,
  https://github.com/laravel/laravel
- `django_auth_0001_32.py`, `django_auth_0001_50.py` -
  `django/contrib/auth/migrations/0001_initial.py` from Django at tags
  3.2 and 5.0. BSD licence, https://github.com/django/django

Everything else under `fixtures/` (the SQL schema and the equivalence
pairs) was written for this recipe.
