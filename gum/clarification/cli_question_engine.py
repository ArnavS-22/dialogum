"""
Command-line interface for the clarifying question engine.

Usage:
    python -m gum.clarification.cli_question_engine \
        --source=file \
        --output=test_results_200_props/clarifying_questions.jsonl \
        --prop-ids=77,200,421 \
        --factor-ids=3,6
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gum.config import Config
from gum.clarification.question_engine import ClarifyingQuestionEngine


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('clarifying_question_engine.log')
        ]
    )


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate clarifying questions for flagged propositions'
    )
    
    parser.add_argument(
        '--source',
        type=str,
        choices=['file', 'db'],
        default='file',
        help='Input source: "file" or "db" (default: file)'
    )
    
    parser.add_argument(
        '--input-file',
        type=str,
        default=None,
        help='Path to flagged_propositions.json (default: test_results_200_props/flagged_propositions.json)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='test_results_200_props/clarifying_questions.jsonl',
        help='Output JSONL file path (default: test_results_200_props/clarifying_questions.jsonl)'
    )
    
    parser.add_argument(
        '--prop-ids',
        type=str,
        default=None,
        help='Comma-separated prop IDs to process (e.g., "77,200,421")'
    )
    
    parser.add_argument(
        '--factor-ids',
        type=str,
        default=None,
        help='Comma-separated factor IDs to process (e.g., "3,6,8,11")'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='OpenAI API key (defaults to OPENAI_API_KEY env var)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gpt-4',
        help='Model to use (default: gpt-4)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("Clarifying Question Engine CLI")
    logger.info("=" * 50)
    
    # Get API key
    api_key = args.api_key or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OpenAI API key not provided. Set OPENAI_API_KEY env var or use --api-key")
        sys.exit(1)
    
    # Parse prop IDs
    prop_ids = None
    if args.prop_ids:
        try:
            prop_ids = [int(x.strip()) for x in args.prop_ids.split(',')]
            logger.info(f"Filtering by prop IDs: {prop_ids}")
        except ValueError as e:
            logger.error(f"Invalid prop IDs format: {e}")
            sys.exit(1)
    
    # Parse factor IDs
    factor_ids = None
    if args.factor_ids:
        try:
            factor_ids = [int(x.strip()) for x in args.factor_ids.split(',')]
            logger.info(f"Filtering by factor IDs: {factor_ids}")
        except ValueError as e:
            logger.error(f"Invalid factor IDs format: {e}")
            sys.exit(1)
    
    # Create config
    config = Config()
    config.model = args.model
    
    # Create OpenAI client
    client = AsyncOpenAI(api_key=api_key)
    
    # Create engine
    engine = ClarifyingQuestionEngine(
        openai_client=client,
        config=config,
        input_source=args.source,
        input_file_path=args.input_file,
        output_path=args.output
    )
    
    # Run pipeline
    logger.info("Starting pipeline...")
    logger.info(f"  Source: {args.source}")
    logger.info(f"  Output: {args.output}")
    
    try:
        summary = await engine.run(
            prop_ids=prop_ids,
            factor_ids=factor_ids
        )
        
        # Print summary
        logger.info("\n" + "=" * 50)
        logger.info("Pipeline Complete!")
        logger.info("=" * 50)
        logger.info(f"Total processed: {summary['total_processed']}")
        logger.info(f"Successful: {summary['successful']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"  - Validation errors: {summary['validation_errors']}")
        logger.info(f"  - Generation errors: {summary['generation_errors']}")
        logger.info(f"Elapsed time: {summary['elapsed_seconds']:.2f}s")
        logger.info(f"Output file: {summary['output_file']}")
        
        if summary['failures']:
            logger.info(f"\nFailures ({len(summary['failures'])}):")
            for failure in summary['failures'][:10]:  # Show first 10
                logger.info(f"  - Prop {failure['prop_id']}, Factor {failure['factor']}: {failure['error'][:100]}")
            if len(summary['failures']) > 10:
                logger.info(f"  ... and {len(summary['failures']) - 10} more")
        
        sys.exit(0 if summary['failed'] == 0 else 1)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

