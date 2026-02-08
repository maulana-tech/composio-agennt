#!/usr/bin/env python3
"""
Live GIPA test script: Full flow from start → answer → generate → PDF → email.

This script runs against the REAL server (localhost:8002) using REAL LLM calls
(Gemini) and REAL email sending (Composio Gmail).

Prerequisites:
    1. Server running: .venv/bin/python -m uvicorn server.api:app --reload --port 8002
    2. Environment variables set: GOOGLE_API_KEY, COMPOSIO_API_KEY
    3. Gmail connected via Composio (user_id="default")

Usage:
    # Full flow including email send:
    .venv/bin/python testing/test_gipa_live.py --email firdaussyah03@gmail.com

    # Generate document only (no email):
    .venv/bin/python testing/test_gipa_live.py

    # Custom server URL:
    .venv/bin/python testing/test_gipa_live.py --url http://localhost:8002

    # Skip PDF generation:
    .venv/bin/python testing/test_gipa_live.py --email firdaussyah03@gmail.com --no-pdf
"""

import argparse
import asyncio
import json
import sys
import os
import time

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8002"
SESSION_ID = f"live-test-{int(time.time())}"

# The sample GIPA request data - one big answer to test AI extraction
SAMPLE_ANSWERS = [
    # Answer 1: Provide most info in one go
    (
        "Nama saya Firdaus Syah, saya bekerja di Environmental Research Group. "
        "Saya ingin meminta dokumen dari Department of Primary Industries. "
        "Saya mencari semua catatan rapat (meeting minutes) dari Badan Pengatur Jalan Tol (BPJT) "
        "yang mencantumkan pembangunan jalan tol, proyek infrastruktur tol, investasi jalan tol, "
        "tarif tol, dan perjanjian konsesi jalan tol. "
        "Periode yang saya minta dari 1 Januari 2022 sampai 30 Januari 2022. "
        "Ini untuk proyek riset tentang transparansi kebijakan infrastruktur publik "
        "dan bagaimana keputusan tol mempengaruhi masyarakat."
    ),
    # Answer 2: Provide targets if asked
    (
        "Target utama adalah Direktur BPJT dan Kepala Divisi Perencanaan Infrastruktur. "
        "Kata kunci tambahan: BPJT, jalan tol, toll road, concession agreement, tarif tol."
    ),
    # Answer 3: Confirm if asked
    "Ya, informasi tersebut sudah benar dan lengkap.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def print_header(text: str):
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}")


def print_step(step: int, total: int, text: str):
    print(f"\n[{step}/{total}] {text}")
    print("-" * 50)


def print_response(data: dict, show_full_doc: bool = False):
    """Pretty-print a GIPA API response."""
    success = data.get("success", False)
    status = data.get("status", "unknown")
    message = data.get("message", "")
    error = data.get("error")
    document = data.get("document")

    icon = "OK" if success else "FAIL"
    print(f"  [{icon}] status={status}")

    if error:
        print(f"  ERROR: {error}")

    # Truncate message for readability
    if len(message) > 500 and not show_full_doc:
        print(f"  Message: {message[:500]}...")
    else:
        print(f"  Message: {message}")

    if document:
        if show_full_doc:
            print(f"\n  --- DOCUMENT ---")
            print(document)
            print(f"  --- END DOCUMENT ---")
        else:
            print(f"  Document: ({len(document)} chars) {document[:200]}...")

    return success, status, message, document


async def run_live_test(
    base_url: str,
    recipient_email: str | None,
    generate_pdf: bool,
    user_id: str,
):
    total_steps = 3  # start + answers + generate
    if generate_pdf:
        total_steps += 1
    if recipient_email:
        total_steps += 1

    current_step = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        # ==================================================================
        # Step 1: Check status (should be no session)
        # ==================================================================
        current_step += 1
        print_step(current_step, total_steps + 1, "Checking session status...")
        resp = await client.post("/gipa/status", json={"session_id": SESSION_ID})
        if resp.status_code == 200:
            data = resp.json()
            print_response(data)
        else:
            print(f"  Status check failed: {resp.status_code}")

        # ==================================================================
        # Step 2: Start GIPA session
        # ==================================================================
        current_step += 1
        print_step(current_step, total_steps + 1, "Starting GIPA session...")
        resp = await client.post("/gipa/start", json={"session_id": SESSION_ID})
        assert resp.status_code == 200, f"Start failed: {resp.status_code} {resp.text}"
        data = resp.json()
        success, status, message, _ = print_response(data)
        assert success, "Start request failed"
        assert status == "collecting"

        # ==================================================================
        # Step 3: Answer clarification questions (multi-turn)
        # ==================================================================
        current_step += 1
        print_step(
            current_step, total_steps + 1, "Answering clarification questions..."
        )

        final_status = "collecting"
        for i, answer in enumerate(SAMPLE_ANSWERS, 1):
            print(f"\n  >>> Answer {i}: {answer[:80]}...")
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": SESSION_ID, "answer": answer},
            )
            assert resp.status_code == 200, (
                f"Answer failed: {resp.status_code} {resp.text}"
            )
            data = resp.json()
            success, final_status, message, _ = print_response(data)
            assert success, f"Answer {i} failed"

            if final_status == "ready":
                print(f"\n  All data collected after {i} answer(s)!")
                break

        if final_status != "ready":
            print("\n  WARNING: Session not ready after all answers.")
            print("  Checking session status...")
            resp = await client.post("/gipa/status", json={"session_id": SESSION_ID})
            data = resp.json()
            print_response(data)

            # Try one more confirmation
            print("\n  Sending confirmation...")
            resp = await client.post(
                "/gipa/answer",
                json={
                    "session_id": SESSION_ID,
                    "answer": (
                        "My name is Firdaus Syah, I work for Environmental Research Group as a nonprofit. "
                        "The agency is Department of Primary Industries. "
                        "Keywords: BPJT, jalan tol, toll road. "
                        "Period: 1 January 2022 to 30 January 2022. "
                        "Public interest: transparency in public infrastructure policy decisions."
                    ),
                },
            )
            data = resp.json()
            success, final_status, message, _ = print_response(data)

        # ==================================================================
        # Step 4: Generate GIPA document
        # ==================================================================
        current_step += 1
        print_step(current_step, total_steps + 1, "Generating GIPA document...")
        resp = await client.post("/gipa/generate", json={"session_id": SESSION_ID})
        assert resp.status_code == 200, (
            f"Generate failed: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        success, status, message, document = print_response(data, show_full_doc=True)

        if not success or not document:
            print("\n  FAILED to generate document. Aborting.")
            return False

        print(f"\n  Document generated successfully! ({len(document)} characters)")

        # ==================================================================
        # Step 5: Generate PDF (optional)
        # ==================================================================
        pdf_path = None
        if generate_pdf:
            current_step += 1
            print_step(current_step, total_steps + 1, "Generating PDF...")

            resp = await client.post(
                "/generate-pdf",
                json={
                    "markdown_content": document,
                    "filename": f"gipa_live_test_{SESSION_ID}.pdf",
                },
            )

            if resp.status_code == 200:
                # The PDF endpoint might return a streaming response or JSON
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    pdf_data = resp.json()
                    pdf_path = pdf_data.get("path") or pdf_data.get("file_path")
                    print(f"  PDF generated: {pdf_path}")
                elif "application/pdf" in content_type:
                    # Save the PDF bytes
                    pdf_filename = f"gipa_live_test_{SESSION_ID}.pdf"
                    pdf_dir = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "attacchment",
                    )
                    os.makedirs(pdf_dir, exist_ok=True)
                    pdf_path = os.path.join(pdf_dir, pdf_filename)
                    with open(pdf_path, "wb") as f:
                        f.write(resp.content)
                    print(f"  PDF saved: {pdf_path} ({len(resp.content)} bytes)")
                else:
                    print(f"  Unexpected content-type: {content_type}")
                    print(f"  Response: {resp.text[:300]}")
            else:
                print(f"  PDF generation failed: {resp.status_code}")
                print(f"  Falling back to local PDF generation...")
                # Fallback: generate PDF locally
                sys.path.insert(
                    0,
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                )
                from server.tools.pdf_generator import generate_pdf_report

                pdf_path = generate_pdf_report.invoke(
                    {
                        "markdown_content": document,
                        "filename": f"gipa_live_test_{SESSION_ID}.pdf",
                        "sender_email": "gipa-test@example.com",
                        "enable_quote_images": False,
                    }
                )
                print(f"  PDF generated locally: {pdf_path}")

        # ==================================================================
        # Step 6: Send email (optional)
        # ==================================================================
        if recipient_email:
            current_step += 1
            print_step(
                current_step, total_steps + 1, f"Sending email to {recipient_email}..."
            )

            # Use the /chat endpoint with a direct instruction to send email
            # This goes through the ReAct agent which has Gmail tools
            email_body = document

            # Try direct chat endpoint to leverage the agent's email capability
            chat_message = (
                f"Kirim dokumen GIPA ini ke email {recipient_email} dengan subject "
                f"'GIPA Application - Live Test {SESSION_ID}'. "
            )

            if pdf_path and os.path.exists(pdf_path):
                chat_message += f"Lampirkan file PDF dari path: {pdf_path}"
            else:
                chat_message += (
                    "Kirim sebagai body email (tanpa attachment). "
                    "Ini isi dokumennya:\n\n" + email_body
                )

            print(f"  Sending via /chat endpoint...")
            print(f"  Chat message: {chat_message[:200]}...")

            resp = await client.post(
                "/chat",
                json={
                    "message": chat_message,
                    "user_id": user_id,
                    "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
                    "history": [],
                },
            )

            if resp.status_code == 200:
                chat_data = resp.json()
                chat_message_resp = chat_data.get("message", "")
                print(f"  Chat response: {chat_message_resp[:500]}")

                if (
                    "berhasil" in chat_message_resp.lower()
                    or "sent" in chat_message_resp.lower()
                    or "success" in chat_message_resp.lower()
                ):
                    print(f"\n  Email sent successfully to {recipient_email}!")
                else:
                    print(
                        f"\n  Email may not have been sent. Check the response above."
                    )
            else:
                print(f"  Chat endpoint failed: {resp.status_code}")
                print(f"  Response: {resp.text[:300]}")

        # ==================================================================
        # Final: Verify session status
        # ==================================================================
        print_header("Final Status Check")
        resp = await client.post("/gipa/status", json={"session_id": SESSION_ID})
        if resp.status_code == 200:
            data = resp.json()
            print_response(data)

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Live GIPA test: start → answer → generate → PDF → email"
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Recipient email address (e.g., firdaussyah03@gmail.com). "
        "If not provided, skips email sending.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"Server base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF generation",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="default",
        help="Composio user_id for Gmail (default: 'default')",
    )

    args = parser.parse_args()

    print_header("GIPA Live Test")
    print(f"  Server:     {args.url}")
    print(f"  Session:    {SESSION_ID}")
    print(f"  Email:      {args.email or '(none - skipping email)'}")
    print(f"  PDF:        {'No' if args.no_pdf else 'Yes'}")
    print(f"  User ID:    {args.user_id}")

    # Quick connectivity check
    print(f"\n  Checking server connectivity...")
    try:
        resp = httpx.get(f"{args.url}/docs", timeout=5)
        if resp.status_code == 200:
            print(f"  Server is running!")
        else:
            print(f"  WARNING: Server returned {resp.status_code}")
    except httpx.ConnectError:
        print(f"  ERROR: Cannot connect to {args.url}")
        print(f"  Start the server first:")
        print(f"    .venv/bin/python -m uvicorn server.api:app --reload --port 8002")
        sys.exit(1)

    # Run the test
    success = asyncio.run(
        run_live_test(
            base_url=args.url,
            recipient_email=args.email,
            generate_pdf=not args.no_pdf,
            user_id=args.user_id,
        )
    )

    print_header("TEST RESULT")
    if success:
        print("  ALL STEPS COMPLETED SUCCESSFULLY")
    else:
        print("  SOME STEPS FAILED - check output above")
    print()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
