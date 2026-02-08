#!/usr/bin/env python3
"""
Generate a sample GIPA application as PDF to preview the document format.

This script bypasses the LLM (no API key needed) by using pre-built data
and the fallback keyword expander, then pipes the markdown through the
existing PDF generator.

Run with:
    .venv/bin/python testing/test_gipa_pdf.py
"""

import asyncio
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.tools.gipa_agent.clarification_engine import GIPARequestData, TargetPerson
from server.tools.gipa_agent.document_generator import GIPADocumentGenerator
from server.tools.gipa_agent.jurisdiction_config import NSW_CONFIG, FEDERAL_CONFIG
from server.tools.pdf_generator import generate_pdf_report


async def build_sample_document_nsw() -> str:
    """Build a sample NSW GIPA document (nonprofit, with targets, multiple keywords)."""
    data = GIPARequestData(
        agency_name="Department of Planning and Environment",
        agency_email="gipa@dpie.nsw.gov.au",
        applicant_name="Sarah Mitchell",
        applicant_organization="Environment Defenders Office",
        applicant_type="nonprofit",
        charity_status="ABN 72 002 880 864",
        public_interest_justification=(
            "This information is critical for understanding government "
            "decision-making regarding koala habitat conservation in the "
            "Greater Sydney region, particularly in light of ongoing "
            "development approvals that may impact listed threatened species."
        ),
        start_date="1 January 2023",
        end_date="31 December 2024",
        targets=[
            TargetPerson(
                name="Minister for Environment",
                role="Minister",
                direction="both",
            ),
            TargetPerson(
                name="Dr James Chen",
                role="Director of Biodiversity Policy",
                direction="sender",
            ),
            TargetPerson(
                name="Rachel Wong",
                role="Deputy Secretary, Planning",
                direction="receiver",
            ),
        ],
        keywords=["koala", "habitat", "development approval", "SEPP 44"],
        jurisdiction="NSW",
        fee_reduction_eligible=True,
        summary_sentence=(
            "All correspondence held by the Department of Planning and Environment "
            "involving the Minister for Environment, Dr James Chen (Director of "
            "Biodiversity Policy), and Rachel Wong (Deputy Secretary, Planning) "
            "containing references to koala, habitat, development approval, and "
            "SEPP 44, for the period 1 January 2023 to 31 December 2024."
        ),
    )

    generator = GIPADocumentGenerator(synonym_expander=None)
    return await generator.generate(data, NSW_CONFIG)


async def build_sample_document_federal() -> str:
    """Build a sample Federal FOI document (journalist, no targets)."""
    data = GIPARequestData(
        agency_name="Department of Home Affairs",
        agency_email="foi@homeaffairs.gov.au",
        applicant_name="David Park",
        applicant_organization="The Guardian Australia",
        applicant_type="journalist",
        public_interest_justification=(
            "The public has a right to understand how visa processing "
            "delays are affecting skilled migration and the Australian "
            "economy, particularly given recent media reports of record "
            "processing backlogs."
        ),
        start_date="1 July 2024",
        end_date="31 January 2025",
        targets=[],
        keywords=["visa backlog", "processing delay", "skilled migration"],
        jurisdiction="Federal",
        fee_reduction_eligible=True,
        summary_sentence=(
            "All correspondence held by the Department of Home Affairs "
            "containing references to visa backlog, processing delay, and "
            "skilled migration, for the period 1 July 2024 to 31 January 2025."
        ),
    )

    generator = GIPADocumentGenerator(synonym_expander=None)
    return await generator.generate(data, FEDERAL_CONFIG)


async def build_sample_document_individual() -> str:
    """Build a sample NSW GIPA document (individual, single keyword, no fee reduction)."""
    data = GIPARequestData(
        agency_name="NSW Police Force",
        agency_email=None,
        applicant_name="Tom Nguyen",
        applicant_type="individual",
        public_interest_justification=(
            "Understanding police use-of-force reporting is vital for "
            "community trust and accountability in law enforcement."
        ),
        start_date="1 June 2024",
        end_date="30 November 2024",
        targets=[
            TargetPerson(
                name="Assistant Commissioner, Metropolitan Field Operations",
                direction="both",
            ),
        ],
        keywords=["use of force"],
        jurisdiction="NSW",
        fee_reduction_eligible=False,
        summary_sentence=(
            "All correspondence held by NSW Police Force involving the "
            "Assistant Commissioner, Metropolitan Field Operations, "
            "containing references to use of force, "
            "for the period 1 June 2024 to 30 November 2024."
        ),
    )

    generator = GIPADocumentGenerator(synonym_expander=None)
    return await generator.generate(data, NSW_CONFIG)


async def main():
    print("=" * 60)
    print("GIPA / FOI Application - PDF Generation Test")
    print("=" * 60)

    # --- Document 1: NSW Nonprofit (full-featured) ---
    print(
        "\n[1/3] Generating NSW GIPA application (nonprofit, 3 targets, 4 keywords)..."
    )
    md_nsw = await build_sample_document_nsw()

    print("\n--- MARKDOWN PREVIEW (NSW) ---")
    print(md_nsw[:500])
    print("...\n")

    path1 = generate_pdf_report.invoke(
        {
            "markdown_content": md_nsw,
            "filename": "gipa_sample_nsw_nonprofit.pdf",
            "sender_email": "sarah.mitchell@edo.org.au",
            "enable_quote_images": False,
        }
    )
    print(f"PDF saved: {path1}")

    # --- Document 2: Federal Journalist ---
    print("\n[2/3] Generating Federal FOI application (journalist, no targets)...")
    md_fed = await build_sample_document_federal()

    path2 = generate_pdf_report.invoke(
        {
            "markdown_content": md_fed,
            "filename": "foi_sample_federal_journalist.pdf",
            "sender_email": "david.park@theguardian.com",
            "enable_quote_images": False,
        }
    )
    print(f"PDF saved: {path2}")

    # --- Document 3: Individual ---
    print("\n[3/3] Generating NSW GIPA application (individual, single keyword)...")
    md_ind = await build_sample_document_individual()

    path3 = generate_pdf_report.invoke(
        {
            "markdown_content": md_ind,
            "filename": "gipa_sample_nsw_individual.pdf",
            "sender_email": "tom.nguyen@gmail.com",
            "enable_quote_images": False,
        }
    )
    print(f"PDF saved: {path3}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("DONE - 3 PDFs generated:")
    print(f"  1. {path1}")
    print(f"  2. {path2}")
    print(f"  3. {path3}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
