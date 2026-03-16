import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from .config import config
from .models import FinalPayload
from .extractor import MetadataExtractor, ExtractionError
from .inferencer import OllamaInferencer, InferenceError
from .notion_writer import NotionWriter, NotionWriterError
from notion_client.errors import APIResponseError


class CLIRunner:
    def __init__(self):
        self.extractor = MetadataExtractor()
        self.inferencer = OllamaInferencer()
        self.notion_writer = NotionWriter()

    def process_single(
        self, raw_input: str, index: int = None, total: int = None
    ) -> Tuple[bool, str]:
        """Process a single URL input (which might contain 'later')

        Returns:
            Tuple of (success: bool, url_or_identifier: str)
        """
        parts = raw_input.strip().split()
        if not parts:
            return False, "(empty line)"

        url = parts[0]
        force_later = False
        if len(parts) > 1 and parts[1].lower() == "later":
            force_later = True

        # Build prefix for better traceability in bulk mode
        prefix = f"[{index}/{total}] " if index and total else ""
        print(f"{prefix}[INFO] Extracting metadata for: {url}...")

        try:
            metadata = self.extractor.extract(url, force_later=force_later)
            print(
                f"{prefix}[INFO] Metadata enriched. Title: '{metadata.title}', Tags: {len(metadata.tags)}, Category: {metadata.game_category}"
            )

            print(
                f"{prefix}[INFO] Requesting classification from MiniMax 2.5 (via Ollama)..."
            )
            inference = self.inferencer.infer(metadata)
            print(
                f"{prefix}[INFO] AI Confidence: {inference.confidence:.2f}. Category: {inference.category.value}. Priority: {inference.priority.value}"
            )

            payload = FinalPayload(metadata=metadata, inference=inference)

            if (
                payload.metadata.force_later
                and payload.inference.priority.value != "Later"
            ):
                print(
                    f"{prefix}[INFO] Manual override active: Priority forced to 'Later'."
                )

            page_id = self.notion_writer.upsert_page(payload)
            print(
                f"{prefix}[SUCCESS] Entry created/updated in Notion: {metadata.title} (ID: {page_id})"
            )
            return True, url

        except ExtractionError as e:
            print(f"{prefix}[ERROR] Extraction failed for {url}: {str(e)}")
            return False, url
        except InferenceError as e:
            print(f"{prefix}[ERROR] Inference failed for {url}: {str(e)}")
            return False, url
        except NotionWriterError as e:
            print(f"{prefix}[ERROR] Notion write failed for {url}: {str(e)}")
            return False, url
        except APIResponseError as e:
            msg = getattr(e, "message", str(e))
            print(f"{prefix}[ERROR] Notion API error for {url}: {msg}")
            return False, url
        except Exception as e:
            print(f"{prefix}[ERROR] Unexpected error processing {url}: {str(e)}")
            return False, url

    def process_bulk(self, filepath: str, max_workers: int = 5):
        """Process URLs from a file concurrently"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]
        except FileNotFoundError:
            print(f"[ERROR] File not found: {filepath}")
            sys.exit(1)

        total = len(lines)
        print(
            f"[INFO] Starting bulk processing for {total} URLs with {max_workers} workers..."
        )

        success_count = 0
        fail_count = 0
        failed_urls = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks with their index
            future_to_info = {
                executor.submit(self.process_single, line, idx + 1, total): (
                    idx + 1,
                    line,
                )
                for idx, line in enumerate(lines)
            }

            for future in as_completed(future_to_info):
                idx, line = future_to_info[future]
                try:
                    success, url = future.result()
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        failed_urls.append((idx, url))
                except Exception as e:
                    print(f"[ERROR] Fatal exception for line [{idx}]: {line}: {str(e)}")
                    fail_count += 1
                    failed_urls.append((idx, line))

        print("\n" + "=" * 50)
        print("--- Bulk Processing Summary ---")
        print(f"Total: {total}")
        print(f"Success: {success_count}")
        print(f"Failed: {fail_count}")

        if failed_urls:
            print("\n--- Failed URLs ---")
            for idx, url in failed_urls:
                print(f"  [{idx}] {url}")


def main():
    parser = argparse.ArgumentParser(description="Media Classification Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-u",
        "--url",
        type=str,
        help="Single YouTube URL (append ' later' if you want to force priority)",
    )
    group.add_argument(
        "-f", "--file", type=str, help="Path to text file containing URLs"
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=3,
        help="Max concurrency workers for bulk mode (default: 3)",
    )

    args = parser.parse_args()

    try:
        config.validate()
    except ValueError as e:
        print(f"[ERROR] Configuration Error: {str(e)}")
        print("Please check your .env file or environment variables.")
        sys.exit(1)

    runner = CLIRunner()

    if args.url:
        runner.process_single(args.url)
    elif args.file:
        runner.process_bulk(args.file, max_workers=args.workers)


if __name__ == "__main__":
    main()
