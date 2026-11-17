"""Create immutable exploratory v3 derivative by deleting three signed train errors."""
import json
from code_v5.noise_disclosed_policy import DERIVED, derive_data

if __name__ == "__main__":
    stats = derive_data()
    print(json.dumps({"data_dir": str(DERIVED), "selected": stats["selected"],
                      "formal_passed": False, "test_rows_decoded": False}, ensure_ascii=False))
