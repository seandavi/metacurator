# Regenerate Pydantic models + JSON Schema from the LinkML schemas (ADR-0003).
# Generated artifacts are NEVER hand-edited (they land in src/metacurator/_generated/).
# Requires the `schema` extra: uv sync --extra schema
#
#   make -C schema all        # regenerate everything
#   make -C schema pydantic   # just the Pydantic models
#   make -C schema jsonschema # just the JSON Schema

GEN := ../src/metacurator/_generated
SCHEMAS := cmd

.PHONY: all pydantic jsonschema clean
all: pydantic jsonschema

pydantic:
	@mkdir -p $(GEN)
	@for s in $(SCHEMAS); do \
		echo "gen-pydantic $$s"; \
		uv run gen-pydantic $$s.yaml > $(GEN)/$$s.py; \
	done

jsonschema:
	@mkdir -p $(GEN)
	@for s in $(SCHEMAS); do \
		echo "gen-json-schema $$s"; \
		uv run gen-json-schema $$s.yaml > $(GEN)/$$s.schema.json; \
	done

clean:
	rm -rf $(GEN)
