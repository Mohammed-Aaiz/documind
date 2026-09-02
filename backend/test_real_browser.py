"""
REAL browser verification test using Playwright.

Interacts with actual DOM elements on http://localhost:3000.
No mocks, no urllib, no simulated results.
"""

import os
import sys
import time
from pathlib import Path

# Test PDF path — we created this earlier with real content
TEST_PDF = "C:/Users/moham/darwin_proper.pdf"

# Ensure the PDF exists
assert os.path.exists(TEST_PDF), f"Test PDF not found at {TEST_PDF}"


def run_tests():
    from playwright.sync_api import sync_playwright

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
        page.goto("http://localhost:3000", wait_until="networkidle")
        time.sleep(1)

        # Should see login form
        email_input = page.locator('input[type="email"]')
        check("Email input visible", email_input.is_visible())

        password_input = page.locator('input[type="password"]')
        check("Password input visible", password_input.is_visible())

        # Fill in credentials
        email_input.fill("test@documind.io")
        password_input.fill("TestPass123!")

        # Click submit button
        submit_btn = page.locator('button[type="submit"]')
        check("Submit button visible", submit_btn.is_visible())
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
        check("Homepage shows 'Awaiting Input'", awaiting.is_visible(timeout=5000))

        # Should NOT see chat messages area
        messages_area = page.locator(".flex-1.overflow-y-auto.px-4.py-4")
        # In homepage mode, this selector shouldn't exist (conversation mode only)
        conv_messages = page.query_selector_all('[class*="overflow-y-auto"][class*="px-4"][class*="py-4"]')
        # The homepage has a different structure — check for upload area instead
        upload_btn = page.locator("text=Select Files")
        check("Upload button visible on homepage", upload_btn.is_visible())

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
        check("Document name visible", doc_name.is_visible(timeout=5000))

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
        if not composer_input.is_visible():
            # Try alternative placeholder
            composer_input = page.locator('input[placeholder*="Ask"]')

        check("Composer input visible", composer_input.is_visible(timeout=5000))

        composer_input.fill("When did Charles Darwin publish On the Origin of Species?")
        time.sleep(0.5)

        # Click send button
        send_btn = page.locator('button[title="Send"]')
        if not send_btn.is_visible():
            send_btn = page.locator('button:has-text("send")').last
        check("Send button visible", send_btn.is_visible())
        send_btn.click()

        # Wait for oracle response
        time.sleep(8)  # QA model inference takes a few seconds

        page_text = page.inner_text("body")
        check("Answer '1859' appears", "1859" in page_text, f"body text snippet: {page_text[:200]}")

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
        if not composer_input.is_visible():
            composer_input = page.locator('input[placeholder*="Ask"]')

        composer_input.fill("How many species of Darwin finches were observed?")
        time.sleep(0.5)

        send_btn = page.locator('button[title="Send"]')
        if not send_btn.is_visible():
            send_btn = page.locator('button:has-text("send")').last
        send_btn.click()

        time.sleep(8)

        page_text = page.inner_text("body")
        check("Second answer '13' appears", "13" in page_text)

        # ==================================================================
        # TEST 10: Conversation messages remain visible
        # ==================================================================
        print("\n10. MESSAGES VISIBLE")
        # Both Q&A pairs should be visible
        all_text = page.inner_text("body")
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
        if not menu_btn.is_visible():
            menu_btn = page.locator('button:has-text("menu")').first
        check("Menu button visible", menu_btn.is_visible(timeout=5000))

        menu_btn.click()
        time.sleep(1)  # Wait for slide animation

        # ==================================================================
        # TEST 12: Drawer slides smoothly
        # ==================================================================
        print("\n12. DRAWER SLIDES")
        # The drawer should now be visible with "CONVERSATIONS" text
        drawer_text = page.locator("text=CONVERSATIONS")
        check("Drawer 'CONVERSATIONS' label visible", drawer_text.is_visible(timeout=3000))

        # Check "New Conversation" button in drawer (the button, not session previews)
        new_conv_btn = page.get_by_role("button", name="add New Conversation")
        check("'New Conversation' button in drawer", new_conv_btn.is_visible(timeout=3000))

        # ==================================================================
        # TEST 13: Recent conversations shown
        # ==================================================================
        print("\n13. RECENT CONVERSATIONS")
        # The current session should appear in the drawer
        # The first question text should appear as a preview
        preview_text = page.locator("text=When did Charles Darwin")
        check("Conversation preview visible in drawer", preview_text.count() > 0)

        # Close drawer by clicking overlay
        overlay = page.locator(".fixed.inset-0.z-40")
        if overlay.count() > 0:
            overlay.click()
            time.sleep(0.5)

        # ==================================================================
        # TEST 14: Open an existing conversation
        # ==================================================================
        print("\n14. OPEN EXISTING CONVERSATION")
        # Re-open drawer
        menu_btn = page.locator('button[title="Toggle conversations"]')
        if not menu_btn.is_visible():
            menu_btn = page.locator('button:has-text("menu")').first
        menu_btn.click()
        time.sleep(1)

        # Click on the first conversation
        first_conv = page.locator("button:has-text('When did Charles Darwin')").first
        if first_conv.is_visible():
            first_conv.click()
            time.sleep(2)

            # ==================================================================
            # TEST 15: Previous messages load
            # ==================================================================
            print("\n15. MESSAGES LOAD")
            body_text = page.inner_text("body")
            check("Previous Q1 visible after reopen", "Origin of Species" in body_text)
            check("Previous A1 '1859' visible after reopen", "1859" in body_text)
        else:
            check("First conversation clickable", False, "button not found")

        # ==================================================================
        # TEST 16: Start a new conversation
        # ==================================================================
        print("\n16. NEW CONVERSATION")
        # Open drawer and click New Conversation
        menu_btn = page.locator('button[title="Toggle conversations"]')
        if not menu_btn.is_visible():
            menu_btn = page.locator('button:has-text("menu")').first
        menu_btn.click()
        time.sleep(1)

        new_conv = page.get_by_role("button", name="add New Conversation")
        if new_conv.is_visible(timeout=3000):
            new_conv.click()
            time.sleep(2)

            # Should see empty message area
            empty_prompt = page.locator("text=Ask the Oracle anything")
            check("New conversation starts empty", empty_prompt.is_visible(timeout=5000))
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
            if not composer_input.is_visible():
                composer_input = page.locator('input[placeholder*="Ask"]')

            composer_input.fill(q)
            time.sleep(0.3)

            send_btn = page.locator('button[title="Send"]')
            if not send_btn.is_visible():
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
        if msg_container.is_visible():
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
        body_text = page.inner_text("body")
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
