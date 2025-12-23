"""
Export functionality for vulnerability scan results

Supports:
- CSV export for Excel/spreadsheet analysis
- PDF export for executive summaries/reports
- JSON export for automation/integration
"""
import csv
import io
from datetime import datetime
from typing import List, Dict
from .models import ScanResult, Vulnerability


def generate_csv(scan_result: Dict) -> str:
    """
    Generate CSV export from scan result

    Args:
        scan_result: ScanResult dict

    Returns:
        CSV string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        'Bug ID',
        'Severity',
        'Headline',
        'Summary',
        'Status',
        'Affected Versions',
        'Labels',
        'URL'
    ])

    # Data rows
    vulnerabilities = scan_result.get('vulnerabilities', [])
    for vuln in vulnerabilities:
        # Clean HTML tags from summary if present
        summary = vuln.get('summary', '') or ''
        summary = summary.replace('<B>', '').replace('</B>', '').replace('<BR>', ' ')

        writer.writerow([
            vuln.get('bug_id', ''),
            vuln.get('severity', ''),
            vuln.get('headline', ''),
            summary,
            vuln.get('status', ''),
            vuln.get('affected_versions', ''),
            ', '.join(vuln.get('labels', [])),
            vuln.get('url', '')
        ])

    return output.getvalue()


def generate_pdf(scan_result: Dict) -> bytes:
    """
    Generate PDF export from scan result

    Args:
        scan_result: ScanResult dict

    Returns:
        PDF bytes

    Note: Requires reportlab or fpdf library
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise RuntimeError(
            "reportlab is required for PDF export. "
            "Install with: pip install reportlab"
        )

    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)

    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=12,
        spaceBefore=12
    )

    # Title
    elements.append(Paragraph("Vulnerability Scan Report", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Summary section
    elements.append(Paragraph("Scan Summary", heading_style))

    summary_data = [
        ['Platform:', scan_result.get('platform', 'N/A')],
        ['Version:', scan_result.get('version', 'N/A')],
        ['Scan ID:', scan_result.get('scan_id', 'N/A')],
        ['Total Bugs Checked:', str(scan_result.get('total_bugs_checked', 0))],
        ['Version Matches:', str(scan_result.get('version_matches', 0))],
        ['Critical/High:', str(scan_result.get('critical_high', 0))],
        ['Medium/Low:', str(scan_result.get('medium_low', 0))],
        ['Scan Time:', f"{scan_result.get('query_time_ms', 0):.2f} ms"],
    ]

    # Add feature filtering info if present
    if scan_result.get('features'):
        summary_data.append(['Features Checked:', str(len(scan_result.get('features', [])))])
        if scan_result.get('feature_filtered') is not None:
            reduction = scan_result.get('version_matches', 0) - scan_result.get('feature_filtered', 0)
            if scan_result.get('version_matches', 0) > 0:
                pct = (reduction / scan_result.get('version_matches', 0)) * 100
                summary_data.append(['Feature Filtering:', f'{reduction} bugs filtered ({pct:.0f}% reduction)'])

    summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))

    # Vulnerabilities section
    vulnerabilities = scan_result.get('vulnerabilities', [])
    if vulnerabilities:
        elements.append(Paragraph(f"Vulnerabilities ({len(vulnerabilities)} total)", heading_style))
        elements.append(Spacer(1, 0.1*inch))

        # Table header
        vuln_data = [['Bug ID', 'Severity', 'Headline', 'Status']]

        # Table rows
        for vuln in vulnerabilities[:50]:  # Limit to 50 for PDF size
            severity_map = {1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low', 5: 'Low', 6: 'Low'}
            severity_text = severity_map.get(vuln.get('severity', 6), 'Unknown')

            headline = vuln.get('headline', '')[:60]  # Truncate long headlines
            if len(vuln.get('headline', '')) > 60:
                headline += '...'

            vuln_data.append([
                vuln.get('bug_id', ''),
                severity_text,
                headline,
                vuln.get('status', '')
            ])

        vuln_table = Table(vuln_data, colWidths=[1.2*inch, 1*inch, 3*inch, 1*inch])
        vuln_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        elements.append(vuln_table)

        if len(vulnerabilities) > 50:
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph(
                f"<i>Note: Showing first 50 of {len(vulnerabilities)} vulnerabilities. "
                f"Export to CSV for full list.</i>",
                styles['Normal']
            ))

    else:
        elements.append(Paragraph("No vulnerabilities found.", styles['Normal']))

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Cisco PSIRT Vulnerability Analysis System",
        footer_style
    ))

    # Build PDF
    doc.build(elements)

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def generate_json(scan_result: Dict) -> Dict:
    """
    Generate JSON export from scan result

    Args:
        scan_result: ScanResult dict

    Returns:
        JSON-serializable dict
    """
    # Clean up datetime objects for JSON serialization
    result = scan_result.copy()

    # Convert datetime to ISO string
    if 'timestamp' in result and isinstance(result['timestamp'], datetime):
        result['timestamp'] = result['timestamp'].isoformat()

    # Clean HTML from summaries
    for vuln in result.get('vulnerabilities', []):
        if 'summary' in vuln and vuln['summary']:
            vuln['summary'] = (
                vuln['summary']
                .replace('<B>', '')
                .replace('</B>', '')
                .replace('<BR>', ' ')
            )

    return result
