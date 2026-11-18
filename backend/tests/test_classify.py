from app.ingest import classify as C

UNI_2425 = "Annual-Report-AY-2024-2025_311025_Version-4-Final-Version-From-Anil_compressed.pdf"
UNI_2324 = "Annual-Report-AY-2023-2024_180325_V5.pdf"
COE_2425 = "Annual-Report_AY-2024-25.pdf"  # Examination Department report, different document


def test_university_annual_report_is_indexed():
    assert C.should_index_pdf("cdn/s3bucket-images/" + UNI_2425, 7_400_837)
    assert C.should_index_pdf("2025/07/" + UNI_2324, 3_611_276)


def test_exam_department_annual_report_stays_excluded():
    assert not C.should_index_pdf("2026/01/" + COE_2425, 4_229_196)


def test_annual_report_metadata():
    assert C.family_of(UNI_2425) == C.family_of(UNI_2324) == "university annual report"
    assert C.academic_year_of(UNI_2425) == "2024-25"
    assert C.academic_year_of(UNI_2324) == "2023-24"
    assert C.school_of(UNI_2425) is None  # university-wide
    assert C.category_of(UNI_2425) == "general"
    assert C.display_title(UNI_2425) == "Bennett University Annual Report 2024-25"
    assert C.display_title("Notification-for-Minimum-Attendance.pdf") == "Notification for Minimum Attendance"
