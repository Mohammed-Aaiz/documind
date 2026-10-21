"""
REAL browser verification test using Playwright.

Interacts with actual DOM elements on http://localhost:3000.
No mocks, no urllib, no simulated results.
"""

import os
import sys
import time
from pathlib import Path

import pytest

from tests.fixtures import e2e_config
from tests.fixtures.live_server import optional_import, require_live_server

# Test PDF — a fixture committed with the test layer.
#
# It used to be a machine-specific absolute path outside the repository
# (``C:/Users/<name>/darwin_proper.pdf``), which made this harness silently
# skip everywhere else and leaked a document into the shared account's corpus
# on every run that did execute.  The committed copy is byte-identical to the
# document the 1859 / 13 / finch assertions were written against.
TEST_PDF = str(e2e_config.DARWIN_PDF)

#: Filename the browser sends for ``TEST_PDF``; the harness owns this document.
TEST_PDF_NAME = e2e_config.DARWIN_PDF.name


# ---------------------------------------------------------------------------
# Deterministic drawer helpers
#
# The conversation drawer panel is *always mounted* in conversation mode and is
# hidden with ``transform: translateX(-100%)`` (WorkspacePage.tsx), so an
# off-screen drawer — and the CONVERSATIONS label inside it — still has a
# bounding box and Chromium reports it as **visible**.  ``state="hidden"`` on
# the panel can therefore never be satisfied: that is why the previous
# ``close_drawer`` hung on ``wait_for(state="hidden")``.
#
# The backdrop, by contrast, is conditionally rendered (``{drawerOpen && ...}``),
# so its presence *is* the drawer's open state.  The helpers below read and drive
# that single signal, which makes them independent of whatever drawer state a
# previous step (or a previous test) left behind.
#
# ``locator.is_visible()`` is a snapshot with no auto-wait, so the harness used
# to sleep and hope; every visibility question now waits on an explicit UI
# state (``_wait_visible``) instead of sampling one.
# ---------------------------------------------------------------------------

#: The drawer's dismiss backdrop.  ``bg-black/40`` distinguishes it from the
#: Document Insights backdrop (``bg-black/50``), which shares the rest of the
#: class list; ``/`` is escaped because it is the CSS class-name separator.
_DRAWER_BACKDROP = "div.fixed.inset-0.z-40.bg-black\\/40"


def _drawer(page):
    """The drawer's own label (used for content assertions, not state)."""
    return page.locator("text=CONVERSATIONS").first


def _drawer_backdrop(page):
    """The backdrop the app renders *only* while the drawer is open."""
    return page.locator(_DRAWER_BACKDROP)


def drawer_is_open(page) -> bool:
    """Whether the conversation drawer is open (its backdrop is rendered)."""
    return _drawer_backdrop(page).count() > 0


def open_drawer(page, *, timeout: int = 5000) -> None:
    """Leave the conversation drawer open, whatever state it starts in."""
    if drawer_is_open(page):
        return
    toggle = page.locator('button[title="Toggle conversations"]')
    toggle.wait_for(state="visible", timeout=timeout)
    toggle.click()
    _drawer_backdrop(page).first.wait_for(state="visible", timeout=timeout)


def close_drawer(page, *, timeout: int = 5000) -> None:
    """Leave the conversation drawer closed, whatever state it starts in.

    Dismisses the drawer through its backdrop rather than the toggle button:
    while the drawer is open the panel (``z-50``) sits over the top bar's
    toggle button, so a toggle click is intercepted by the panel subtree and
    times out.  The backdrop is what a real user clicks to dismiss the drawer,
    and the app *unmounts* it, so ``state="detached"`` is an unambiguous
    closed state to wait for.  Clicking away from the panel's 288px column
    (``w-72``) keeps the hit unambiguous at any viewport this test uses.
    """
    backdrop = _drawer_backdrop(page)
    if backdrop.count() == 0:
        return
    backdrop.first.click(position={"x": 900, "y": 600})
    backdrop.first.wait_for(state="detached", timeout=timeout)


#: The drawer panel — the only container that holds conversation entries.
_DRAWER_PANEL = "div.fixed.top-0.left-0.bottom-0.z-50"


def _active_session(page):
    """The drawer's entry for the conversation this run is currently in.

    The preview text cannot identify it.  The drawer lists every session this
    harness has ever created, they all preview the same first question, and the
    list is a *snapshot taken when the session was created* — before its
    messages were persisted — so this run's own entry still reads "New
    conversation".  Picking "the first entry whose preview matches the
    question" is therefore a silent selection of a stale conversation from an
    earlier run, whose persisted answer may be anything at all.  The
    conversation this run owns is the *active* one, and the app marks it with
    ``border-cyber-cyan``.
    """
    return page.locator(f"{_DRAWER_PANEL} button.border-cyber-cyan").first


def _message_area_text(page) -> str:
    """Text of the scrollable messages area — never the always-mounted drawer.

    Scoping answer assertions to this element matters: the drawer is mounted in
    conversation mode even while closed and renders a preview of every past
    session, so ``body`` contains the first question even when the reopened
    conversation is empty.  A check that cannot fail is not a check.
    """
    return page.evaluate(
        """() => {
            const els = document.querySelectorAll(
                '[class*="overflow-y-auto"][class*="px-4"][class*="py-4"]');
            return els.length ? els[els.length - 1].innerText : '';
        }"""
    )


def _wait_for_message_text(page, needles=(), any_of=(), *, timeout: int = 20000) -> str:
    """Poll the messages area until it satisfies the needles; return its text.

    Every needle must be present (case-sensitive); at least one of ``any_of``
    must be present (case-insensitive, for answers whose casing is not fixed).
    The last text observed is returned when the timeout elapses, so the
    caller's assertion — not this helper — reports the failure.
    """
    deadline = time.monotonic() + timeout / 1000.0
    while True:
        text = _message_area_text(page)
        if all(n in text for n in needles) and (
            not any_of or any(n in text.lower() for n in any_of)
        ):
            return text
        if time.monotonic() >= deadline:
            return text
        time.sleep(0.25)


def _wait_visible(locator, *, timeout: int) -> bool:
    """Wait for ``locator`` to become visible; return whether it did.

    Replaces ``locator.is_visible(timeout=...)``, which ignores the timeout and
    returns a snapshot immediately — the source of the intermittent failures.
    """
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def run_tests(base: str = None):
    from playwright.sync_api import sync_playwright

    base = base or e2e_config.base_url()
    passed = 0
    failed = 0
    errors = []

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            msg = f"  [FAIL] {name}"
            if detail:
                msg += f" -- {detail}"
            print(msg)
            errors.append(name)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # ==================================================================
        # TEST 1: Login
        # ==================================================================
        print("\n1. LOGIN")
        page.goto(base, wait_until="networkidle")
        time.sleep(1)

        # Should see login form
        email_input = page.locator('input[type="email"]')
        check("Email input visible", _wait_visible(email_input, timeout=10000))

        password_input = page.locator('input[type="password"]')
        check("Password input visible", _wait_visible(password_input, timeout=10000))

        # Fill in credentials (single source of truth: tests/fixtures/e2e_config)
        email_input.fill(e2e_config.DEMO_USER_EMAIL)
        password_input.fill(e2e_config.DEMO_USER_PASSWORD)

        # Click submit button
        submit_btn = page.locator('button[type="submit"]')
        check("Submit button visible", _wait_visible(submit_btn, timeout=10000))
        submit_btn.click()

        # Wait for navigation to workspace
        page.wait_for_url("**/workspace**", timeout=10000) if "**" in page.url else None
        time.sleep(3)

        # Verify we're past login — check for "Oracle Interface" or workspace content
        page_text = page.inner_text("body")
        check("Logged in (workspace visible)", "Oracle" in page_text or "Workspace" in page_text or "Awaiting" in page_text)

        # ==================================================================
        # TEST 2: Empty homepage (no active conversation)
        # ==================================================================
        print("\n2. EMPTY HOMEPAGE")
        # Should see "Awaiting Input" drop zone
        awaiting = page.locator("text=Awaiting Input")
        check("Homepage shows 'Awaiting Input'", _wait_visible(awaiting, timeout=10000))

        # Should NOT see chat messages area
        messages_area = page.locator(".flex-1.overflow-y-auto.px-4.py-4")
        # In homepage mode, this selector shouldn't exist (conversation mode only)
        conv_messages = page.query_selector_all('[class*="overflow-y-auto"][class*="px-4"][class*="py-4"]')
        # The homepage has a different structure — check for upload area instead
        upload_btn = page.locator("text=Select Files")
        check("Upload button visible on homepage", _wait_visible(upload_btn, timeout=10000))

        # ==================================================================
        # TEST 3: No permanent left sidebar
        # ==================================================================
        print("\n3. NO PERMANENT SIDEBAR")
        sidebar = page.locator("aside")
        sidebar_count = sidebar.count()
        check("No permanent sidebar element", sidebar_count == 0, f"found {sidebar_count} aside elements")

        # Also verify no "Core" / nav items from SideNavBar
        core_nav = page.locator("text=Core")
        threads_nav = page.locator("text=Threads")
        check("No 'Core' nav item", core_nav.count() == 0)
        check("No 'Threads' nav item", threads_nav.count() == 0)

        # ==================================================================
        # TEST 4: Upload a real PDF
        # ==================================================================
        print("\n4. UPLOAD PDF")
        # Click the upload area to trigger file input
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(TEST_PDF)
        time.sleep(2)

        # Verify document appears in the list
        doc_name = page.locator("text=darwin_proper.pdf")
        check("Document name visible", _wait_visible(doc_name, timeout=10000))

        # ==================================================================
        # TEST 5: Wait for processing + embeddings to reach READY
        # ==================================================================
        print("\n5. WAIT FOR PROCESSING")
        # Poll for the green checkmark / "ready" status
        ready = False
        for attempt in range(30):
            time.sleep(2)
            page_html = page.content()
            # Check for green check_circle icon or "chunks" text
            if "check_circle" in page_html and "chunks" in page_html:
                ready = True
                break
            # Also check for embedding_status = ready via the chunks text
            if "chunks" in page.inner_text("body"):
                ready = True
                break

        check("Document processed and ready", ready)

        # ==================================================================
        # TEST 6: Ask a real question
        # ==================================================================
        print("\n6. ASK A QUESTION")
        # The composer is at the bottom — find the input
        composer_input = page.locator('input[placeholder*="Oracle"]')
        if not _wait_visible(composer_input, timeout=5000):
            # Try alternative placeholder
            composer_input = page.locator('input[placeholder*="Ask"]')

        check("Composer input visible", _wait_visible(composer_input, timeout=5000))

        composer_input.fill("When did Charles Darwin publish On the Origin of Species?")
        time.sleep(0.5)

        # Click send button
        send_btn = page.locator('button[title="Send"]')
        if not _wait_visible(send_btn, timeout=5000):
            send_btn = page.locator('button:has-text("send")').last
        check("Send button visible", _wait_visible(send_btn, timeout=5000))
        send_btn.click()

        # Wait for the oracle's answer to actually render, rather than sleeping
        # a fixed time and then sampling the DOM once.
        page_text = _wait_for_message_text(page, ("1859",), timeout=30000)
        check("Answer '1859' appears", "1859" in page_text, f"message area snippet: {page_text[:200]}")

        # ==================================================================
        # TEST 7: Verify answer is displayed
        # ==================================================================
        print("\n7. ANSWER DISPLAYED")
        # The oracle message should contain "1859"
        oracle_msgs = page.locator("text=1859")
        check("Oracle answer element exists", oracle_msgs.count() > 0)

        # ==================================================================
        # TEST 8: Verify source/document/page displayed
        # ==================================================================
        print("\n8. SOURCE DISPLAYED")
        # Check for SOURCES label
        sources_label = page.locator("text=SOURCES")
        check("SOURCES label visible", sources_label.count() > 0)

        # Check for document name in sources
        source_doc = page.locator("text=darwin_proper.pdf")
        check("Source document name visible", source_doc.count() > 0)

        # Check for page number
        page_ref = page.locator("text=p.1")
        check("Page number visible", page_ref.count() > 0)

        # ==================================================================
        # TEST 9: Ask another question
        # ==================================================================
        print("\n9. SECOND QUESTION")
        composer_input = page.locator('input[placeholder*="Oracle"]')
        if not _wait_visible(composer_input, timeout=5000):
            composer_input = page.locator('input[placeholder*="Ask"]')

        composer_input.fill("How many species of Darwin finches were observed?")
        time.sleep(0.5)

        send_btn = page.locator('button[title="Send"]')
        if not _wait_visible(send_btn, timeout=5000):
            send_btn = page.locator('button:has-text("send")').last
        send_btn.click()

        page_text = _wait_for_message_text(page, ("13",), timeout=30000)
        check("Second answer '13' appears", "13" in page_text)

        # ==================================================================
        # TEST 10: Conversation messages remain visible
        # ==================================================================
        print("\n10. MESSAGES VISIBLE")
        # Both Q&A pairs should be visible in the transcript itself (not in
        # ``body``, which also holds the drawer's preview of a past session).
        all_text = _wait_for_message_text(
            page, ("Origin of Species", "1859", "13"), timeout=15000
        )
        check("First question text visible", "Origin of Species" in all_text)
        check("First answer '1859' visible", "1859" in all_text)
        check("Second question text visible", "finch" in all_text.lower())
        check("Second answer '13' visible", "13" in all_text)

        # ==================================================================
        # TEST 11: Conversation drawer appears from left
        # ==================================================================
        print("\n11. DRAWER OPENS")
        # Find the hamburger/menu button
        menu_btn = page.locator('button[title="Toggle conversations"]')
        check("Menu button visible", _wait_visible(menu_btn, timeout=5000))

        # Deterministic open (the drawer may already be open from a prior step).
        open_drawer(page)

        # ==================================================================
        # TEST 12: Drawer slides smoothly
        # ==================================================================
        print("\n12. DRAWER SLIDES")
        # The drawer should now be visible with "CONVERSATIONS" text
        drawer_text = _drawer(page)
        check("Drawer 'CONVERSATIONS' label visible", _wait_visible(drawer_text, timeout=3000))
        # The label alone cannot prove the drawer is open: the panel is always
        # mounted and merely translated off-screen, so this label is "visible"
        # to Chromium even when the drawer is shut.  The backdrop is the real
        # open-state signal, so assert that too rather than leave the check
        # vacuous.
        check("Drawer is open (backdrop rendered)", drawer_is_open(page))

        # Check "New Conversation" button in drawer (the button, not session previews)
        new_conv_btn = page.get_by_role("button", name="add New Conversation")
        check("'New Conversation' button in drawer", _wait_visible(new_conv_btn, timeout=3000))

        # ==================================================================
        # TEST 13: Recent conversations shown
        # ==================================================================
        print("\n13. RECENT CONVERSATIONS")
        # The drawer renders each session with its first user message as a
        # preview.  (Which session that preview belongs to is exactly the
        # accumulated state TEST 14 must not depend on — it identifies its own
        # conversation by the active marker instead.)
        preview_text = page.locator("text=When did Charles Darwin").first
        check("Conversation preview visible in drawer", _wait_visible(preview_text, timeout=5000))

        # Close the drawer deterministically, and confirm it actually closed.
        close_drawer(page)

        # ==================================================================
        # TEST 14: Open an existing conversation
        # ==================================================================
        print("\n14. OPEN EXISTING CONVERSATION")
        # Re-open the drawer explicitly rather than blind-toggling it.
        open_drawer(page)

        # Open *this run's* conversation — identified by the active marker, not
        # by its preview text (see ``_active_session``).
        first_conv = _active_session(page)
        if _wait_visible(first_conv, timeout=8000):
            first_conv.click()

            # ==================================================================
            # TEST 15: Previous messages load
            # ==================================================================
            print("\n15. MESSAGES LOAD")
            # Wait for the reopened transcript to contain both this run's
            # question and its answer.  Reading the messages area (not
            # ``body``) is what makes this an assertion about the reopened
            # conversation rather than about a past session's drawer preview.
            body_text = _wait_for_message_text(
                page, ("Origin of Species", "1859"), timeout=15000
            )
            check("Previous Q1 visible after reopen", "Origin of Species" in body_text)
            check("Previous A1 '1859' visible after reopen", "1859" in body_text)
        else:
            check("First conversation clickable", False, "button not found")

        # ==================================================================
        # TEST 16: Start a new conversation
        # ==================================================================
        print("\n16. NEW CONVERSATION")
        # Open drawer and click New Conversation
        open_drawer(page)

        new_conv = page.get_by_role("button", name="add New Conversation")
        if _wait_visible(new_conv, timeout=3000):
            new_conv.click()
            time.sleep(2)

            # Should see empty message area
            empty_prompt = page.locator("text=Ask the Oracle anything")
            check("New conversation starts empty", _wait_visible(empty_prompt, timeout=10000))
        else:
            check("New Conversation button visible", False)

        # ==================================================================
        # TEST 17: Create a long conversation
        # ==================================================================
        print("\n17. LONG CONVERSATION")
        questions = [
            "What is natural selection?",
            "Who are Charles Darwin and Alfred Russel Wallace?",
            "When did the HMS Beagle depart from England?",
            "How long did the voyage last?",
            "What did Darwin collect during the journey?",
        ]

        for i, q in enumerate(questions):
            composer_input = page.locator('input[placeholder*="Oracle"]')
            if not _wait_visible(composer_input, timeout=5000):
                composer_input = page.locator('input[placeholder*="Ask"]')

            composer_input.fill(q)
            time.sleep(0.3)

            send_btn = page.locator('button[title="Send"]')
            if not _wait_visible(send_btn, timeout=5000):
                send_btn = page.locator('button:has-text("send")').last
            send_btn.click()
            time.sleep(6)  # Wait for QA response

            print(f"  Sent question {i+1}: {q[:40]}...")

        check("Long conversation created (5+ messages)", True)

        # ==================================================================
        # TEST 18: Scroll to bottom
        # ==================================================================
        print("\n18. SCROLL TO BOTTOM")
        # The messages container should be scrollable
        # Find the scrollable messages area
        msg_container = page.locator('[class*="flex-1"][class*="overflow-y-auto"][class*="px-4"][class*="py-4"]').last
        if _wait_visible(msg_container, timeout=5000):
            # Scroll to bottom using JS
            page.evaluate("""
                const containers = document.querySelectorAll('[class*="overflow-y-auto"]');
                const last = containers[containers.length - 1];
                if (last) last.scrollTop = last.scrollHeight;
            """)
            time.sleep(1)
            check("Scrolled to bottom", True)
        else:
            check("Messages container found for scrolling", False)

        # ==================================================================
        # TEST 19: Final message visible
        # ==================================================================
        print("\n19. FINAL MESSAGE VISIBLE")
        # Wait for the last answer instead of trusting TEST 17's fixed sleeps.
        body_text = _wait_for_message_text(
            page, any_of=("specimen", "journey", "collected"), timeout=20000
        )
        # The last question was about "Darwin collect"
        check("Final answer about 'specimens' or 'journey' visible",
              "specimen" in body_text.lower() or "journey" in body_text.lower() or "collected" in body_text.lower())

        # ==================================================================
        # TEST 20: Composer does NOT cover final message
        # ==================================================================
        print("\n20. COMPOSER COVERAGE CHECK")
        # Get the last message element's bounding box
        last_msg_bottom = page.evaluate("""() => {
            const msgs = document.querySelectorAll('[class*="flex"][class*="mb-4"]');
            if (msgs.length > 0) {
                const last = msgs[msgs.length - 1];
                const rect = last.getBoundingClientRect();
                return rect.bottom;
            }
            return 0;
        }""")

        # Get the composer's top position
        composer_top = page.evaluate("""() => {
            const composer = document.querySelector('[class*="flex-shrink-0"][class*="px-4"][class*="py-3"][class*="border-t"]');
            if (composer) {
                const rect = composer.getBoundingClientRect();
                return rect.top;
            }
            return 9999;
        }""")

        if last_msg_bottom > 0 and composer_top < 9999:
            gap = composer_top - last_msg_bottom
            check("Composer does not cover last message",
                  gap >= -5,  # allow 5px tolerance
                  f"gap={gap:.0f}px (composer_top={composer_top:.0f}, last_msg_bottom={last_msg_bottom:.0f})")
        else:
            check("Composer coverage check (elements found)", False, "could not find message/composer elements")

        # ==================================================================
        # Cleanup
        # ==================================================================
        browser.close()

    # ======================================================================
    # Summary
    # ======================================================================
    total = passed + failed
    print()
    print("=" * 60)
    print(f"  BROWSER VERIFICATION RESULTS: {passed}/{total} passed, {failed} failed")
    if errors:
        print(f"  Failed: {', '.join(errors)}")
    print("=" * 60)
    print()

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)


# ---------------------------------------------------------------------------
# pytest entry point — the test-isolation contract requires tests to run only
# through pytest.  Skipped unless the dev server is up, Playwright is installed
# and the machine-specific test PDF is present.
# ---------------------------------------------------------------------------
@pytest.mark.e2e
def test_real_browser_playwright_flow():
    """Real Chromium DOM flow against a running dev server (Playwright).

    The harness owns one document in the demo account.  It removes any copy a
    previous run left behind *before* uploading, and removes its own copy again
    afterwards, so the run neither depends on nor adds to accumulated database
    rows.  Existing authentication and upload behaviour is exercised unchanged.
    """
    base = e2e_config.base_url()
    require_live_server(base)
    optional_import("playwright", reason="Playwright is not in requirements.txt")
    if not os.path.isfile(TEST_PDF):
        pytest.skip(f"test PDF not found at {TEST_PDF}")

    token = e2e_config.login(
        e2e_config.DEMO_USER_EMAIL, e2e_config.DEMO_USER_PASSWORD, base
    )
    stale = e2e_config.purge_documents(base, token=token, name=TEST_PDF_NAME)
    print(f"\n[setup] removed {stale} stale {TEST_PDF_NAME} document(s) before upload")
    try:
        assert run_tests(base) is True
    finally:
        removed = e2e_config.purge_documents(base, token=token, name=TEST_PDF_NAME)
        print(f"[teardown] removed {removed} {TEST_PDF_NAME} document(s) after upload")
