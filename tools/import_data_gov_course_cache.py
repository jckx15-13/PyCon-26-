from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "course_directory_cache.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.connectors import DataGovCourseDirectoryClient


def main() -> None:
    os.environ.setdefault("SKILLQUEST_ENABLE_DATA_GOV_COURSES", "true")
    os.environ.setdefault("DATA_GOV_COURSE_LIMIT", "18")
    status = DataGovCourseDirectoryClient().fetch()
    if not status.get("items"):
        raise SystemExit(f"No course rows imported: {status.get('status')} {status.get('error') or status.get('detail')}")
    payload = {
        "source": "Cached MySkillsFuture Course Directory slice",
        "url": status.get("url"),
        "dataset_id": status.get("dataset_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "tools/import_data_gov_course_cache.py",
        "records": status.get("records", {"loaded": len(status.get("items", []))}),
        "detail": "Cached from the public data.gov.sg MySkillsFuture Course Directory for fast offline demos.",
        "items": status["items"],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['items'])} courses to {OUTPUT}")


if __name__ == "__main__":
    main()
