from __future__ import annotations

import argparse
from pathlib import Path

from dealhunter.llm.warm import APPROVAL_PHRASE, warm_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm and verify the reviewed S3 LLM cache")
    parser.add_argument("--manifest", type=Path, default=Path("fixtures/llm_manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("fixtures/llm_cache.sqlite"))
    parser.add_argument(
        "--approve-live",
        metavar="PHRASE",
        help=f"fresh approval phrase: {APPROVAL_PHRASE!r}",
        required=True,
    )
    args = parser.parse_args()
    outputs = warm_manifest(args.manifest, args.output, args.approve_live)
    print(f"warmed and replay-verified {len(outputs)} manifest cases: {args.output}")


if __name__ == "__main__":
    main()
