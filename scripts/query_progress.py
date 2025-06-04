#!/usr/bin/env python3
"""
Workflow Progress Query CLI Tool

A command-line tool for querying workflow progress and status.
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.progress_client import ProgressQueryClient


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    import logging
    
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def query_single_workflow(args):
    """Query progress for a single workflow."""
    client = ProgressQueryClient(
        temporal_host=args.temporal_host,
        namespace=args.namespace,
        api_base_url=args.api_url
    )
    
    try:
        if args.method == "direct":
            result = await client.query_progress_direct(args.workflow_id)
        elif args.method == "api":
            result = await client.query_progress_api(args.workflow_id)
        elif args.method == "detailed":
            result = await client.query_detailed_status_api(args.workflow_id)
        else:  # fallback
            result = await client.query_progress_with_fallback(args.workflow_id)
        
        if args.json:
            # Output as JSON
            output = {
                "workflow_id": result.workflow_id,
                "success": result.success,
                "progress": result.progress,
                "error": result.error,
                "timestamp": result.timestamp,
                "source": result.source
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            print(f"Workflow ID: {result.workflow_id}")
            print(f"Source: {result.source}")
            print(f"Timestamp: {result.timestamp}")
            print(f"Success: {result.success}")
            
            if result.success:
                print("\nProgress:")
                if isinstance(result.progress, dict):
                    for key, value in result.progress.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {result.progress}")
            else:
                print(f"Error: {result.error}")
    
    finally:
        # Temporal Python client doesn't have a close method
        # It cleans itself up when no longer referenced
        pass


async def query_multiple_workflows(args):
    """Query progress for multiple workflows."""
    workflow_ids = args.workflow_ids.split(",")
    
    client = ProgressQueryClient(
        temporal_host=args.temporal_host,
        namespace=args.namespace,
        api_base_url=args.api_url
    )
    
    try:
        results = await client.query_multiple_workflows(
            workflow_ids, 
            use_api=(args.method == "api")
        )
        
        if args.json:
            # Output as JSON array
            output = []
            for result in results:
                output.append({
                    "workflow_id": result.workflow_id,
                    "success": result.success,
                    "progress": result.progress,
                    "error": result.error,
                    "timestamp": result.timestamp,
                    "source": result.source
                })
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            print(f"Queried {len(results)} workflows:\n")
            for result in results:
                print(client.format_progress_result(result))
    
    finally:
        # Temporal Python client doesn't have a close method
        # It cleans itself up when no longer referenced
        pass


async def monitor_workflow(args):
    """Monitor workflow progress over time."""
    client = ProgressQueryClient(
        temporal_host=args.temporal_host,
        namespace=args.namespace,
        api_base_url=args.api_url
    )
    
    try:
        print(f"Monitoring workflow {args.workflow_id} (interval: {args.interval}s, max: {args.max_iterations})")
        print("Press Ctrl+C to stop monitoring\n")
        
        results = await client.monitor_progress(
            args.workflow_id,
            interval=args.interval,
            max_iterations=args.max_iterations,
            use_api=(args.method == "api")
        )
        
        if args.json:
            # Output as JSON array
            output = []
            for result in results:
                output.append({
                    "workflow_id": result.workflow_id,
                    "success": result.success,
                    "progress": result.progress,
                    "error": result.error,
                    "timestamp": result.timestamp,
                    "source": result.source
                })
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output with progress history
            print("Progress History:")
            for i, result in enumerate(results):
                timestamp = result.timestamp[:19] if result.timestamp else "unknown"
                print(f"[{timestamp}] {client.format_progress_result(result)}")
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    
    finally:
        # Temporal Python client doesn't have a close method
        # It cleans itself up when no longer referenced
        pass


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Query Temporal workflow progress and status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query single workflow progress
  python query_progress.py single workflow-123
  
  # Query multiple workflows
  python query_progress.py multiple "workflow-1,workflow-2,workflow-3"
  
  # Monitor workflow progress
  python query_progress.py monitor workflow-123 --interval 2
  
  # Query via API instead of direct Temporal connection
  python query_progress.py single workflow-123 --method api
  
  # Get detailed status information
  python query_progress.py single workflow-123 --method detailed
  
  # Output as JSON
  python query_progress.py single workflow-123 --json
"""
    )
    
    # Global options
    parser.add_argument("--temporal-host", default="localhost:7233", help="Temporal server host")
    parser.add_argument("--namespace", default="default", help="Temporal namespace")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API server base URL")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Single workflow query
    single_parser = subparsers.add_parser("single", help="Query single workflow")
    single_parser.add_argument("workflow_id", help="Workflow ID to query")
    single_parser.add_argument(
        "--method", 
        choices=["direct", "api", "fallback", "detailed"], 
        default="fallback",
        help="Query method (default: fallback)"
    )
    
    # Multiple workflows query
    multiple_parser = subparsers.add_parser("multiple", help="Query multiple workflows")
    multiple_parser.add_argument("workflow_ids", help="Comma-separated workflow IDs")
    multiple_parser.add_argument(
        "--method", 
        choices=["direct", "api", "fallback"], 
        default="fallback",
        help="Query method (default: fallback)"
    )
    
    # Monitor workflow
    monitor_parser = subparsers.add_parser("monitor", help="Monitor workflow progress")
    monitor_parser.add_argument("workflow_id", help="Workflow ID to monitor")
    monitor_parser.add_argument("--interval", type=float, default=5.0, help="Query interval in seconds")
    monitor_parser.add_argument("--max-iterations", type=int, default=100, help="Maximum number of queries")
    monitor_parser.add_argument(
        "--method", 
        choices=["direct", "api", "fallback"], 
        default="fallback",
        help="Query method (default: fallback)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Run appropriate command
    try:
        if args.command == "single":
            asyncio.run(query_single_workflow(args))
        elif args.command == "multiple":
            asyncio.run(query_multiple_workflows(args))
        elif args.command == "monitor":
            asyncio.run(monitor_workflow(args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()