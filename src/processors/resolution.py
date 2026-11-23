from src.utils import normalize_name

# Seed list is illustrative; extend with verified canonical entities.
SEED_ENTITIES = ["OpenAI", "Anthropic", "Google", "Microsoft", "Meta", "NVIDIA", "Mistral AI"]

class EntityResolver:
    def __init__(self, seed=None):
        self.seed = seed or SEED_ENTITIES
        self.index = {normalize_name(x): x for x in self.seed}
        self.mapping_log = []

    def resolve(self, raw_name: str) -> str:
        key = normalize_name(raw_name)
        if not key:
            return raw_name
        if key in self.index:
            canonical = self.index[key]
        else:
            canonical = raw_name.strip()
            self.index[key] = canonical
        self.mapping_log.append({"raw_name": raw_name, "canonical_name": canonical})
        return canonical
