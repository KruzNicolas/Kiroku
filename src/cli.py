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

    def process_single(self, raw_input: str) -> bool:
        """Process a single URL input (which might contain 'later')"""
        parts = raw_input.strip().split()
        if not parts:
            print("[ERROR] Empty input.")
            return False

        url = parts[0]
        force_later = False
        if len(parts) > 1 and parts[1].lower() == "later":
            force_later = True

        print(f"[INFO] Extracting metadata for: {url}...")

        try:
            metadata = self.extractor.extract(url, force_later=force_later)
            print(
                f"[INFO] Metadata enriched. Title: '{metadata.title}', Tags: {len(metadata.tags)}, Category: {metadata.game_category}"
            )

            print("[INFO] Requesting classification from MiniMax 2.5 (via Ollama)...")
            inference = self.inferencer.infer(metadata)
            print(
                f"[INFO] AI Confidence: {inference.confidence:.2f}. Category: {inference.category.value}. Priority: {inference.priority.value}"
            )

            payload = FinalPayload(metadata=metadata, inference=inference)

            if (
                payload.metadata.force_later
                and payload.inference.priority.value != "Later"
            ):
                print(f"[INFO] Manual override active: Priority forced to 'Later'.")

            page_id = self.notion_writer.upsert_page(payload)
            print(
                f"[SUCCESS] Entry created/updated in Notion: {metadata.title} (ID: {page_id})"
            )
            return True

        except ExtractionError as e:
            print(f"[ERROR] Extraction failed for {url}: {str(e)}")
            return False
        except InferenceError as e:
            print(f"[ERROR] Inference failed for {url}: {str(e)}")
            return False
        except NotionWriterError as e:
            print(f"[ERROR] Notion write failed for {url}: {str(e)}")
            return False
        except APIResponseError as e:
            msg = getattr(e, "message", str(e))
            print(f"[ERROR] Notion API error for {url}: {msg}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error processing {url}: {str(e)}")
            return False

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

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.process_single, line): line for line in lines
            }

            for future in as_completed(future_to_url):
                line = future_to_url[future]
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    print(f"[ERROR] Fatal exception for line '{line}': {str(e)}")
                    fail_count += 1

        print("\n--- Bulk Processing Summary ---")
        print(f"Total: {total}")
        print(f"Success: {success_count}")
        print(f"Failed: {fail_count}")


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
