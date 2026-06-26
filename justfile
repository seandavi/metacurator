# metacurator task runner. Run `just` to list recipes.
#
# Codegen (`just gen`) regenerates Pydantic models + JSON Schema from the LinkML
# schemas into src/metacurator/_generated/ (ADR-0003). Generated artifacts are
# NEVER hand-edited and are not checked in. Needs the `schema` extra.

# LinkML schemas under schema/ to generate from (space-separated stems).
schemas := "cmd"
gen_dir := "src/metacurator/_generated"

# List available recipes.
default:
    @just --list

# Install all dev/optional dependencies.
sync:
    uv sync --extra dev --extra schema --extra mcp --extra tables

# Lint with ruff.
lint:
    uv run ruff check .

# Run the test suite (offline; set RUN_INTEGRATION=1 for live tests).
test *args:
    uv run pytest {{args}}

# Regenerate everything from the LinkML schemas.
gen: gen-pydantic gen-jsonschema

# Regenerate Pydantic models.
gen-pydantic:
    mkdir -p {{gen_dir}}
    for s in {{schemas}}; do \
        echo "gen-pydantic $s"; \
        uv run gen-pydantic schema/$s.yaml > {{gen_dir}}/$s.py; \
    done

# Regenerate JSON Schema.
gen-jsonschema:
    mkdir -p {{gen_dir}}
    for s in {{schemas}}; do \
        echo "gen-json-schema $s"; \
        uv run gen-json-schema schema/$s.yaml > {{gen_dir}}/$s.schema.json; \
    done

# Remove generated artifacts.
clean:
    rm -rf {{gen_dir}}
