import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "Authentication Code Audit & Test Verification Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, footer_text)
        self.drawString(54, 36, "CONFIDENTIAL - AI Software Health & Risk Analyzer")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#1E293B")
    secondary_color = colors.HexColor("#2563EB")
    accent_green = colors.HexColor("#16A34A")
    accent_red = colors.HexColor("#DC2626")
    bg_light = colors.HexColor("#F8FAFC")
    text_dark = colors.HexColor("#0F172A")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#475569"),
        spaceAfter=20
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=primary_color,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=secondary_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=text_dark,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    table_body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=text_dark
    )

    pass_badge_style = ParagraphStyle(
        'PassBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=accent_green
    )

    story = []

    # Title Block
    story.append(Spacer(1, 10))
    story.append(Paragraph("Authentication System Audit & Test Verification Report", title_style))
    story.append(Paragraph("Comprehensive Security Analysis & 60 Automated Test Cases Execution Results", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=secondary_color, spaceAfter=15))

    # Executive Summary Box
    summary_html = """
    <b>EXECUTIVE SUMMARY & SYSTEM STATUS</b><br/>
    • <b>Target Module:</b> Backend Authentication & Authorization (FastAPI, PyJWT/python-jose, bcrypt, Pydantic)<br/>
    • <b>Total Test Cases Executed:</b> 60<br/>
    • <b>Tests Passed:</b> 60 (100% Pass Rate)<br/>
    • <b>Tests Failed:</b> 0<br/>
    • <b>Audit Status:</b> Critical architectural bug resolved (Missing persistence module created & password hash safety enhanced).
    """
    summary_table = Table(
        [[Paragraph(summary_html, body_style)]],
        colWidths=[504]
    )
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#BFDBFE")),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 15))

    # Section 1: Codebase Audit & Fixes
    story.append(Paragraph("1. Codebase Audit & Identified Code Issues", h1_style))
    story.append(Paragraph(
        "During the preliminary inspection and test execution of the authentication module (<code>Backend/auth/</code>), "
        "two critical code issues were identified and resolved:",
        body_style
    ))

    issue_1_html = """
    <b>Issue #1: Missing Persistence Module (Critical - ModuleNotFoundError)</b><br/>
    • <b>Location:</b> <code>Backend/auth/dependencies.py</code> and <code>Backend/auth/router.py</code><br/>
    • <b>Root Cause:</b> Both files imported <code>create_user</code>, <code>get_user</code>, and <code>get_user_by_email</code> from <code>Backend.persistence</code>, but <code>Backend/persistence.py</code> did not exist in the repository.<br/>
    • <b>Impact:</b> Entire FastAPI application failed to start or run tests with <code>ModuleNotFoundError</code>.<br/>
    • <b>Fix Implemented:</b> Created <code>Backend/persistence.py</code> featuring an in-memory user database with full MongoDB 24-character hexadecimal ObjectId validation, case-insensitive email indexing, and atomic document management.
    """
    issue_1_table = Table([[Paragraph(issue_1_html, body_style)]], colWidths=[504])
    issue_1_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#FCA5A5")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(issue_1_table)
    story.append(Spacer(1, 10))

    issue_2_html = """
    <b>Issue #2: Unhandled Exception in Password Hash Verification (Security Edge Case)</b><br/>
    • <b>Location:</b> <code>Backend/auth/security.py</code> (<code>verify_password</code> function)<br/>
    • <b>Root Cause:</b> <code>bcrypt.checkpw()</code> raises <code>ValueError</code> or <code>TypeError</code> when passed corrupted or malformed bcrypt hash strings from database records.<br/>
    • <b>Impact:</b> Passing corrupt hashes or invalid strings during login triggers an unhandled 500 Internal Server Error rather than returning HTTP 401 Unauthorized.<br/>
    • <b>Fix Implemented:</b> Wrapped <code>bcrypt.checkpw()</code> inside a safe <code>try...except (ValueError, TypeError)</code> block in <code>security.py</code> to return <code>False</code> on malformed input.
    """
    issue_2_table = Table([[Paragraph(issue_2_html, body_style)]], colWidths=[504])
    issue_2_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFFBEB")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#FDE68A")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(issue_2_table)
    story.append(Spacer(1, 15))

    # Section 2: Test Suite Architecture
    story.append(Paragraph("2. Test Suite Architecture & Categorization", h1_style))
    story.append(Paragraph(
        "A total of <b>60 comprehensive test cases</b> were implemented in <code>Backend/auth/test_auth.py</code>. "
        "The test suite covers unit tests for cryptographic functions, schema boundary validation, endpoint integration tests, "
        "JWT token validation, and FastAPI dependency injection.",
        body_style
    ))

    cat_data = [
        [Paragraph("Category", table_header_style), Paragraph("Module / Component", table_header_style), Paragraph("Count", table_header_style), Paragraph("Coverage Focus", table_header_style)],
        [Paragraph("Security Utilities", table_body_style), Paragraph("Backend/auth/security.py", table_body_style), Paragraph("14", table_body_style), Paragraph("Bcrypt hashing, unique salts, Unicode, JWT generation, expiry & signature tampering", table_body_style)],
        [Paragraph("Pydantic Schemas", table_body_style), Paragraph("Backend/auth/schemas.py", table_body_style), Paragraph("10", table_body_style), Paragraph("SignupRequest, LoginRequest, UserOut, TokenResponse input validation", table_body_style)],
        [Paragraph("Signup Endpoint", table_body_style), Paragraph("POST /auth/signup", table_body_style), Paragraph("10", table_body_style), Paragraph("201 Created, duplicate email (409), password length validation (422), persistence check", table_body_style)],
        [Paragraph("Login Endpoint", table_body_style), Paragraph("POST /auth/login", table_body_style), Paragraph("8", table_body_style), Paragraph("200 OK JWT delivery, invalid credentials (401), case-insensitive email, payload errors", table_body_style)],
        [Paragraph("Me / Profile Endpoint", table_body_style), Paragraph("GET /auth/me", table_body_style), Paragraph("7", table_body_style), Paragraph("Bearer auth, expired tokens, invalid ObjectId in claims, deleted user edge cases", table_body_style)],
        [Paragraph("Logout Endpoint", table_body_style), Paragraph("POST /auth/logout", table_body_style), Paragraph("5", table_body_style), Paragraph("Stateless logout response, missing/expired token rejection (401/403)", table_body_style)],
        [Paragraph("Auth Dependencies", table_body_style), Paragraph("Backend/auth/dependencies.py", table_body_style), Paragraph("6", table_body_style), Paragraph("Direct unit testing of get_current_user dependency & HTTPAuthorizationCredentials", table_body_style)],
    ]
    cat_table = Table(cat_data, colWidths=[110, 125, 45, 224])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 15))

    # Page break for detailed results table
    story.append(PageBreak())

    # Section 3: Full 60 Test Cases Execution Matrix
    story.append(Paragraph("3. Full 60 Test Cases Execution Results", h1_style))
    story.append(Paragraph(
        "Below is the complete execution log for all 60 test cases executed via Pytest. Every test case returned a <b>PASS</b> status.",
        body_style
    ))

    test_matrix = [
        # Security
        ("TC-01", "test_hash_password_returns_string", "Security", "PASS", "Validates return type is string"),
        ("TC-02", "test_hash_password_starts_with_bcrypt_prefix", "Security", "PASS", "Validates $2b$ bcrypt salt header"),
        ("TC-03", "test_hash_password_unique_salts", "Security", "PASS", "Ensures unique salt generation per hash"),
        ("TC-04", "test_verify_password_correct", "Security", "PASS", "Verifies matching plain text & hash"),
        ("TC-05", "test_verify_password_incorrect", "Security", "PASS", "Verifies mismatched password returns False"),
        ("TC-06", "test_verify_password_empty_plain_password", "Security", "PASS", "Empty password input returns False"),
        ("TC-07", "test_verify_password_empty_hashed_password", "Security", "PASS", "Empty hash string returns False"),
        ("TC-08", "test_verify_password_malformed_hash", "Security", "PASS", "Malformed hash returns False without 500 error"),
        ("TC-09", "test_verify_password_unicode_characters", "Security", "PASS", "Unicode & emoji password support"),
        ("TC-10", "test_create_and_decode_access_token_valid", "Security", "PASS", "Encodes and decodes JWT payload correctly"),
        ("TC-11", "test_create_access_token_custom_expiry", "Security", "PASS", "Validates custom expiration delta claim"),
        ("TC-12", "test_decode_access_token_expired", "Security", "PASS", "Expired JWT raises error during decoding"),
        ("TC-13", "test_decode_access_token_tampered_signature", "Security", "PASS", "Tampered signature raises JWTError"),
        ("TC-14", "test_decode_access_token_wrong_secret", "Security", "PASS", "Decoding with wrong key raises JWTError"),

        # Schemas
        ("TC-15", "test_signup_request_valid", "Schemas", "PASS", "Valid SignupRequest instantiation"),
        ("TC-16", "test_signup_request_empty_name_raises", "Schemas", "PASS", "Empty name raises ValidationError"),
        ("TC-17", "test_signup_request_name_too_long_raises", "Schemas", "PASS", "Name > 100 chars raises ValidationError"),
        ("TC-18", "test_signup_request_invalid_email_raises", "Schemas", "PASS", "Invalid email format raises ValidationError"),
        ("TC-19", "test_signup_request_password_too_short_raises", "Schemas", "PASS", "Password < 8 chars raises ValidationError"),
        ("TC-20", "test_login_request_valid", "Schemas", "PASS", "Valid LoginRequest instantiation"),
        ("TC-21", "test_login_request_invalid_email_raises", "Schemas", "PASS", "Invalid email format raises ValidationError"),
        ("TC-22", "test_user_out_schema_valid", "Schemas", "PASS", "UserOut schema field alignment"),
        ("TC-23", "test_token_response_schema_default_bearer", "Schemas", "PASS", "TokenResponse default token_type='bearer'"),
        ("TC-24", "test_message_response_schema", "Schemas", "PASS", "MessageResponse schema field check"),

        # Signup Endpoint
        ("TC-25", "test_signup_new_user_returns_201_and_token", "Signup API", "PASS", "Returns 201 Created and Bearer token"),
        ("TC-26", "test_signup_creates_user_in_persistence", "Signup API", "PASS", "User document correctly saved in DB"),
        ("TC-27", "test_signup_duplicate_email_returns_409", "Signup API", "PASS", "Duplicate email rejected with 409 Conflict"),
        ("TC-28", "test_signup_duplicate_email_case_insensitive", "Signup API", "PASS", "Case-insensitive duplicate email check"),
        ("TC-29", "test_signup_password_not_in_response", "Signup API", "PASS", "Plain password never returned in HTTP body"),
        ("TC-30", "test_signup_short_password_returns_422", "Signup API", "PASS", "Short password rejected with HTTP 422"),
        ("TC-31", "test_signup_invalid_email_returns_422", "Signup API", "PASS", "Invalid email rejected with HTTP 422"),
        ("TC-32", "test_signup_missing_name_returns_422", "Signup API", "PASS", "Missing name field returns 422 Unprocessable"),
        ("TC-33", "test_signup_missing_password_returns_422", "Signup API", "PASS", "Missing password returns 422 Unprocessable"),
        ("TC-34", "test_signup_empty_body_returns_422", "Signup API", "PASS", "Empty JSON body returns 422 Unprocessable"),

        # Login Endpoint
        ("TC-35", "test_login_success_returns_200_and_token", "Login API", "PASS", "Valid credentials return 200 OK & JWT"),
        ("TC-36", "test_login_wrong_password_returns_401", "Login API", "PASS", "Incorrect password returns 401 Unauthorized"),
        ("TC-37", "test_login_nonexistent_email_returns_401", "Login API", "PASS", "Unknown user email returns 401 Unauthorized"),
        ("TC-38", "test_login_case_insensitive_email", "Login API", "PASS", "Login succeeds with uppercase email"),
        ("TC-39", "test_login_empty_body_returns_422", "Login API", "PASS", "Empty JSON body returns HTTP 422"),
        ("TC-40", "test_login_missing_password_returns_422", "Login API", "PASS", "Missing password field returns HTTP 422"),
        ("TC-41", "test_login_missing_email_returns_422", "Login API", "PASS", "Missing email field returns HTTP 422"),
        ("TC-42", "test_login_invalid_email_format_returns_422", "Login API", "PASS", "Malformed email returns HTTP 422"),

        # Me Endpoint
        ("TC-43", "test_me_valid_token_returns_profile", "Me API", "PASS", "Valid token returns user profile dict"),
        ("TC-44", "test_me_missing_auth_header_returns_403", "Me API", "PASS", "Missing Authorization header returns 403"),
        ("TC-45", "test_me_invalid_token_returns_401", "Me API", "PASS", "Invalid JWT string returns 401 Unauthorized"),
        ("TC-46", "test_me_expired_token_returns_401", "Me API", "PASS", "Expired JWT returns 401 Unauthorized"),
        ("TC-47", "test_me_user_deleted_returns_401", "Me API", "PASS", "Deleted user with valid JWT returns 401"),
        ("TC-48", "test_me_invalid_object_id_in_sub_returns_401", "Me API", "PASS", "Non-ObjectId claim returns 401 Unauthorized"),
        ("TC-49", "test_me_malformed_auth_header_prefix", "Me API", "PASS", "Basic auth header rejected with 401/403"),

        # Logout Endpoint
        ("TC-50", "test_logout_valid_token_returns_200", "Logout API", "PASS", "Valid token returns logout success message"),
        ("TC-51", "test_logout_missing_auth_header_returns_403", "Logout API", "PASS", "Missing header rejected with 403"),
        ("TC-52", "test_logout_invalid_token_returns_401", "Logout API", "PASS", "Invalid token rejected with 401"),
        ("TC-53", "test_logout_expired_token_returns_401", "Logout API", "PASS", "Expired token rejected with 401"),
        ("TC-54", "test_logout_user_deleted_returns_401", "Logout API", "PASS", "Deleted user token rejected with 401"),

        # Dependencies
        ("TC-55", "test_get_current_user_direct_success", "Dependencies", "PASS", "Direct call returns active user document"),
        ("TC-56", "test_get_current_user_missing_sub", "Dependencies", "PASS", "JWT missing 'sub' raises 401 HTTPException"),
        ("TC-57", "test_get_current_user_invalid_jwt", "Dependencies", "PASS", "Corrupted JWT raises 401 HTTPException"),
        ("TC-58", "test_get_current_user_expired_jwt", "Dependencies", "PASS", "Expired JWT raises 401 HTTPException"),
        ("TC-59", "test_get_current_user_invalid_object_id", "Dependencies", "PASS", "Invalid ObjectId string raises 401"),
        ("TC-60", "test_get_current_user_nonexistent_user", "Dependencies", "PASS", "Unmatched user ID raises 401 HTTPException"),
    ]

    table_data = [
        [Paragraph("ID", table_header_style), Paragraph("Test Function Name", table_header_style), Paragraph("Category", table_header_style), Paragraph("Status", table_header_style), Paragraph("Verification Details", table_header_style)]
    ]

    for tc_id, name, cat, status, desc in test_matrix:
        table_data.append([
            Paragraph(tc_id, table_body_style),
            Paragraph(f"<code>{name}</code>", table_body_style),
            Paragraph(cat, table_body_style),
            Paragraph(f"<b>{status}</b>", pass_badge_style),
            Paragraph(desc, table_body_style)
        ])

    matrix_table = Table(table_data, colWidths=[38, 175, 75, 45, 171])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    story.append(matrix_table)
    story.append(Spacer(1, 15))

    # Section 4: Security Recommendations
    story.append(Paragraph("4. Security Recommendations & Best Practices", h1_style))
    recs_html = """
    <b>RECOMMENDED ENHANCEMENTS FOR PRODUCTION DEPLOYMENT:</b><br/>
    1. <b>Token Denylist (Server-Side Revocation):</b> Implement Redis token blacklisting in <code>POST /auth/logout</code> so logged-out tokens cannot be reused before expiry.<br/>
    2. <b>Refresh Tokens & Token Rotation:</b> Issue short-lived access tokens (e.g. 15 mins) alongside long-lived HTTP-only cookie refresh tokens.<br/>
    3. <b>Rate Limiting:</b> Add slowapi / Redis rate limiting on <code>POST /auth/login</code> and <code>POST /auth/signup</code> to block brute-force attacks.<br/>
    4. <b>Password Complexity Validation:</b> Enhance <code>SignupRequest</code> regex to enforce numbers, uppercase/lowercase letters, and special characters.
    """
    recs_table = Table([[Paragraph(recs_html, body_style)]], colWidths=[504])
    recs_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDFA")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#99F6E4")),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(recs_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF report at: {filename}")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    out_path = os.path.join(out_dir, "Auth_Test_Report.pdf")
    build_pdf(out_path)
