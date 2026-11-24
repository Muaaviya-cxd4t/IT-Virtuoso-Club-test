from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from xml.sax.saxutils import escape

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def generate_confirmation_pdf(team, members, whatsapp_link=""):
    """
    Generate a registration confirmation PDF in memory.

    Returns:
        BytesIO: PDF file ready to be sent to the browser.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="ITV Registration Confirmation",
        author="IT Virtuoso Club",
    )

    styles = getSampleStyleSheet()

    navy = colors.HexColor("#101B46")
    blue = colors.HexColor("#3156D3")
    light = colors.HexColor("#F3F5FA")
    border = colors.HexColor("#D9DEEA")
    muted = colors.HexColor("#68728A")
    white = colors.white
    green = colors.HexColor("#16845B")

    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=navy,
        alignment=TA_LEFT,
        spaceAfter=5,
    )

    subtitle_style = ParagraphStyle(
        "SubtitleCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=muted,
        alignment=TA_LEFT,
    )

    section_style = ParagraphStyle(
        "SectionCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=blue,
        spaceBefore=8,
        spaceAfter=8,
    )

    normal_style = ParagraphStyle(
        "NormalCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#18213B"),
    )

    small_style = ParagraphStyle(
        "SmallCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=muted,
    )

    center_style = ParagraphStyle(
        "CenterCustom",
        parent=normal_style,
        alignment=TA_CENTER,
    )

    story = []

    # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------

    story.append(
        Paragraph(
            "IT VIRTUOSO CLUB",
            ParagraphStyle(
                "ClubTitle",
                parent=title_style,
                fontSize=20,
                leading=23,
                textColor=navy,
            ),
        )
    )

    story.append(
        Paragraph(
            "DEPARTMENT OF COMPUTER SCIENCE &amp; ENGINEERING",
            subtitle_style,
        )
    )

    story.append(Spacer(1, 7 * mm))

    story.append(
        Paragraph(
            "REGISTRATION CONFIRMATION",
            ParagraphStyle(
                "ConfirmationTitle",
                parent=title_style,
                fontSize=18,
                leading=22,
            ),
        )
    )

    story.append(
        Paragraph(
            "Your registration and payment have been successfully verified.",
            normal_style,
        )
    )

    story.append(Spacer(1, 7 * mm))

    story.append(
        HRFlowable(
            width="100%",
            thickness=1,
            color=border,
            spaceBefore=2,
            spaceAfter=10,
        )
    )

    # ---------------------------------------------------------
    # Event / Team information
    # ---------------------------------------------------------

    story.append(Paragraph("REGISTRATION DETAILS", section_style))

    event_name = str(team.get("event_name", ""))
    team_name = str(team.get("team_name", ""))
    amount = team.get("amount", 0)
    payment_id = str(team.get("razorpay_payment_id") or "N/A")
    order_id = str(team.get("razorpay_order_id") or "N/A")

    created_at = team.get("created_at")

    if created_at:
        try:
            dt = datetime.fromisoformat(
                str(created_at).replace("Z", "+00:00")
            )
            registration_date = dt.strftime("%d %B %Y, %I:%M %p")
        except ValueError:
            registration_date = str(created_at)
    else:
        registration_date = "N/A"

    details = [
        [
            Paragraph("<b>Event</b>", normal_style),
            Paragraph(escape(event_name), normal_style),
        ],
        [
            Paragraph("<b>Team Name</b>", normal_style),
            Paragraph(escape(team_name), normal_style),
        ],
        [
            Paragraph("<b>Amount Paid</b>", normal_style),
            Paragraph(f"Rs. {amount}", normal_style),
        ],
        [
            Paragraph("<b>Payment Status</b>", normal_style),
            Paragraph(
                '<font color="#16845B"><b>PAID / VERIFIED</b></font>',
                normal_style,
            ),
        ],
        [
            Paragraph("<b>Registration Date</b>", normal_style),
            Paragraph(escape(registration_date), normal_style),
        ],
    ]

    details_table = Table(
        details,
        colWidths=[48 * mm, 115 * mm],
        hAlign="LEFT",
    )

    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), light),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story.append(details_table)

    story.append(Spacer(1, 8 * mm))

    # ---------------------------------------------------------
    # Team members
    # ---------------------------------------------------------

    story.append(Paragraph("TEAM MEMBERS", section_style))

    member_data = [
        [
            Paragraph("<b>#</b>", center_style),
            Paragraph("<b>NAME</b>", normal_style),
            Paragraph("<b>USN</b>", normal_style),
            Paragraph("<b>PHONE</b>", normal_style),
        ]
    ]

    for index, member in enumerate(members, start=1):
        member_data.append(
            [
                Paragraph(str(index), center_style),
                Paragraph(
                    escape(str(member.get("name", ""))),
                    normal_style,
                ),
                Paragraph(
                    escape(str(member.get("usn", ""))),
                    normal_style,
                ),
                Paragraph(
                    escape(str(member.get("phone", ""))),
                    normal_style,
                ),
            ]
        )

    member_table = Table(
        member_data,
        colWidths=[
            12 * mm,
            62 * mm,
            42 * mm,
            47 * mm,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )

    member_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ]
        )
    )

    story.append(member_table)

    story.append(Spacer(1, 8 * mm))

    # ---------------------------------------------------------
    # Payment details
    # ---------------------------------------------------------

    story.append(Paragraph("PAYMENT DETAILS", section_style))

    payment_data = [
        [
            Paragraph("<b>Razorpay Order ID</b>", normal_style),
            Paragraph(escape(order_id), small_style),
        ],
        [
            Paragraph("<b>Razorpay Payment ID</b>", normal_style),
            Paragraph(escape(payment_id), small_style),
        ],
    ]

    payment_table = Table(
        payment_data,
        colWidths=[55 * mm, 106 * mm],
        hAlign="LEFT",
    )

    payment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), light),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story.append(payment_table)

    # ---------------------------------------------------------
    # Event WhatsApp group
    # ---------------------------------------------------------

    if whatsapp_link:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("EVENT WHATSAPP GROUP", section_style))

        whatsapp_style = ParagraphStyle(
            "WhatsAppLink",
            parent=normal_style,
            fontSize=9,
            leading=13,
            textColor=blue,
        )

        whatsapp_text = (
            f'<link href="{whatsapp_link}" color="#3156D3">'
            f'<u>Join the WhatsApp group</u>'
            f'</link>'
        )

        whatsapp_table = Table(
            [
                [
                    Paragraph("<b>Group</b>", normal_style),
                    Paragraph(whatsapp_text, whatsapp_style),
                ]
            ],
            colWidths=[55 * mm, 106 * mm],
            hAlign="LEFT",
        )

        whatsapp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), light),
                    ("BOX", (0, 0), (-1, -1), 0.7, border),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, border),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        story.append(whatsapp_table)

    story.append(Spacer(1, 10 * mm))

    # ---------------------------------------------------------
    # Footer message
    # ---------------------------------------------------------

    story.append(
        Paragraph(
            "Keep this confirmation for your records. "
            "Your registration is considered complete after successful "
            "payment verification.",
            small_style,
        )
    )

    story.append(Spacer(1, 7 * mm))

    story.append(
        Paragraph(
            "IT Virtuoso Club • Department of Computer Science & Engineering",
            ParagraphStyle(
                "Footer",
                parent=small_style,
                alignment=TA_CENTER,
            ),
        )
    )

    document.build(story)

    buffer.seek(0)
    return buffer