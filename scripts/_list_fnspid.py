"""List files in the FNSPID HuggingFace repo to find parquet files."""
from huggingface_hub import HfApi

api = HfApi()
items = list(api.list_repo_tree("Zihan1004/FNSPID", repo_type="dataset", recursive=True))
print(f"Total items: {len(items)}")
for item in items:
    path = getattr(item, "path", "?")
    size = getattr(item, "size", "dir")
    if size != "dir" and size is not None:
        mb = size / (1024 * 1024)
        print(f"  {path}  ({mb:.1f} MB)")
    else:
        print(f"  {path}/")
