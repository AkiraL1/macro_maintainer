from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from event_maintainer.app_context import build_app_context

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from event_maintainer.search import format_results_json, format_results_text, search_web
from event_maintainer.sources import load_event_drafts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Macro event database maintainer (3-table SQLite)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Run one event maintenance pass.")
    ingest.add_argument(
        "--input", required=True, help="Path to a JSON list of event drafts."
    )

    subparsers.add_parser("init-db", help="Create or verify database tables.")
    subparsers.add_parser("db-status", help="Show database tables and row counts.")
    list_events_cmd = subparsers.add_parser("list-events", help="List stored events.")
    list_events_cmd.add_argument(
        "--maintenance-window",
        action="store_true",
        help="Only events in maintenance window (past 72h + next 7d by default).",
    )
    list_events_cmd.add_argument(
        "--past-hours",
        type=int,
        default=None,
        help="Override MAINTENANCE_PAST_HOURS for window filter.",
    )
    list_events_cmd.add_argument(
        "--future-days",
        type=int,
        default=None,
        help="Override MAINTENANCE_FUTURE_DAYS for window filter.",
    )

    subparsers.add_parser(
        "recency-window",
        help="Show maintenance time window (72h past + 7d future) and search hints.",
    )
    recency_audit_cmd = subparsers.add_parser(
        "recency-audit",
        help="Split stored events into recent / upcoming / outside maintenance window.",
    )
    recency_audit_cmd.add_argument("--past-hours", type=int, default=None)
    recency_audit_cmd.add_argument("--future-days", type=int, default=None)
    subparsers.add_parser("list-logs", help="List maintenance logs.")
    subparsers.add_parser("list-duplicates", help="List duplicate decisions.")
    subparsers.add_parser(
        "category-audit",
        help="Audit event categories against event_category.mdc registry.",
    )

    update_event = subparsers.add_parser(
        "update-event", help="Update non-dedup event fields (category, summary, country)."
    )
    update_event.add_argument("--id", required=True, dest="event_id")
    update_event.add_argument("--category", default=None, help="Primary category (single).")
    update_event.add_argument(
        "--categories",
        default=None,
        help="Ordered labels by relevance, comma-separated (e.g. 央行,宏观).",
    )
    update_event.add_argument("--summary", default=None)
    update_event.add_argument("--country", default=None)

    search_web_cmd = subparsers.add_parser(
        "search-web", help="Search the web via DuckDuckGo HTML."
    )
    search_web_cmd.add_argument("--query", required=True, help="Search query.")
    search_web_cmd.add_argument(
        "--count", type=int, default=10, help="Number of results (1-20)."
    )
    search_web_cmd.add_argument("--offset", type=int, default=0, help="Result offset.")
    search_web_cmd.add_argument(
        "--json", action="store_true", help="Output JSON array."
    )

    get_event = subparsers.add_parser("get-event", help="Get one stored event.")
    get_event.add_argument("event_id", help="Stored event id.")

    args = parser.parse_args()
    context = build_app_context()

    if args.command == "ingest":
        drafts = load_event_drafts(Path(args.input))
        output = asdict(context.maintenance.ingest_events(drafts))
    elif args.command == "init-db":
        output = context.tools.init_database()
    elif args.command == "db-status":
        output = context.tools.database_status()
    elif args.command == "list-events":
        filter_window = (
            args.maintenance_window
            or args.past_hours is not None
            or args.future_days is not None
        )
        output = context.tools.search_events(
            past_hours=args.past_hours,
            future_days=args.future_days,
            use_maintenance_window=filter_window,
        )
    elif args.command == "recency-window":
        output = context.tools.recency_window()
    elif args.command == "recency-audit":
        output = context.tools.recency_audit(
            past_hours=args.past_hours,
            future_days=args.future_days,
        )
    elif args.command == "list-logs":
        output = context.tools.list_maintenance_logs()
    elif args.command == "list-duplicates":
        output = context.tools.list_duplicate_records()
    elif args.command == "category-audit":
        output = context.tools.category_audit()
    elif args.command == "update-event":
        categories: tuple[str, ...] | None = None
        if args.categories:
            categories = tuple(
                part.strip() for part in args.categories.split(",") if part.strip()
            )
        output = context.tools.update_event(
            args.event_id,
            category=args.category,
            categories=categories,
            summary=args.summary,
            country=args.country,
        )
    elif args.command == "search-web":
        results = search_web(args.query, count=args.count, offset=args.offset)
        if args.json:
            print(format_results_json(results))
            return
        print(format_results_text(args.query, results))
        return
    else:
        output = context.tools.get_event(args.event_id)

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
