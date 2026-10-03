# metacurator task runner. Run `just` to list recipes.
#
# Codegen (`just gen`) regenerates Pydantic models + JSON Schema from each curation
# target's LinkML schema (targets/<name>/schema.yaml) into src/metacurator/_generated/
# (ADR-0003, ADR-0010). Generated artifacts are NEVER hand-edited and are not checked
# in. Needs the `schema` extra.

# Curation targets under targets/ to generate from (space-separated names).
targets := "cmd"
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
    for t in {{targets}}; do \
        echo "gen-pydantic $t"; \
        uv run gen-pydantic targets/$t/schema.yaml > {{gen_dir}}/$t.py; \
    done

# Regenerate JSON Schema.
gen-jsonschema:
    mkdir -p {{gen_dir}}
    for t in {{targets}}; do \
        echo "gen-json-schema $t"; \
        uv run gen-json-schema targets/$t/schema.yaml > {{gen_dir}}/$t.schema.json; \
    done

# Remove generated artifacts.
clean:
    rm -rf {{gen_dir}}
